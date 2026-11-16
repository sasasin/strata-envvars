# `STRATA_PRIVATE_GR_SILU_FROM_LO`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の fused hyper-connection read にある private Battlemage 実験経路で、down の reduce カーネルが low-rank 値に SiLU を適用して `lo` に書き、その値を up 段階で使う経路の条件の一つです。これだけではカーネルを有効にせず、後述の `STRATA_PRIVATE_GR_F32_REG` などの条件も必要です。`STRATA_PRIVATE_GR_F32_PHASE` が未設定または `both` のときは up phase 自体が有効なため reduce の SiLU カーネルが選ばれ、この変数が選択を変えるのは主に `down` phase の場合です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532,2685-2693,3388-3395,3465-3470`）。

通常の設定向け変数ではなく、SYCL ソース内の private 実験用スイッチです。同名の CUDA/HIP/Metal 読み取りは見つかりません。SYCL の fused GR 実装ファイルがビルド対象です（`sycl/CMakeLists.txt:42`）。

## 値と判定

関数内 `static const bool` の初期化ラムダで `std::getenv` の結果を `std::atoi` に渡し、戻り値が 0 以外なら有効とします（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL 実装 | `false` | `1`、`-1`、` 1`、`1tail`（`atoi` の結果が非 0） | 空文字、`0`、`0tail`、`true`、`false`、数値で始まらない文字列 |

文字列全体の妥当性、範囲、大文字小文字は検査しません。`atoi` の数値変換規則に従うため、先頭の空白と符号は数値として扱われ、数値の後ろに文字があっても変換結果を使います。数値変換できない文字列と明示的な空文字は 0 です。値の CLI 引数による上書き・優先順位はありません。

## 有効になる条件

- SYCL バックエンドの `fused_gr_read_multi()` が呼ばれる必要があります。この判定は SYCL 実装にのみあります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3141,3510-3533`）。
- 実際に `gf_reduce_silu` と実験 up 経路へ進むには、別変数 `STRATA_PRIVATE_GR_F32_REG` が非 0で、token 数が 1〜4、`STRATA_GR_DOWN_SLICED` と `STRATA_GR_NORM_SPLIT` が有効、`STRATA_GR_MORE_GROUPS` と `STRATA_GR_LARGE_GRF` が無効、`STRATA_GR_UP_COLS` が既定の 16、`STRATA_GR_UP_ILP` が無効で、GPU 世代が Battlemage である必要があります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`）。
- F32 実験経路で down 側を実行するには `STRATA_PRIVATE_GR_F32_PHASE` が未設定、`both`、または `down` である必要があります。up を同時に実行するかどうかもこの変数で別途判定します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693,3365-3370,3388-3392`）。
- 一部の up 実装では、さらに `STRATA_PRIVATE_GR_UP_ROWS16` が先頭文字 `1` で始まり、Battlemage layout と main actor の条件を満たす必要があります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2517-2526,3469-3470`）。
- 別の SoA cache 経路を有効にしたとき、token 数が 1、2、4 のいずれかなら、この変数を含む制御組合せが要求されます。組合せが合わない場合は `std::logic_error("B60 GR cache requires the measured GR control combination")` が送出されます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969,3160-3166`）。
- 特殊な T=1 Q8 up 経路には加えて `STRATA_PRIVATE_GR_Q8_UP32`、Battlemage layout、`q8_mixed` があり、down phase が有効で up phase が無効である必要があります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2386,3465-3468`）。

## 実行時の詳細

`gr_combo_silu_enabled()` が最初に呼ばれた時点で環境を一度読み、結果を関数ローカル static に保存します。その後の `fused_gr_read_multi()` 呼び出しでは同じ値を使い、実行中に環境を書き換えても反映されません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532`）。

有効条件を満たす down-sliced 経路では、reduce が down の部分和を合計し、low-rank 行ごとに `x / HC` を計算して `value / (1 + exp(-value))` を `lo` に保存します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2644-2655,3385-3395`）。`STRATA_PRIVATE_GR_F32_PHASE=down` ならこの変数が有効な場合に同じ `lo` を使う `launch_gr_up_from_lo()` 経路が選ばれます。phase が未設定または `both` なら up phase 判定で `gf_dispatch_up()` が選ばれるため、この変数はその経路選択を変えません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693,3465-3470`）。

条件を満たさないとき、この変数だけを理由に通常経路が失敗することはありません。該当する private 分岐が選ばれず、通常の reduce/up 分岐へ進みます。ただし SoA cache 経路を明示的に使い、要求される組合せが不足した場合は前節の例外になります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3160-3166,3388-3410,3465-3493`）。

T=1 の特殊 Q8 分岐まで条件が揃うと、`q8_mixed` 画像もその up カーネルが書き、`fused_gr_read_multi()` は `true` を返します。それ以外は `false` を返すため、verify 側は通常の `native_quantize_q8_1()` を実行します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3465-3470,3499-3500`; `sycl/src/core/verify.cpp:1811-1814,1859-1862`）。

## ログと測定値

この変数の値を報告する専用ログはありません。SoA cache 経路で要求される制御条件が不足した場合は、前述の文字列を持つ `std::logic_error` が発生します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3160-3166`）。この環境変数に紐づく条件付き測定値はソースで確認できません。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532` — 対象環境変数の唯一の実読み取りと static cache。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2644-2655,2685-2693,3365-3395,3465-3500` — 適用条件、reduce/up の分岐、戻り値。
- `sycl/src/core/verify.cpp:1811-1814,1859-1862` — Q8 画像を使う呼び出し側と fallback quantize。
- `sycl/CMakeLists.txt:42` — SYCL ビルド対象。
