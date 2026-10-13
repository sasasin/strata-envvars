# `STRATA_GROUPED_V1`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

native 形式の grouped expert 計算で、旧方式の kernel launch 構成を選びます。旧方式は可能な各 group に block row を割り当て、SwiGLU と q8_1 量子化を別々の kernel で実行します。無効時は渡された `grid_groups` に合わせて group 軸の block row を減らし、通常の CUDA/SYCL 経路では SwiGLU と q8_1 量子化を一つの kernel にまとめます。ヘッダーはこの二方式の結果を bitwise 同一と説明しています（`native_grouped_parity` が検査する旨も記載）。

この設定が使われるのは `native_expert_grouped()` の経路です。呼び出し元には verifier と peer/remote expert 処理があります。量子化 expert 全般や、native grouped 経路を通らない計算を一律に切り替える設定ではありません。

## 値と判定

文字列の parse や数値変換は行わず、値が unset でなく、空文字でなく、先頭文字が `0` でない場合に有効です。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効 |
| `0`、`0abc` | 無効 |
| `1`、`true`、`false`、`2`、空白で始まる文字列など | 有効（先頭文字が `0` 以外で空でない場合） |

大文字小文字、文字列全体、後続文字は検査されません。環境変数は CUDA と SYCL の各 kernel 実装のグローバル初期化時に一度読みます。その初期化後にプロセス環境を変更しても値は更新されません。C++ API `native_grouped_set_v1(bool)` は内部値を変更できますが、製品コードでの呼び出しは確認できず、リポジトリ内の確認できる呼び出しは parity 用コードです。

根拠: `src/kernels/cuda/iq_kernels.cu:1951-1954,3445-3449`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2813-2816,5046-5050`; `include/strata/kernels/iq_kernels.hpp:74-77`。

## 有効になる条件

- `native_expert_grouped()` が呼ばれること。`cap_groups <= 0` または `cap_entries <= 0` なら関数は直ちに戻り、この変数による launch はありません。
- CUDA/HIP 実装では、`STRATA_EXPERT_V2` の先頭が `1` で、gate/up type 21、down type 20、`n_embd=2560`、`n_ff=640` の場合、または `STRATA_EXPERT_V2K` の先頭が `1` で gate/up type が 12/13、down type が 7/8、同じ shape の場合、先行する専用経路で return するため、この設定は使われません。SYCL 実装はこれらの AMD 専用設定を無視する旨をログに出します。
- `STRATA_GROUPED_V1` が無効でも、関数の `grid_groups <= 0` または `grid_groups > cap_groups` なら group 軸は `cap_groups` になります。したがって、ここでは有効/無効の差がありません。
- gfx906 HIP/SYCL 経路では `STRATA_HIP_SWIGLU_FUSED` との相互作用があります。`STRATA_GROUPED_V1` が有効なら、fused 設定にかかわらず旧来の二 kernel SwiGLU/q8_1 構成です。無効なら、`STRATA_HIP_SWIGLU_FUSED` が有効な場合に fused kernel、そうでなければ二 kernel 構成になります。

## 実行時の詳細

grouped 処理は gate/up の計算、SwiGLU と q8_1 への変換、down projection の順です。設定が有効な場合、gate/up と down の group 軸に `cap_groups` を使用し、SwiGLU を全 `cap_entries * n_ff` 要素に対して実行した後、別 kernel で q8_1 へ量子化します。設定が無効で `0 < grid_groups <= cap_groups` の場合、gate/up と down は `grid_groups` 分の block row を起動し、残りの group は block row が stride して処理します。SwiGLU と量子化は `swiglu_q8_1_entries_kernel` 一つで処理します。group count や entry 数が不足する分は kernel 内で処理対象外となります。

CUDA/HIP 実装では V2/V2K の早期 return 後に `g_grouped_v1` を参照し、通常の gate/up launch geometry と SwiGLU 経路、down launch geometry を選びます。CUDA の fused gate/up layout が選ばれる場合、gate/up launch 自体は専用 fused kernel になりますが、設定は SwiGLU と down 側には引き続き影響します。SYCL 実装も同じ `gy` と SwiGLU 分岐を使います。

設定による警告や設定専用ログは見つかりません。既定値では旧方式は無効です。性能上の効果は build、GPU、モデル、group 数、entry 数などに依存しますが、この調査では測定値を確認していません。`docs/DETAILS.md` にこの変数の説明や測定条件は見つかりませんでした。

## 根拠

- 値の読み取りと判定: `src/kernels/cuda/iq_kernels.cu:1951-1954,3445-3449`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2813-2816,5046-5050`。
- CUDA/HIP grouped 計算、早期 return、group 軸、SwiGLU 分岐、down launch: `src/kernels/cuda/iq_kernels.cu:3451-3456,3464-3495,3505-3525,3570-3579,3582-3585`。
- SYCL grouped 計算、group 軸、SwiGLU 分岐: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5052-5079,5136-5195`。
- gfx906 の fused SwiGLU 条件: `src/kernels/cuda/iq_kernels.cu:3565-3579`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5141-5195`。
- API の方式説明と同一結果の記述: `include/strata/kernels/iq_kernels.hpp:64-77`。
- 主な production 呼び出し元: `src/core/verify.cpp:1441,1582`; `src/core/peer_experts.cpp:240`; `src/core/remote_experts.cpp:318`; `sycl/src/core/remote_experts.cpp:431`。
