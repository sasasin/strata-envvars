# `STRATA_HIP_SWIGLU_FUSED`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

AMD gfx906 互換ビルドの grouped expert カーネルで、SwiGLU の計算と結果の Q8_1 量子化を1つのカーネルにまとめるかを選びます。有効時は gate/up の出力から SwiGLU 値を計算し、Q8_1 ブロックへ直接書き込みます。無効時は SwiGLU と Q8_1 量子化を別々のカーネルで実行します。

## 値と判定

`env_on()` は値が存在し、空文字でなく、先頭文字が `0` でない場合に true を返します。文字列全体や数値としての妥当性は調べません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`、`0abc` | 無効 |
| `1`、`true`、`2abc`、先頭が空白の値 | 有効 |

CUDA/HIP 実装と SYCL ポートの `env_on()` は同じ判定です。変数の判定値は関数内の `static const bool` に保存されます。初期化は gate/up と SwiGLU の処理が行われ、この分岐に初めて到達した時点で一度だけ実行されます。その後の環境変更は反映されません。

## 有効になる条件

- ビルドで `STRATA_HIP_GFX906` が定義されている必要があります。CMake では `STRATA_HIP_GFX906` オプションが gfx906 向け HIP 互換ビルドを構成し、この macro を定義します。通常の CUDA、wave32 AMD HIP (`STRATA_ENABLE_HIP`)、その他のビルドでは、この変数を読む分岐がコンパイルされません。
- `native_expert_grouped()` が gate/up と SwiGLU の処理を実行する必要があります。`g_exp_phase == 2` では gate/up 側をスキップするため、この設定は使われません。
- `STRATA_GROUPED_V1` または `native_grouped_set_v1(true)` によって grouped v1 が選ばれている場合は、環境変数が有効でも2段階の方式が使われます。コードは `sw_v1 = v1 || !sw_fused` と判定します。

## 実行時の詳細

`native_expert_grouped()` の `STRATA_HIP_GFX906` 分岐で環境変数を一度判定し、grouped v1 が無効かつ本変数が有効なら `swiglu_q8_1_entries_kernel` を起動します。このカーネルは実際に呼び出された expert entry 範囲について gate と up から SwiGLU 値を計算し、その値を Q8_1 形式へ格納します。

それ以外の場合は `swiglu_entries_kernel` で SwiGLU 値を中間バッファへ書き、続けて `quantize_q8_1_kernel` で Q8_1 に変換します。実装コメントは統合版の結果を別々のカーネルと bitwise 同一と説明しています。環境変数専用のログ出力はありません。カーネル起動後は共通の `check("native_expert_grouped/swiglu")` が実行されます。

CUDA/HIP 実装と SYCL ポートの両方に同じ環境変数分岐があります。SYCL 側も `STRATA_HIP_GFX906` 条件で分岐し、統合版では1つの `parallel_for`、従来版では2つの `parallel_for` を起動します。`docs/DETAILS.md` にこの環境変数の説明や、この切り替えの測定値は見つかりませんでした。この調査では実機で parity や性能を測定していません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:2128-2131` — 値の存在、空文字、先頭文字による `env_on()` 判定。
- `src/kernels/cuda/iq_kernels.cu:3641-3646,3771-3787` — grouped expert 呼び出し、gfx906 条件、`STRATA_GROUPED_V1` との優先関係、統合版と2段階版の起動。
- `src/kernels/cuda/iq_kernels.cu:1461-1467,1677-1708` — 個別の SwiGLU・量子化処理と、両方をまとめるカーネル。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3014-3017,5276-5285,5371-5429` — SYCL ポートでの同じ値判定と起動分岐。
- `CMakeLists.txt:64-70,128-144` — gfx906 互換ビルドの設定と `STRATA_HIP_GFX906` macro の定義。
