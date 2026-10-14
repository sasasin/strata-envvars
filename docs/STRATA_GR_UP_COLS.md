# `STRATA_GR_UP_COLS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 fused GR の multi-token up projection kernel で、1 work-group が処理する列数 `COLS` を選びます。既定の 16 列から 4、8、32、64 列へ変更できます。`COLS` が小さいときは起動 work-group 数が増え、大きいときは減ります。コードコメントでは、各行の dot、butterfly reduction、列ごとの stream sum の順序と出力が同じになる設計とされています。これは実装コメントの説明であり、ここでは別途測定・検証していません。

この名前を環境から読む実装は `sycl/src/kernels/cuda/fused_gr.dp.cpp` のみです。CUDA/HIP の `src/kernels/cuda/fused_gr.cu` には、この環境変数の読み取りはありません。したがって、変数が制御するのはこの SYCL port の経路です。

## 値と判定

値は `std::atoi` で整数に変換し、その結果が `4`, `8`, `32`, `64` のいずれかなら採用します。それ以外は既定の `UPM_COLS`（16）になります。文字列全体の数値検証はしません。

| 設定 | 選択される列数 |
|---|---:|
| 未設定 | 16 |
| `4`, `8`, `32`, `64` | 変換結果の値 |
| `16` | 16（無効値からの fallback） |
| 空文字、非数値、`0`、負値、その他の数値 | 16 |
| `8abc`, ` 8`, `+8` など | `atoi` が返す整数が候補値なら採用（この例では 8） |

たとえば `8.0` は `atoi` が先頭の整数部分 `8` を返すため 8 列です。先頭が数値でない文字列は通常 0 となり 16 列に fallback します。`atoi` が整数範囲外の値に対して返す値はC/C++仕様上保証されないため、その場合の選択は断定できません。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:670-673,840-843`。

## 有効になる条件

- `fused_gr_read_multi()` が通常の multi-token fused GR up-kernel を起動する経路で有効です。`launch_gr_up_multi()` が値を読み、`COLS` ごとのテンプレート kernel を起動します。
- `STRATA_GR_V3` による two-kernel 経路がデバイスの local memory 条件を満たす場合、関数は専用の `gr_up_v3_kernel` を起動して戻るため、この設定はその呼び出しでは参照されません。
- `STRATA_GR_MORE_GROUPS` が有効な経路では `launch_gr_up_more()` が up kernel を起動し、固定の `UPM_COLS_MORE`（8）を使います。この場合も `STRATA_GR_UP_COLS` は無視されます。同変数が未設定の場合、Alchemist 世代では `STRATA_GR_MORE_GROUPS` が既定で有効なため、`STRATA_GR_UP_COLS` を適用したい場合は `STRATA_GR_MORE_GROUPS=0` が必要です。
- `fused_gr_read()` が通常の単一 token kernel を直接使う経路ではこの値を読みません。一方、同関数が down-sliced / norm-split / down-direct 条件によって `fused_gr_read_multi(..., 1, ...)` に委譲する場合は、先述の multi-token 経路とその条件に従います。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:1770-1824,1881-1919,1956-1964,2038-2044,2061-2084`。

## 実行時の詳細

`gr_up_cols()` 内の `static const int` 初期化で環境変数を読みます。したがって値はプロセス内で最初にこの関数が実行されたときに決まり、以後の環境変更は反映されません。値はキューやデバイスごとに保持されず、この関数の static 値として共有されます。

選ばれた列数 `C` に対し、up kernel の work-group 数は `N / C`（`N=2560`）です。4、8、16、32、64 列ではそれぞれ 640、320、160、80、40 work-group になります。kernel は `gr_up_multi_kernel<C>` として起動されます。`gr_large_grf()` が有効な起動では 256-register GRF の variant が選ばれ、通常は `STRATA_GR_UP_ILP=1` による ILP variant または通常 variant が選ばれます。いずれも `COLS` の選択自体は共通です。

この環境変数専用のログ、警告、エラー出力は実装にありません。無効値は警告なしで 16 列になります。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:840-874,1770-1790,2038-2044`。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:840-843` — 環境変数の読み取り、`atoi`、許容値と fallback。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:849-874` — 列幅ごとの kernel 起動と work-group 数。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1770-1824,1881-1919` — multi-token 経路、別の v3 経路による早期 return。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2038-2044` — `STRATA_GR_MORE_GROUPS` が有効な場合の別 kernel dispatch。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2061-2084` — 単一 token の直接経路と multi-token への委譲。
