# `DF2B_VARIANTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版 `dflash2_bench gemm` が測定する DF2 Q4 GEMM variant の ID 一覧を指定します。通常の Strata 実行経路が読む設定ではなく、CMake target `dflash2_bench` の GEMM ベンチマーク専用です。指定した ID ごとに `fc`、`qkv(3)` などの形状を各列数で計測し、variant ID と時間・帯域を表に出します。target の定義は `sycl/CMakeLists.txt:437-438`、モード選択は `sycl/src/kernels/dflash2_bench.cpp:894-901` です。

## 値と判定

環境変数の値は `std::getenv` で直接読み、設定されていればカンマ区切りで走査して各要素を `std::atoi` に渡します。文字列全体の検証や空要素の除外はありません。

| 値 | 結果 |
|---|---|
| 未設定 | 既定 ID `28, 12, 40, 41, 42, 43` を計測します。 |
| 空文字 | 設定済みとして扱われますが走査要素がなく、variant 列は 0 件です。既定値には戻りません。 |
| 数値列 | カンマまでの各部分を `atoi` で整数化します。例: `10,12` は ID 10 と 12。 |
| 空要素・非数値 | `atoi` の変換結果を使うため、先頭要素が数値として読めない場合は 0 になります。例: `,12` は 0 と 12、`abc` は 0。 |
| 数字の後ろに文字 | `atoi` が先頭の数値部分を返します。例: `12junk` は 12。 |
| 末尾カンマ | 最後のカンマの後ろは空のため要素になりません。 |

先頭・末尾の空白等は `atoi` の規則に委ねられ、ベンチマーク側でエラーや警告を出して値を拒否する処理はありません。格納先は `int vs[16]` で要素数を検査しないため、空でない要素が 16 個を超える値は配列外書き込みになります（その場合の動作は定義されません）。読み取りと配列への格納は `sycl/src/kernels/dflash2_bench.cpp:634-636` です。

## 有効になる条件

- `dflash2_bench` を `gemm` モードで実行したときだけ読み取られます。引数なしまたは他のモードでは `run_gemm_bench()` に入らず、この変数による variant 一覧は使いません（`sycl/src/kernels/dflash2_bench.cpp:894-901`）。
- SYCL の `dflash2_bench` target がビルドされ、GPU queue の生成に成功している必要があります。queue はモード判定より前に生成されます（同 `:898-901`）。OS や Strata のサーバーモードによる条件分岐はこの参照箇所にはありません。
- dispatcher が実装する ID は `10, 11, 12, 17, 24, 25, 28, 34, 40, 41, 42, 43` です。これ以外の ID はエラーにならず、GEMM dispatcher の `default` 分岐で ID 28 の実装に落ちます（`sycl/src/kernels/cuda/dflash2.dp.cpp:718-732`）。
- ID 0 は `g_gemm_variant` を 0 にするため、明示的な variant 固定値としては扱われません。その GEMM 呼び出しでは `STRATA_DF2_GEMM4` が非 0 ならその値、そうでなければ `DF2_Q4_AUTO(rows)` が選ばれます。したがって `DF2B_VARIANTS=0` の出力列は ID 0 でも、実測カーネルが ID 0 を表すわけではありません（同 `:716-718`）。

## 実行時の詳細

`run_gemm_bench()` に入ると `DF2B_VARIANTS` を一度読み、配列に得た ID ごとに `df2_gemm_variant(vs[i])` を設定して、列数 8、4、1 の各計測を行います。計測は各形状で 200 回の back-to-back launch です（`sycl/src/kernels/dflash2_bench.cpp:614-616,634-662`）。variant setter はベンチマーク用のグローバル値を更新し、GEMM dispatcher がそれを選択に使います（`sycl/src/kernels/cuda/dflash2.dp.cpp:37,702-718,735`）。

環境変数は `run_gemm_bench()` 内で一度だけ読み、その後再読込・cache 更新する処理はありません。値は表の列数と各列で設定する dispatcher variant に反映されます。`std::printf` により device 名、variant 列見出し、各形状の時間・帯域が標準出力に出ます（`sycl/src/kernels/dflash2_bench.cpp:631,638-665`）。空文字の場合もエラーにはならず、列見出しに variant は並ばず、各形状で variant を設定して計測する内側ループも実行されません。

この一覧は各 GEMM 計測の間 `STRATA_DF2_GEMM4` より優先されます（ただし ID 0 の場合を除く）。一覧計測後は `df2_gemm_variant(0)` で override を解除します（`sycl/src/kernels/dflash2_bench.cpp:654-670`）。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:634-636` — 直接読み取り、区切り走査、`atoi`、未設定時の既定 ID。
- `sycl/src/kernels/dflash2_bench.cpp:614-616,638-662` — GEMM ベンチマーク内での用途、出力、計測回数。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — CLI モードによる実行経路と SYCL queue 初期化。
- `sycl/src/kernels/cuda/dflash2.dp.cpp:37,702-718,735` — setter の状態と `STRATA_DF2_GEMM4`・自動選択との優先順位、および未知 ID の fallback。
- `sycl/CMakeLists.txt:437-438` — `dflash2_bench` 実行ファイル target。
