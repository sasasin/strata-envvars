# `STRATA_PREFILL_LEND_PCT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--prefill auto` でプロンプト用バッファを GPU の expert cache から借りるとき、借りる cache slot 数の上限を割合で指定します。自動 chunk の選択では、必要な slot 数がこの割合を超える候補を除外します。layer split の自動配置・起動可能性判定にも同じ割合が使われます。

この変数はプロンプト借用そのものを有効にしません。`--no-prefill-borrow`、profile 不在、cache 不在などで借用経路に入らない場合は、値を設定しても借用は起きません。通常の明示的な `--prefill N` では割合上限を適用せず、chunk が cache に収まるかで判定します。

## 値と判定

3箇所とも `getenv()` の結果を `std::atoi()` で整数化します。文字列全体の妥当性検査や 0–100 への clamp はありません。

| 設定 | 判定値 |
|---|---:|
| 未設定 | pinned expert の割合が 90% 以上なら 90、未満なら 85（ただし split の配置探索・probe は下記参照） |
| 空文字 | `atoi("")` により 0 |
| 数字で始まる文字列 | `atoi` が読み取った整数。例: `80tail` は 80、`-5` は -5 |
| 数字に変換できない文字列 | 0 |
| `100` より大きい値 | そのまま使う。別の「cache に128 slot残す」条件が上限になる |
| 0 または負数 | 自動借用の割合条件を満たせず、実質的に自動借用を抑止する |

整数変換は大文字小文字に関係しません。`atoi` のため小数や単位付きの値を割合として解釈しません。

## 有効になる条件

- 単一 GPU の `generate` / `serve` で自動 chunk を選び、expert cache から借りられること。`--prefill auto` は expert profile がない場合、または `--no-prefill-borrow` の場合に自動選択を解除して 2048-token chunk に切り替えます。
- layer split では、自動配置探索と `STRATA_LAYER_SPLIT_PROBE` が割合を用いた借用可否判定をします。probe 自体は `multi_gpu && split_auto && split_probe` の場合だけ実行されます。
- 実際に借りられる slot 数には、割合に加えて cache に128 slot以上残す条件があります。serve では全 split participant が chunk を貸せる必要があり、小さいカードがあると単独 GPU の選択より chunk が小さくなることがあります。
- 固定 chunk の `--prefill N` では、この割合 cap は適用されません。ただし必要 slot が収まらなければ借用できず、自前バッファへ fallback します。
- `--no-prefill-borrow` を指定すると借用判定に入りません。

## 実行時の詳細

単一 GPU の自動 chunk 選択では、`plan_lend()` が chunk ごとの必要 slot 数を算出し、`k + 128 <= cache slots` と `k * 100 <= percentage * cache slots` の両方を満たす chunk を選びます。新しい ring byte-budget 経路では割合から slot 予算も作り、その予算内で chunk と streamed ring のサイズを決めます。借用できた slot は prompt path のバッファとして使われ、プロンプト後に cache 用として refilling されます。選択した chunk は stderr に `strata generate: prompt chunk auto: ...` と出力され、borrow した slot 数もログに出ます。

serve の layer split は各 GPU cache に対して同じ割合 cap を適用します。参加 GPU のうちいずれかで希望 chunk が収まらないと、より小さな chunk に落とすことがあり、stderr に `prompt chunk ..., not ...` の警告を出します。明示 chunk はこの割合条件を外して slot と128-slot floorのみを見ます。

読み取り箇所はいずれも環境から整数を取得してローカル値へ保持し、設定を継続的に監視しません。split 配置探索と L2 probe の値はそれぞれの探索時に取得され、通常の chunk 選択用の値は engine の prefill 計画時に取得されます。server の各リクエストで再取得する処理はありません。

未設定時の注意点: split 配置探索（`generate.cpp:3903-3906`）と L2 probe（`5633-5637`）は、実際の pinned ratio を計算して `Prefill::set_pinned_share()` を呼ぶ箇所（`6533-6545`）より前に走ります。`g_pinned_share` の初期値は `1.0` なので、この2箇所では未設定時に 90 が選ばれます。一方、通常の prefill 計画は pinned ratio 設定後に実行され、実測 ratio に応じて 90 または 85 になります。明示値を設定した場合は3箇所とも同じ `atoi` 値です。

## ログ・資料との照合

`docs/DETAILS.md` は `--prefill auto` の最大 chunk と streamed ring の選び方を説明していますが、`STRATA_PREFILL_LEND_PCT` 自体の設定仕様は記載していません。ソースコメントは、pinned RAM から DMA copy する場合は90%、host copy が律速の場合は85%を既定値にする意図を説明しています。また12 GBカード・Q2_0・32K prompt の比較値をコメントに記載していますが、この環境変数の効果を独立したベンチマーク結果として docs が保証しているわけではありません。

## 根拠

- `src/program/generate.cpp:2523-2526` — auto prefill が borrow/profile 不在時に解除される条件。
- `src/program/generate.cpp:3903-3907,4013-4028,5631-5653` — split 配置探索・L2 probe における parse、既定値、slot 上限判定。
- `src/program/generate.cpp:6533-6545` — pinned expert の byte ratio 算出と `Prefill` への設定。
- `src/prefill/prefill.cpp:213,1859-1865` — pinned ratio の初期値と getter/setter。
- `src/program/generate.cpp:6598-6611,6677-6710,6725-6745` — 通常の既定値と auto chunk/ring 予算への適用。
- `src/program/generate.cpp:7343-7350,7404-7425,7452-7459` — serve の split participant ごとの cap、明示 chunk の扱い、警告。
- `src/program/generate.cpp:13169-13206` — prefill 借用実行と chunk/borrow ログ。
- `docs/DETAILS.md:1926-1932` — auto prefill と ring 選択についての資料。
