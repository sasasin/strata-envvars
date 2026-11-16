# `STRATA_PRIVATE_GR_LO_VEC4`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 版 fused GR の「low-order part から up projection を行う」処理で、2〜4 token の場合に専用の vec4 kernel を選ぶ private switch である。設定が無効、または 1 token の場合はこの専用 kernel を選ばず、通常の `GrUpFromLo` kernel に進む。切り替わるのは計算 kernel であり、生成 token や上位の選択結果を変える設定ではない。環境変数の判定は `gr_lo_vec4_enabled()`、kernel 選択は `launch_gr_up_from_lo()` にある（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2366-2369,2521-2526`）。

## 値と判定

`std::getenv` で値を取得し、値が存在して `std::atoi(value) != 0` の場合だけ有効とする。文字列全体の数値妥当性は検査しない。未設定と空文字は無効。`atoi` の規則により先頭空白と符号は許され、数値部分の後ろは無視される。したがって `1`、`-1`、`2tail` は有効、`0`、`0tail`、`true`、`false`、`tail`、空文字は無効になる。数値に変換できない先頭（例 `tail`）は `atoi` の結果が 0 となる。値の取得結果は関数内 `static const bool` に一度保存される（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2366-2369`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| SYCL `gr_lo_vec4_enabled()` を含む build | `false` | `1`, `-1`, `2tail` | 空文字, `0`, `0tail`, `true`, `tail` |

## 有効になる条件

- SYCL backend の `fused_gr_read_multi()` 経由で、低ランク結果から up projection を行う `launch_gr_up_from_lo()` に到達する必要がある。`fused_gr_read()` は `kDownXnTooBig || gr_down_sliced() || gr_norm_split() || gr_down_direct()` のとき multi-token 実装へ転送する（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3510-3533`）。
- `STRATA_PRIVATE_GR_F32_REG` も `atoi` で非ゼロになり、`gf_enabled()` の条件を満たす必要がある。条件は `m.T` が 1〜4、down projection が sliced、more-groups と large-GRF 経路でない、norm split、有効な up columns が 16、up ILP 無効、Intel GPU 世代が Battlemage であること（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689,3465-3470`）。
- `STRATA_PRIVATE_GR_SILU_FROM_LO` も非ゼロである必要がある。up-phase の GF kernel を選ばない場合に、同変数の有効化が `launch_gr_up_from_lo()` への経路を開く（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532,3469-3470`）。
- `STRATA_PRIVATE_GR_F32_PHASE` が未設定、`both`、または `up` の場合は `gf_phase("up")` が真になり、先行する `gf_dispatch_up()` が vec4 分岐より優先される。vec4 分岐に到達するにはこの判定が偽である必要がある。通常の down GF 経路も使う設定は `down`（`gf_phase()` は完全一致で比較する）である（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693,3369-3370,3468-3470`）。
- token 数は 2〜4 が必要。1 token では専用 kernel に切り替わらない（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2521-2526`）。
- 4 token で `STRATA_PRIVATE_GR_UP_ROWS16` が `'1'` から始まる値で有効、かつ B60 layout と main actor の条件も満たす場合は、先に `gf_dispatch_up()` が選ばれ、この vec4 kernel は選ばれない（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2517,2521-2524`）。

## 実行時の詳細

初回に `gr_lo_vec4_enabled()` が評価された時点で環境値を読み、以降はプロセス内の static 値を使う。実行中に環境を書き換えても、この判定値には反映されない。読み取り自体は起動時ではなく、この関数の初回呼び出し時である（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2366-2369`）。

有効条件を満たす 2〜4 token の呼び出しでは、`launch_gr_up_lo_vec4()` が `GrUpLoVec4` SYCL kernel を投入する。kernel は低ランク値を vec4 配置の local storage に移し、up weight と組み合わせて dot/reduction を行い、gate 値を token ごとに reduction して mixed output を書き込む。条件を満たさないときは `GrUpFromLo` kernel が投入される（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2245-2268,2331-2362,2370-2374,2521-2526`）。

## ログと測定値

この変数の判定や kernel 選択に伴う専用ログ、警告、終了処理は見つからない。SYCL queue の kernel 投入時に例外が発生した場合の一般的な経路は、この環境変数に固有の処理ではないため、本書では記載しない。`docs/` にこの switch の設計説明や条件付き測定値は見つからず、性能差は確認できない。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2366-2369` — 環境変数の唯一のコード読み取り箇所と static cache。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2245-2362,2370-2374` — 専用 kernel と launch。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2517-2526,2529-2532,2690-2693` — token 数、rows16 と phase の選択順、および low-part 経路。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689,3365-3392,3465-3470` — GF 経路の条件と down/reduce/up の呼び出し。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:3510-3533` — single-token API から multi-token 実装へ入る条件。
