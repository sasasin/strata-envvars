# `STRATA_PREFILL_LM_EVEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

layer-major prefill の super-chunk を、VRAM 等に収まる最大サイズと末尾の小さい余りに分けるか、同じ数のほぼ均等な super-chunk に分けるかを切り替える。既定は均等分割で、無効にすると適合する最大サイズを先に使う。均等分割は、たとえば 32K tokens の読み込みで 28K が適合する場合、`28K + 4K` ではなく `16K + 16K` にする計算である。layer-major 経路そのものの有効化スイッチではない。`engine/src/prefill/prefill.cpp:8093-8095, 8342-8388`。

## 値と判定

`lm_even_env()` が `std::getenv` の文字列の**先頭 1 文字だけ**を調べる。未設定、空文字、先頭が `0` 以外なら有効（均等分割）。先頭が `0` なら無効。数値変換や文字列全体の比較はなく、空白除去・大文字小文字判定もない。`engine/src/prefill/prefill.cpp:8093-8095`。

| 条件 | unset | 均等分割になる値 | 最大サイズ優先になる値 |
|---|---|---|---|
| layer-major の適合サイズが複数 super-chunk に分かれ、均等化後サイズが小さくなる場合 | 有効 | `1`, `1anything`, `true`, `false`, ` `（先頭が `0` 以外） | `0`, `0anything` |
| 上記以外の分割条件 | 判定に到達しない場合あり | この変数による差なし | この変数による差なし |

空文字は設定済みでも先頭文字がないため有効になる。`0.5` や `0abc` は無効、` 0` は先頭が空白なので有効。CLI 引数による値の上書き・優先順位はなく、この環境変数の値を直接読む。ほかの設定が作る適合上限や、layer-major 経路の選択条件は別途影響する（下記）。`engine/src/prefill/prefill.cpp:8093-8095, 8375-8388`。

## 有効になる条件

- `Prefill::run()` が layer-major 経路を選び、`lm_prepare_chain()` が呼ばれる必要がある。通常は `STRATA_PREFILL_LAYER_MAJOR` が明示的に有効であることが必要。未設定時の標準判定は現行コードでは false。小さい expert cache 向けの自動選択は、1 GPU・auto chunk・native pack 等の条件下で `STRATA_PREFILL_LAYER_MAJOR` を設定することがある。`engine/src/prefill/prefill.cpp:9657-9677`、`engine/include/strata/core/sm120_series.hpp:184-191, 211-218`、`engine/src/program/generate.cpp:12562-12612`。
- HIP build は別途 `STRATA_LM_HIP=1` が必要。Metal の `Prefill::run()` は先行する Metal 経路を実行して戻るため、この layer-major 判定には到達しない。`engine/src/prefill/prefill.cpp:8166-8179, 9633-9651`。
- `lm_prepare()` が layer-major を拒否しないこと。拒否条件には未初期化モデル、GPU peer / chunk hand-off、split 時の PLE 配置、画像 prompt、非対応 DFlash2 taps、`STRATA_KVA` 有効、chunk 境界で yield する batch、`--prefill-pipe` の chunk 指定、ビルド済み nibble expert の有効化、routing/row debug dump、MMQ/FP16 用 buffer 不足、非対応 expert format や fused layout がある。`engine/src/prefill/prefill.cpp:8166-8234`。
- prompt が必要最小長以上であり、各 stage 共通の適合 super-chunk が確保できること。明示的な `STRATA_PREFILL_LM_TOKENS`、VRAM margin / residual 配置の設定、GPU の空きメモリや layer split の stage ごとの上限が適合サイズを決める。`engine/src/prefill/prefill.cpp:8235-8285, 8342-8388`。
- この変数が実際の分割を変えるのは、`k = ceil(n / cap)` が 2 以上で、`T` 単位に丸めた均等サイズが `cap` より小さい場合だけ。そうでなければ有効値でも `cap` のまま。`engine/src/prefill/prefill.cpp:8375-8388`。

## 実行時の詳細

値は `lm_even_env()` の関数内 `static const bool` に初回評価時の結果を cache する。初回評価は、共通の `cap` が決まり、`k >= 2` かつ均等化サイズ `< cap` となるまで遅れる（条件式の短絡評価による）。その初回評価後にプロセス環境を変更しても反映されない。`engine/src/prefill/prefill.cpp:8093-8095, 8375-8378`。

有効時は `k = ceil(n / cap)` を求め、`even = ceil(ceil(n / k) / T) * T` を計算する。`even < cap` なら各 stage の既存 buffer を解放して `even` で再準備し、全 stage の chunk サイズをそろえる。無効時または `even >= cap` なら適合済み `cap` を返す。`lm_run()` は `m.lm.S` を super-chunk サイズとして各 prompt を切り分ける。`engine/src/prefill/prefill.cpp:8375-8388, 8475-8511`。

均等サイズでの再準備に失敗した場合、`lm_prepare_chain()` は失敗理由を返して layer-major 用 buffer を解放する。通常の `run()` はその prompt の layer-major 経路を見送り、`run_impl()` に進む。つまり均等サイズ確保の失敗時に、同じ prompt で不均等な `cap` に自動再試行する処理はない。複数 prompt の `run_multi()` では準備失敗を `prefill: multi-prompt read declined: ...` として返す。`engine/src/prefill/prefill.cpp:8379-8393, 8421-8432, 9677-9705`。

## ログと測定値

この変数だけを理由に出す専用ログはない。通常経路で layer-major の準備が失敗すると `strata prefill: layer-major off for this prompt: <理由>` が stderr に出る（同じ理由の重複と、既定選択での短い prompt は抑制される）。適用された場合は layer-major の実行統計 `strata prefill: layer-major (layers ...): ...` が stderr に出る。`engine/src/prefill/prefill.cpp:9694-9702, 9566-9574`。

`docs/DETAILS.md` にこの変数固有の説明・測定値は見つからなかった。ここではソースコード上の分割計算だけを記載し、性能差は推定していない。

## 根拠

- `engine/src/prefill/prefill.cpp:8093-8095` — 対象名の唯一の実読み取りと先頭文字判定。
- `engine/src/prefill/prefill.cpp:8166-8234` — layer-major 経路の backend・状態・機能上の拒否条件。
- `engine/src/prefill/prefill.cpp:8235-8285` — prompt 長、目標サイズ、空き VRAM と適合サイズ。
- `engine/src/prefill/prefill.cpp:8342-8393` — layer split 共通 cap と均等化処理、再確保失敗。
- `engine/src/prefill/prefill.cpp:8475-8511, 9633-9705` — super-chunk の利用、実行経路と fallback。
- `engine/include/strata/core/sm120_series.hpp:184-191, 211-218` — layer-major の unset default と small-card 条件。
- `engine/src/program/generate.cpp:12562-12612` — small-card prompt path による layer-major 自動選択。
- `engine/src/prefill/prefill.cpp:9566-9574, 9694-9702` — stderr の実行統計・準備失敗ログ。
