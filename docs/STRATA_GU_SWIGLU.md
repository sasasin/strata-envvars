# `STRATA_GU_SWIGLU`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

ルーティングされた expert の gate/up 行列積、SwiGLU 活性化、結果の q8_1 量子化を一つの CUDA/HIP カーネル起動で行う経路を選びます。通常経路では gate/up の中間値を書き出した後、SwiGLU と q8_1 量子化を別カーネルで実行します。この融合経路が使われた場合は `native_expert_grouped/gu+swiglu` のカーネル検査名が使われます。

環境変数は `src/kernels/cuda/iq_kernels.cu` の `gu_swiglu_on()` で評価され、結果は関数内の `static const int` に保存されます。初回評価後のプロセス環境変更は反映されません。

## 値と判定

値は `std::atoi` で整数に変換します。文字列全体の検証はなく、先頭の空白や符号の後にある10進整数接頭辞を変換し、整数値が0かどうかで判定します。空文字、数値に変換できない文字列、`0` で始まる整数接頭辞は無効です。`1`, `-1`, `2`, `1tail` は有効、`0`, `0tail`, `false`, 空文字は無効です。整数変換の範囲外の入力に対する扱いはコードで個別に定義されていません。

| 状態 | 判定 |
|---|---|
| 未設定、compute capability 12.0 の CUDA GPU で `STRATA_SM120_PERF` が有効 | 有効 |
| 未設定、それ以外の GPU、または HIP | 無効 |
| 明示設定 | `atoi` の結果が0以外なら有効、0なら無効。GPU 世代の既定値より優先 |
| SM 8.6 CUDA で起動時既定が適用され、ユーザーが未設定 | `STRATA_GU_SWIGLU=1` が設定され有効 |

compute capability 12.0 の既定は `strata::sm120_default()` によります。これは compute capability が12.0で、かつ `STRATA_SM120_PERF` が未設定または `atoi` の結果が0以外の場合に真です。したがって `STRATA_SM120_PERF=0` は未設定時の `STRATA_GU_SWIGLU` を無効にしますが、`STRATA_GU_SWIGLU` 自体を明示していればその明示値が優先されます。

## 有効になる条件

値判定が有効でも、融合カーネルは次の条件がそろう場合に限り実行されます。

- grouped expert の通常の gate/up 経路にあり、`g_exp_phase == 0`、`v1` が無効である。
- `STRATA_EXP_LAYOUTS` ビルドでは `em0 == 0` の配置である（融合済み `fused_gu` ではない）。このビルド設定がない場合はこの配置条件を使いません。
- `STRATA_EXPDEC` の経路がこのレイアウトで処理可能な場合に優先されていない。
- gate/up 型が `STRATA_GU_FMTS` の形式で、split 対応である。
- `g_old_kernels`、`split_off<TG>()`、`g_no_sub16_gu` が無効であり、`n_embd == 2560`、`n_ff > 0` かつ32の倍数である。
- その形式について `(n_embd / qk) * ipb == 80` が成り立つ。

したがって、変数が有効でも一般のモデル形状や全ての量子化形式で融合するわけではありません。`launch_gu_swiglu()` が条件に合わず `false` を返した場合は、後続の通常 gate/up と SwiGLU/量子化カーネルに進みます。HIP では変数未設定時の既定値は常に無効です。一方、明示設定は CUDA/HIP 共通の環境判定より先に処理されるため、明示値が有効なら HIP でも上記のカーネル条件を満たす経路で候補になります。

## 実行時の詳細

`native_expert_grouped()` は `gs_layout && g_exp_phase == 0 && !v1 && gu_swiglu_on()` を確認して fused kernel を試します。成功すると `native_gu_swiglu_kernel` が gate/up の dot を計算し、その場で SwiGLU を適用して q8_1 block を保存し、後続の個別 SwiGLU/量子化カーネルを省略します。失敗時や条件不一致時は通常の gate/up、`swiglu_entries_kernel`、`quantize_q8_1_kernel` 等にフォールバックします。通常の SwiGLU/量子化カーネルは `g_exp_phase` と Hadamard-folded down weights の状態に応じて選択されます。

未設定時の世代別既定値は次のとおりです。

- compute capability 12.0 の CUDA では、`STRATA_SM120_PERF` が無効でなければ `gu_swiglu_on()` が既定 ON と判定します。
- NVIDIA CUDA の起動処理では、全ての可視 CUDA device が同じ compute capability の場合に限り `apply_nv_defaults()` を呼びます。同一 compute capability が8.6で、`STRATA_SM86_PERF` の先頭文字が `0` でない場合（または未設定）に、環境へ `STRATA_GU_SWIGLU=1` を設定します。`STRATA_SM86_PERF=0anything` も既定セットを止めます。ユーザーが `STRATA_GU_SWIGLU` を設定済みなら、空文字や `0` を含めて上書きしません。
- その他の GPU では未設定時は OFF です。HIP の未設定時も OFF です。

compute capability 8.6 の既定値設定時には、設定した環境変数名を列挙する1行の stderr ログが出ます。明示設定時や compute capability 12.0 の `gu_swiglu_on()` 判定自体が出す専用ログは確認できません。Strata の `docs/DETAILS.md` は、RTX PRO 5000 (compute capability 12.0) の IQ3_S 測定でこのスイッチを含む構成を記載しています。これは記載条件の測定値であり、この変数単独の性能保証ではありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:4106-4128` — 値の読み取りとキャッシュ、未設定時の HIP / compute capability 12.0 分岐。
- `src/kernels/cuda/iq_kernels.cu:4130-4152` — split・モデル形状・行レイアウト条件と fused kernel 起動。
- `src/kernels/cuda/iq_kernels.cu:5149-5168,5207-5230` — grouped expert 経路での条件、検査名、通常経路への fallback。
- `src/kernels/cuda/iq_kernels.cu:2758-2765,2815-2825` — fused kernel の計算と量子化。
- `src/core/nv_defaults.cpp:12-15,18-35,52-68` — sm_86 の既定値、`STRATA_SM86_PERF` 判定、ユーザー設定の優先、stderr ログ。
- `src/program/generate.cpp:2800-2817` — CUDA 起動時に同一 compute capability の全 device 向けに既定値を適用。
- `include/strata/core/sm120_series.hpp:28-41` — `STRATA_SM120_PERF` と compute capability 12.0 の既定判定。
- `docs/DETAILS.md:2463-2482` — compute capability 12.0 の測定条件と当該スイッチの記述。
