# `STRATA_PRIVATE_GR_F32_REG`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の fused GR (`fused_gr_read_multi`) で、Battlemage 向けの private ESIMD FP32 down/up kernel を選べるようにする opt-in 変数。通常の down/up kernel を、FP32 の SIMD/FMA 計算を使う `gf_*` 経路に置き換える。変数が有効でも、GPU 世代や GR の設定条件を満たさない場合は通常経路を使う。CUDA/HIP 実装でこの変数を読む箇所はない。`gf_enabled` の値判定と適用条件は `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`、kernel dispatch は同ファイルの `sycl/src/kernels/cuda/fused_gr.dp.cpp:3365-3389` と `sycl/src/kernels/cuda/fused_gr.dp.cpp:3465-3470`。

## 値と判定

初回の `gf_enabled` 呼び出しで `std::getenv` の結果を `std::atoi(s) != 0` に変換し、関数内 `static` に保存する。未設定と空文字はいずれも無効。`atoi` は文字列全体の真偽値比較ではなく整数変換であり、数値の後ろは検査されない。したがって `1`、`-1`、`1anything` は有効、`0`、`0anything`、`true`、`false`、空文字、数値に変換できない文字列は無効になる。先頭の空白や符号は `atoi` の整数変換規則に従う。変換可能な整数の範囲検査や fallback は実装していない。根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2688`。

| 条件（SYCL build） | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `STRATA_PRIVATE_GR_F32_REG` | 無効 | `1`, `-1`, `1anything` | 空文字, `0`, `0anything`, `true`, `false`, `abc` |

## 有効になる条件

`STRATA_PRIVATE_GR_F32_REG` が有効でも、すべて次の条件を満たすときだけ `gf_enabled` が true になる: token 数 `m.T` が 1〜4、`STRATA_GR_DOWN_SLICED` が unset または `atoi` 非ゼロ、`STRATA_GR_MORE_GROUPS` と `STRATA_GR_LARGE_GRF` が false、`STRATA_GR_NORM_SPLIT` が unset または `atoi` 非ゼロ、`STRATA_GR_UP_COLS` の有効値が 16、`STRATA_GR_UP_ILP` が `1` で始まらず、device 世代が `Battlemage`。これらの helper の既定値と判定は `sycl/src/kernels/cuda/fused_gr.dp.cpp:812-836`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:1203-1210`、対象 gate は `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`。

- phase は別変数 `STRATA_PRIVATE_GR_F32_PHASE` で選ぶ。unset または文字列全体が `both` なら down/up 両方、`down` または `up` なら一致する phase のみ。比較は大文字小文字を区別し、その他の値（空文字を含む）はどちらにも一致しない。phase は `gf_phase` の呼び出しごとに `getenv` される（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693`）。
- `STRATA_PRIVATE_GR_SILU_FROM_LO` は down 選択後の reduce / up-from-lo 経路に関わる。これが有効なら、phase が down だけでも GR の reduce と up-from-lo を使う分岐がある（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3388-3394`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3465-3470`）。
- `STRATA_PRIVATE_GR_SOA_CACHE` が有効で、`b60_main_actor()` も true の場合、1/2/4 token では指定された measured control combination を要求し、条件不一致なら例外になる。down kernel の選択も SOA 経路に変わる（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3160-3166`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3095-3115`）。`STRATA_PRIVATE_GR_2D_PAIR` は4 token の down dispatch に関与し、`STRATA_PRIVATE_GR_UP_ROWS16` は B60 layout / main actor 条件下で4 token の up compute を変える（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2764`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2517-2526`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3103-3118`）。
- fused GR API 自体が呼び出されない経路では効果がない。呼び出し元は SYCL の verify / MTP 経路など（例: `sycl/src/core/verify.cpp:1150`、`sycl/src/core/mtp.cpp:948`）。この環境変数に対する CLI 優先順位や別設定からの上書きは実装されていない。

## 実行時の詳細

`fused_gr_read_multi` は token 数を 1〜`kFusedGrMaxT`（8）に制限し、範囲外や null scratch では `stderr` に `fused_gr_read_multi: invalid arguments` を出して `exit(1)` する（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3142-3145`、`include/strata/kernels/fused_gr.hpp:70`）。`gf_enabled` gate 自体が許可するのは 1〜4 token だけである。引数ポインタ等の検査を通ったあと `gf_enabled` が真で phase に `down` が含まれると `gf_dispatch_down` を選び、それ以外は通常の sliced down kernel に進む。reduce は phase に `up` が含まれるか `STRATA_PRIVATE_GR_SILU_FROM_LO` が有効な場合に `gf_reduce_silu` を使う。up は phase に `up` が含まれれば `gf_dispatch_up`、そうでなく SiLU-from-lo が有効なら `launch_gr_up_from_lo`、それ以外は通常経路を使う（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3167`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3365-3410`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:3465-3493`）。

対象変数の判定は最初の `gf_enabled` 呼び出しで process-local に一度 cache され、実行中に環境を書き換えても再評価されない。phase は `gf_phase` 呼び出しごとに読み直される。`gf_down` は sliced activation と down/inject weights を読み FP32 SIMD FMA で部分和を作り（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2594-2629`）、`gf_up` は low-rank 値と up weights から FP32 SIMD FMA/XOR reduction で `xn` を更新する（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2550-2592`）。この経路の数値同一性や性能は、この調査では測定していない。

## ログと測定値

この変数の読み取り・有効化・無効化を知らせるログはない。fused GR の入力不正時は「実行時の詳細」に記した文字列を出して終了する。SOA cache 経路で必要な設定の組合せが満たされない場合は `B60 GR cache requires the measured GR control combination`、decode cache がない場合は `B60 missing GR decode cache` の `std::logic_error` が投げられる（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3160-3166`）。性能測定値は記載しない。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2693` — 対象値の parse/cache と phase の読み取り。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3167` — API 入力検証と SOA cache 条件。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:3365-3410,3465-3500` — down/reduce/up の dispatch と fallback。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2550-2629` — FP32 up/down kernel。
