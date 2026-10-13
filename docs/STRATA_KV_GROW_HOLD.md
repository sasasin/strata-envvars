# `STRATA_KV_GROW_HOLD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

`--serve` の弾性 K/V（`--kv-grow`）が有効なとき、短いリクエストの開始時に K/V 領域を縮める際の保持量を決めます。既定では次のリクエストが必要とする prompt 分（`n + 256` cells）まで縮めます。非ゼロ値を指定すると、これに加えて、会話キャッシュに駐車中の最長会話を復元できる分も保持対象にします。これにより、その会話を復元するたびに K/V を拡張し直す機会を減らします。

この変数だけでは弾性 K/V を有効にしません。弾性 K/V 自体を有効にする条件は `STRATA_KV_GROW` / `--kv-grow` の項に記載します。

## 値と判定

値全体の parse や文字列比較ではなく、`std::atoi(v) != 0` で判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | `atoi("")` が 0 のため無効 |
| 整数として 0 になる文字列 | 無効。例: `0`, `abc`, `0tail` |
| `atoi` が非ゼロを返す文字列 | 有効。例: `1`, `-1`, `2tail`, ` 1` |

したがって `=1` だけが有効なわけではなく、負の非ゼロ値も有効です。`atoi` は文字列全体の厳密な検証をしないため、先頭の空白や符号の後の数値を読み、数値の後ろにある文字は判定に影響しません。数値変換できない文字列は 0 として扱われます。

## 有効になる条件

- サーバーのリクエスト処理で `kvg.on` が true であること。弾性 K/V の初期化は CUDA 経路で行われ、単一 GPU、プロファイル済み expert cache、全 K/V を VRAM に置く構成、RAM 上の全 expert、VMM 対応が必要です。`--batch`、`--vram-elastic`、`--peer-device`、remote expert cache などとの併用では初期化側で無効になります。無効化された要求があると stderr に `strata generate: --kv-grow is off (...)` が出ます。
- 会話キャッシュが有効で駐車中の会話があるときに保持量の差が現れます。`longest_tokens()` は駐車中エントリーの `live.ids.size()` の最大値を返します。会話がなければ 0 なので、変数を有効にしても追加保持量はありません。
- `STRATA_KV_GROW_HOLD` の値は、弾性 K/V が有効なサーバーで、リクエスト開始時の trim 分岐に初めて到達した時にだけ読み込まれます。

## 実行時の詳細

サーバーは次のリクエストの prompt 長 `n` に対して、まず `kvg_ensure(n + 256, ...)` を行います。以前のリクエストから残った K/V が不足すると、必要量まで拡張します。その後、以前の会話状態を駐車し、復元対象の会話を取り出して必要なら拡張したうえで、現在のリクエストが再利用する prefix より後の K/V を書き換える前に trim します。

trim の希望量は `max(n + 256, hold)` です。`hold_on` が false なら `hold=0`、true なら `hold=conversations.longest_tokens() + 256` です。`kvg_trim` は希望量を `STRATA_KV_GROW_STEP` 単位（既定 8192 cells）に切り上げ、少なくとも1 step を残します。現在量が目標より 2 step 以上大きく、返却可能な expert slot がある場合に縮小し、解放した領域を expert cache に戻して profile 順に expert を補充します。差が小さい場合や返却可能 slot がない場合は縮小しません。そのため、この変数は厳密な保持 cell 数や VRAM 量を指定するものではありません。

値の判定は関数内の `static const bool` 初期化で一度だけ行われます。プロセス内で最初に trim 分岐へ到達した後に環境を変更しても再評価されません。保持量自体は各リクエストの trim 時にその時点の `conversations.longest_tokens()` から計算します。

縮小失敗時は stdout に `ERR the K/V could not give its VRAM back to the expert cache` を出し、サーバー処理は `1` を返して終了します。縮小が成功した場合は、K/V の cell 数と cache に戻した slot 数を stderr に `strata: K/V trimmed to ...` と出します。

## 文書との照合

`docs/DETAILS.md` は `--kv-grow` / `STRATA_KV_GROW` がリクエストで到達した cell 分だけ K/V に VRAM を使い、長い context に応じて expert cache の slot を譲る機能であると説明しています。`STRATA_KV_GROW_HOLD` の保持ポリシー自体は同資料に説明がありません。上記の保持動作はソースコードから確認した範囲です。

## 根拠

- `src/program/generate.cpp:4221-4238`: `STRATA_KV_GROW` と `STRATA_KV_GROW_INIT` の読み取り、弾性 K/V を有効にする条件、無効時のログ。
- `src/program/generate.cpp:6410-6424`: `kvg.on` の実条件、step の既定値と `STRATA_KV_GROW_STEP` の読み取り。
- `src/program/generate.cpp:6530-6597`: trim 量の step 丸め、縮小条件、expert cache への slot 返却・補充、ログと失敗処理。
- `src/program/generate.cpp:10214-10221,10362-10365,10437-10448`: request ごとの K/V 拡張、駐車会話の復元と、`STRATA_KV_GROW_HOLD` による trim 保持量。
- `include/strata/core/conversation_cache.hpp:210-215`: 最長駐車会話の token 数の定義。
- `docs/DETAILS.md:260-264`: `--kv-grow` の概要と利用条件。
