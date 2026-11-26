# `STRATA_PLE_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査対象リポジトリの作業ツリーは `## main...origin/main`。

## 役割

PLE テーブルを direct I/O で開いた後に行う起動時の読み取り速度計測を抑止する。設定が無い場合は `ple_direct_rows_per_s()` を呼び、結果に応じて速度ログ、低速警告、または `STRATA_PLE_AUTO_MMAP` による mmap への切り替えを行う。設定があると、この分岐全体を実行しない。環境変数自身が PLE の I/O モードを指定したり、必ず direct を選んだりするわけではない。CUDA/HIP 共通の `engine/src/program/generate.cpp` と SYCL の `engine/sycl/src/program/generate.cpp` に同じ判定がある（`engine/src/program/generate.cpp:6350-6383`、`engine/sycl/src/program/generate.cpp:3373-3406`）。

## 値と判定

両実装とも `std::getenv("STRATA_PLE_PROBE") == nullptr` のときだけ計測ブロックに入る。値の内容は読み取らず、文字列比較・数値変換・真偽値 parse はしない。unset は計測を許可し、空文字を含む何らかの設定値は計測を抑止する。

| 条件 | unset | 計測を抑止する値 | 無効値・境界 |
|---|---|---|---|
| CUDA/HIP `generate` と SYCL `generate` の PLE direct 経路 | 計測を行う | 空文字、`0`、`1`、`true`、`false`、その他すべての設定値 | 値の形式・大文字小文字・空白・数値としての妥当性を検査しない。設定されていれば一律に抑止する（`engine/src/program/generate.cpp:6352`、`engine/sycl/src/program/generate.cpp:3375`）。 |

## 有効になる条件

- `o.ple_gguf` が空でなく、PLE テーブルを開く経路であること。PLE GGUF がない場合は、この読み取りを含むテーブル処理に入らない（`engine/src/program/generate.cpp:6264-6271`、`engine/sycl/src/program/generate.cpp:3346-3353`）。
- テーブルの現在の I/O モードが `Direct` であること。`--ple-io` の既定値は `direct` で、`mmap` または `ram` は `Mmap` に設定されるため、直接指定された場合は計測ブロックの対象外（`engine/src/program/generate.cpp:817-819, 6271-6272`、`engine/sycl/src/program/generate.cpp:501-503, 3352-3353`）。
- `STRATA_PLE_AUTO_RAM` のポリシーで先にテーブルが `Mmap` に切り替わった場合も対象外。CUDA/HIP 実装では direct かつ `--ple-io` 未指定のときにポリシーを評価し、採用時に `pio.mode` を変更してから probe 条件を判定する（`engine/src/program/generate.cpp:6303-6327, 6352`）。
- 他の環境変数との相互作用として、probe が許可され、測定値が低速域に入った後でのみ `STRATA_PLE_AUTO_MMAP` が自動切替を制御する。`STRATA_PLE_PROBE` が設定済みなら、その後段まで到達しない（`engine/src/program/generate.cpp:6352-6375`、`engine/sycl/src/program/generate.cpp:3375-3398`）。

## 実行時の詳細

判定はテーブル open 後、初回の prompt 処理に進む前の `generate` 実行中に行われる。関数内 static cache はなく、この箇所で `getenv` を評価する。読み取りは PLE GGUF が存在する場合に限られ、現在のモードが direct のときだけ値の有無が条件に使われる（`engine/src/program/generate.cpp:6269-6288, 6352`、`engine/sycl/src/program/generate.cpp:3350-3369, 3375`）。

未設定なら、テーブルの行数が 4096 未満のとき計測関数は `-1` を返し、それ以外では疑似乱数で行を選び、4 token 分（1 batch 64 行）の `gather_batch` を最大 64 batch、経過時間が約 0.6 秒を超えるまで実行して rows/s を算出する。読み取りに失敗した場合も `-1` を返す。値が 15000 rows/s 以上なら `PLE direct read probe: … (fine)` を出し、0 より大きく 15000 未満なら、`--ple-io` が明示されておらず、かつ `STRATA_PLE_AUTO_MMAP` の `atoi` 結果が非ゼロの場合に限り mmap に切り替える。それ以外は警告を出して direct を維持する（`engine/src/program/generate.cpp:3446-3472, 6352-6383`、`engine/sycl/src/program/generate.cpp:1774-1797, 3375-3406`）。

`STRATA_PLE_PROBE` が設定済みなら計測用 `gather_batch` とこのブロック内のログ・自動切替を丸ごと省略する。従って `STRATA_PLE_AUTO_MMAP=1` もこの条件を迂回しない。明示的な `--ple-io` は CLI parser で `ple_io_explicit` に記録され、低速時の自動切替を抑える（`engine/src/program/generate.cpp:3901, 6362-6375`、`engine/sycl/src/program/generate.cpp:1940, 3385-3398`）。この変数単独による終了・エラー経路はない。

## ログと測定値

`STRATA_PLE_PROBE` 自体を示すログはない。設定すると、probe 分岐内の正常時 `strata generate: PLE direct read probe: %.0f rows/s (fine)`、低速時の `WARNING: --ple-io direct measures slow here ...`、または mmap 切替時の `using --ple-io mmap instead ...` は出ない。計測結果が 0 以下の場合は、変数 unset でもこの probe 分岐内のログは出ない。いずれも stderr への出力（`engine/src/program/generate.cpp:6354-6381`、`engine/sycl/src/program/generate.cpp:3377-3404`）。

## 根拠

- CUDA/HIP の PLE open、direct 判定、自動 RAM policy、probe の読み取りと結果分岐: `engine/src/program/generate.cpp:6264-6288, 6303-6348, 6350-6383`
- CUDA/HIP の probe 実装と計測上限・失敗時の戻り値: `engine/src/program/generate.cpp:3446-3472`
- CUDA/HIP の `--ple-io` 既定値と明示指定の記録: `engine/src/program/generate.cpp:817-819, 3901`
- SYCL の PLE open と probe の読み取り・結果分岐: `engine/sycl/src/program/generate.cpp:3346-3369, 3373-3406`
- SYCL の probe 実装と計測上限・失敗時の戻り値: `engine/sycl/src/program/generate.cpp:1774-1797`
- SYCL の `--ple-io` 既定値と明示指定の記録: `engine/sycl/src/program/generate.cpp:500-503, 1940`
- `terminal/data/settings-register.json` にも名前が登録されているが、これは設定レジストリ上の参照であり、実際の環境変数読み取り箇所は上記 2 箇所（`terminal/data/settings-register.json:34709-34725`）。
- `docs/DETAILS.md` は `--ple-io direct` の起動時 probe と `STRATA_PLE_AUTO_MMAP=1` による切替を説明するが、`STRATA_PLE_PROBE` による抑止は記載していない（`docs/DETAILS.md:1215`）。
