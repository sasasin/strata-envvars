# `STRATA_PF_PLAIN_FLOOR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

ビルド時に llama.cpp の MMQ prompt kernel を含まず、native 形式ではない plain Q2_0 pack を fused kernel で扱う場合に、離散 CUDA GPU 上で長い prompt chunk を streamed walk に切り替える token 数の floor を既定の 64 から 1,536 に引き上げる。短い chunk では routed expert だけを staged walk で処理し、そのうち該当する expert は dequantize + FP16 経路を使う。変数が変えるのはこの prompt 処理経路の境界であり、生成時の token 選択を直接変更する設定ではない。実装は `plain_discrete_floor_now()` と `stream_all_min()`（`src/prefill/prefill.cpp:598-625`）、値判定は純粋関数 `plain_floor_off()`（`include/strata/prefill/plain_floor_rule.hpp:29-35`）。

## 値と判定

`plain_discrete_floor_now()` が `std::getenv` で取得し、値を数値変換せず `plain_floor_off()` に渡す。無効化されるのは文字列全体が厳密に `"0"` の場合だけ。未設定、空文字、`"00"`、`"0anything"`、`"1"`、`"true"`、`"false"`、空白を含む値などはすべてこのルールを有効にする。大文字小文字や数値としての妥当性は検査しない。`include/strata/prefill/plain_floor_rule.hpp:29-35`

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 下記の適用条件を満たし、`STRATA_PREFILL_STREAM_MIN` による上書きがない | 有効（1,536 floor） | 空文字、`1`、`true`、`00`、`0anything` | 厳密に `0` のみ |
| その他の build / GPU / pack 条件 | floor を変更しない | floor を変更しない | floor を変更しない |

この変数自体の既定は無効ではなく、条件を満たせば unset でも新 floor が使われる。1,536 は環境変数から読む値ではなく、`kPlainDiscreteFloor` の定数（`include/strata/prefill/plain_floor_rule.hpp:26-27`）。ただし `STRATA_PREFILL_STREAM_MIN` が設定され、その `std::atoll` 結果が 0 以上なら `stream_all_min()` はその値を返し、この変数による floor は適用されない。空文字や数値に変換できない文字列は `atoll` により 0 となり、同様に上書きとして扱われる。負値は `env >= 0` の条件を通らず、この上書き経路では採用されない（`src/prefill/prefill.cpp:614-625`）。

適用条件内では、CPU share の limit が有効でもこの変数が有効なら `max(default_floor, 1536)` が返り、share limit に置き換わらない。無効なら従来どおり share limit が正数の場合はそれを使い、そうでなければ default floor を使う（`include/strata/prefill/plain_floor_rule.hpp:38-43`）。plain pack の default floor は 64（`include/strata/prefill/stream_floor_rule.hpp:20-21,45-50`）。

## 有効になる条件

- `STRATA_PF_OWN_ONLY` が定義された、llama.cpp の MMQ prompt kernel を含まない build であること。MMQ build では helper が常に false を返す（`src/prefill/prefill.cpp:482-490,601-612`）。
- expert layout が読み込まれ、native pack ではなく、少なくとも 1 層あること。`STRATA_PREFILL_MMQ=0` は fused plan を無効にし、fused kernel が build 済みかつ有効である必要がある（`src/prefill/prefill.cpp:479-490`）。
- CUDA の離散 GPU であること。GPU の属性が取得できない場合は integrated 扱いとなり、この floor は適用されない。統合 GPU と HIP build でも適用されない（`src/prefill/prefill.cpp:601-612,3413-3426`）。
- GPU の expert share 情報が既知であること。`set_card_expert_share()` が呼ばれる単一 GPU・batch slots なしの経路で情報を受け取るまでは false を返し、target env を読まず、cache もしない（`src/prefill/prefill.cpp:443-448,457-471,601-609`）。
- `STRATA_PREFILL_STREAM_MIN` が未設定、またはその変換結果が負値で、明示 floor の上書きが起きていないこと（`src/prefill/prefill.cpp:614-616`）。

## 実行時の詳細

prompt chunk のサイズが `stream_all_min()` 以上なら streamed walk を選び、下回れば staged walk を選ぶ。streamed walk は各層の非 resident expert を ring 経由で読み、staged walk は routed expert を処理する。判定は `ring_slots()` など prompt 経路から `stream_all_min()` を呼ぶ箇所で利用される（`src/prefill/prefill.cpp:794-830,4389-4390`; `include/strata/prefill/stream_floor_rule.hpp:1-5`）。plain pack において floor が上がると、share limit が従来の境界だった場合も含め、1,536 token 以上で streamed walk、未満で staged walk となる。

`STRATA_PREFILL_STREAM_MIN` の値は `stream_all_min()` 内の function-local `static` に初回呼び出し時に保存される。対象変数は別の `plain_discrete_floor_now()` 内の atomic cache に保存され、layout と GPU class が既知になった後の初回評価で決まる。条件が揃う前の呼び出しは false を返すだけで cache しない。したがって対象変数は条件成立後の評価で一度読み取られ、その後のプロセス内変更は反映されない（`src/prefill/prefill.cpp:601-620`）。

## ログと測定値

対象変数専用の警告、エラー、終了経路はない。build without MMQ では floor を反映した起動時の経路説明が出る。plain pack の floor が標準の 1,024 と異なる場合の文言は `prefill: prompt pieces of <N> tokens or more read on the fused kernels, as long prompts do. STRATA_PF_PLAIN_FLOOR=0 keeps the earlier rule; STRATA_PREFILL_STREAM_MIN=N sets the number by hand.`。また prompt kernel の計画行は `strata: prompt kernels: chunks of <N> tokens or more run ...; shorter chunks run ... .` の形で floor と各経路の layer 数を示す。出力は `stderr` で、plan と GPU/share 情報が揃った後に一度出す（`include/strata/prefill/own_only_line.hpp:56-76,79-103`; `src/prefill/prefill.cpp:627-636,2038-2062,3666-3673`）。

実装コメントにある測定は RTX 5070 12 GB、PCIe 4.0 x16、非 resident expert 15.6% の plain pack、MMQ なし build と MMQ build の比較。floor 64 の streamed walk は約 1.27 秒の固定コストで、256-token prompt は 1,224 ms 対 590 ms、1,000-token prompt は 1,252 ms 対 1,050 ms。staged FP16 経路は token あたり約 0.41 ms 増え、両経路は約 1,420 tokens で交差したため、離散 CUDA GPU では 1,536 を採用したとコメントに記載されている。他の離散 GPU class は未測定であり、この測定値は一般化できない。測定条件と数値は設計コメントの記録であり、本調査で再計測していない（`include/strata/prefill/plain_floor_rule.hpp:11-17,26-27`）。

## 根拠

- `include/strata/prefill/plain_floor_rule.hpp:11-17,26-43` — 設計背景、測定条件、値判定、floor 合成。
- `src/prefill/prefill.cpp:479-490,598-625` — plain pack 条件、対象環境変数の読み取り、cache、stream floor と上書き優先順位。
- `src/prefill/prefill.cpp:3413-3426` — GPU 属性と expert share 情報の設定。
- `src/prefill/prefill.cpp:794-830,4389-4390` — prompt chunk の floor による経路選択。
- `include/strata/prefill/own_only_line.hpp:56-76,79-103` — 観測可能な起動ログと出力時期。
- `include/strata/prefill/stream_floor_rule.hpp:20-21,28-30,45-50` — plain pack の標準 floor と build 条件。
