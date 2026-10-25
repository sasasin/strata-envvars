# `STRATA_IQ_STAGE_GRID_MMVQ`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

単一行列の IQ MMVQ カーネルで、i-quant の codebook grid を block/work-group 内の共有メモリへコピーして使うかを選びます。既定では無効です。有効にすると、対応する型の新しい multi-column MMVQ 経路が grid を共有メモリに stage します。無効時は grid の共有メモリ staging を行わず、既存の grid 配列を使います。

このスイッチは `STRATA_IQ_STAGE_GRID` が有効な場合に限り意味を持ちます。後者は別途、grouped expert の gate/up カーネルでも staging を制御しますが、この変数自体は単一行列 MMVQ の選択用です。

## 値と判定

値は文字列全体でなく先頭文字だけで判定されます。初期化時に `STRATA_IQ_STAGE_GRID` が有効と判定された場合だけ、この変数を読みます。

| `STRATA_IQ_STAGE_GRID` の判定 | `STRATA_IQ_STAGE_GRID_MMVQ` | MMVQ staging |
|---|---|---|
| 無効（先頭文字が `0`） | 任意、読み取りも行わない | 無効 |
| 有効 | unset、空文字 | 無効 |
| 有効 | 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| 有効 | その他（例: `0`, `true`, ` 1`） | 無効 |

`STRATA_IQ_STAGE_GRID` は unset または空文字なら有効、値の先頭文字が `0` なら無効、それ以外なら有効です。したがってこの親変数を unset のままにし、`STRATA_IQ_STAGE_GRID_MMVQ=1` を設定すれば MMVQ staging が有効になります。親変数を `0` または `0anything` にすると、子変数を `1` にしても無効です。

## 有効になる条件

- ビルドに CUDA または SYCL の IQ カーネル実装が含まれていること。CUDA 実装は `src/kernels/cuda/iq_kernels.cu`、SYCL はその移植版 `sycl/src/kernels/cuda/iq_kernels.dp.cpp` です。
- `iq_mmvq()` が呼ばれ、新しい multi-column カーネルが選ばれること。`STRATA_OLD_IQ_MMVQ` が有効だと旧 `mmvq_kernel` が選ばれ、この staging 分岐を通りません。
- 型が compile-time staging 対象の `IQ2_XXS` (16)、`IQ2_XS` (17)、`IQ2_S` (22)、`IQ1_M` (29) であること。他の型では staging されません。
- 対象変数の判定結果は `STRATA_IQ_STAGE_GRID` の判定結果との AND です。親スイッチが無効なら本変数を設定しても有効になりません。

Grouped expert kernels は `g_stage_grid` を参照し、この MMVQ 専用変数を参照しません。そのため、本変数だけで grouped expert kernels の staging を有効化することはありません。

## 実行時の詳細

両変数はカーネル翻訳単位のグローバル変数初期化時に一度評価され、結果が `g_stage_grid` と `g_stage_grid_mmvq` に保持されます。実行中に環境を書き換えても再評価されません。`g_stage_grid` が false の場合、C++ の `&&` 短絡評価により本変数の `getenv()` は呼ばれません。

対象型で staging が有効な場合、`launch_mmvq()` は `mmvq_multi_kernel<..., true>` を起動します。カーネルは IQ2_XXS / IQ2_XS / IQ2_S / IQ1_M に対応する grid 配列を block 内の共有領域へロードし、同期後にその領域を参照します。staging が無効なら同じ multi-column 経路を `<..., false>` で起動し、grid の共有領域コピーを省略します。各形式で staging する要素数はコード上で定義されています（256、512、1024、1024 個の `uint2`）。SYCL 移植版も同様に work-group local memory へロードして barrier します。

この環境変数による専用ログや警告は実装にありません。カーネルのコメントは staged/unstaged の出力は bitwise 同一としています。CUDA ソースのコメントには、RTX 5070 で IQ2_XS / IQ2_S / IQ1_M の 3–8 列 MMVQ が staging 時に 10–20% 遅かったという `iq_multi_parity --bench` の結果を、既定無効にした理由として記録しています。ただし、そのコメントには反復数などの測定条件が記載されていないため、一般的な性能差とはみなせません。`docs/DETAILS.md` に本変数固有の測定説明は見当たりません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:1958-1969`: 親・対象変数の読み取り、既定値、先頭文字判定。
- `src/kernels/cuda/iq_kernels.cu:663-666,716-717,742-743,836-837`: staging 対象型と型名。
- `src/kernels/cuda/iq_kernels.cu:1120-1155,1167-1173`: 型ごとの grid コピー、共有領域サイズ、MMVQ カーネル。
- `src/kernels/cuda/iq_kernels.cu:1988-2002,2736-2747`: 旧カーネルとの選択と MMVQ の呼び出し。
- `src/kernels/cuda/iq_kernels.cu:2672-2683`: grouped expert の gate/up は親変数を参照し、対象変数を参照しない。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2825-2836,1461-1523,3087-3095`: SYCL 移植版の判定と MMVQ staging。
- `CMakeLists.txt:345-377`: CUDA 側のソース一覧に `iq_kernels.cu` が含まれる。`sycl/CMakeLists.txt:1-10` は CUDA ソースの移植版を SYCL ビルドで使う構成を説明する。
- `docs/DETAILS.md`: IQ カーネルの説明はあるが、本変数を直接説明する記述はない。
