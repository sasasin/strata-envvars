# `STRATA_DENSE_I8_TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。調査開始時の Strata の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

CUDA の native MMVQ decode / speculative verify において、条件を満たす dense projection を INT8 Tensor Core kernel `dense_i8_tc_mmvq` に切り替える機能を無効化するスイッチです。未設定・空文字・`atoi` の結果が 0 になる値では、GPU 対応状況が許せばこの経路を有効にします。値が有効でも、出力幅・列数・量子化型・GPU 条件が合わなければ通常の native MMVQ 経路を使います（`engine/src/kernels/cuda/dense_i8_tc.cu:1712-1719`、`engine/src/kernels/cuda/native_mmvq.cu:3775-3805`）。

この変数は prompt prefill の切り替えには使われません。prefill 側は別の `STRATA_PREFILL_DENSE_I8_TC` を読みます（`engine/src/kernels/cuda/dense_i8_tc.cu:1722-1729`）。

Strata の `docs/SETTINGS.md` はこの変数を「NVIDIA and AMD」と分類していますが、調査対象 commit の実装では HIP の `current_cc()` が 0 を返すため、この decode kernel は AMD/HIP では有効になりません（`docs/SETTINGS.md:54`、`engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`）。

## 値と判定

`dense_i8_tc_decode_enabled()` の関数内 `static` 初期化で `std::getenv` を一度呼び、未設定または空文字なら未指定扱い、その他は `std::atoi` を適用し、結果が 0 以外なら有効とします。文字列全体の妥当性検証や `true` / `false` の特別扱い、大文字小文字の判定はありません。`atoi` は先頭の空白と符号の後の数字列を変換し、数字列の後ろは判定しません。したがって `1x` や ` 1` は有効、`0anything`、`true`、`false`、数字で始まらない非空文字列は無効です。負の非ゼロ数も有効です（`engine/src/kernels/cuda/dense_i8_tc.cu:1712-1719`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_DENSE_I8_TC` の判定 | GPU が対応していれば有効 | `1`, `-1`, `1x`, ` 1` | `0`, `0anything`, `true`, `false`, `x`, 空文字 |

## 有効になる条件

- CUDA 実行であること。HIP コンパイル時の `current_cc()` は 0 を返すため、この機能は有効になりません（`engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`）。CMake の GPU kernel library には CUDA kernel と native MMVQ が登録されています（`engine/cmake/strata_gpu_engine.cmake:69-103`）。
- 現在の CUDA device の compute capability が 7.5 以上であること。device/API の問い合わせ失敗時は 0 を返し、機能は無効になります（`engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`）。
- `native_mmvq` に渡る出力幅 `n_out` が 1024 以上で、列数 `ncols` が `STRATA_DENSE_I8_TC_MIN_T` 以上かつ 16 以下であること。同変数の未設定・空文字時の閾値は実装上 9 です。非空値は `atoi` 後に最低 1 へ clamp されます（`engine/src/kernels/cuda/native_mmvq.cu:3767-3773,3780-3782`）。
- 重み型が Q8_0、Q2_K、Q3_K、Q4_K、Q5_K、Q6_K、IQ3_XXS、IQ4_NL、IQ3_S、IQ4_XS のいずれかであること（`engine/src/kernels/cuda/dense_i8_tc.cu:1705-1709`）。
- kernel 側でポインターが非 null、`T` が 1..16、`n_in` と `n_out` が正で、型に応じた `n_in` のアラインメントを満たすこと。Q8_0 と IQ4_NL は 32、それ以外の対応型は 256 の倍数が必要です（`engine/src/kernels/cuda/dense_i8_tc.cu:1732-1738`）。
- native interleaved MMVQ が先に選ばれる形状でも、`g_tune_rows == 0` かつ同じ幅・列数・型・有効条件に合えば `native_mmvq_il_supported()` が false を返して interleave kernel を見送り、通常の `native_mmvq()` に送ります（`engine/src/kernels/cuda/native_mmvq.cu:4218-4234`）。

## 実行時の詳細

環境値は `dense_i8_tc_decode_enabled()` が初めて呼ばれたときに static cache されます。プロセス実行中に環境を変更しても、そのプロセスでは再評価されません。GPU 対応性はその関数の呼び出しごとに確認されます（`engine/src/kernels/cuda/dense_i8_tc.cu:1712-1719`）。

対象条件を満たすと `native_mmvq()` は `dense_i8_tc_mmvq()` を呼びます。呼び出しが kernel launch に成功すれば dispatch を記録して戻り、失敗（型・shape・alignment 等の検査不通過や `cudaGetLastError()` 不成功）なら通常の native MMVQ の型別 kernel に進みます。`ncols > 16` などゲート条件を外れる場合も既存経路へ進みます（`engine/src/kernels/cuda/native_mmvq.cu:3775-3805`、`engine/src/kernels/cuda/dense_i8_tc.cu:1732-1767`）。

対象変数を参照する Strata の実装は `dense_i8_tc.cu` の decode 判定 1 箇所です。`native_mmvq.cu` の分岐と interleaved 経路はこの判定関数を呼びます。CLI 引数や設定ファイルから値を上書きする処理は確認できません。別の `STRATA_DENSE_I8_TC_MIN_T` は対象経路の列数閾値だけを変え、対象変数の `atoi` 結果が 0 なら経路全体を無効化します（`engine/src/kernels/cuda/native_mmvq.cu:3767-3782`）。

## ログと測定値

この変数の有効・無効や fallback 理由を直接表示するログ、警告、エラー出力は該当分岐にありません。カーネル成功時には内部の `strata::dispatch::kernel(..., 30, ...)` が呼ばれます（`engine/src/kernels/cuda/native_mmvq.cu:3782-3785`）。この調査では build・GPU 実行・性能測定を行っていません。

## 根拠

- `engine/src/kernels/cuda/dense_i8_tc.cu:1683-1719` — GPU capability と対象変数の値判定。
- `engine/src/kernels/cuda/dense_i8_tc.cu:1732-1767` — decode kernel の受け付け条件、launch とエラー判定。
- `engine/src/kernels/cuda/native_mmvq.cu:3767-3805` — 閾値、decode 経路の選択、既存 kernel への fallback。
- `engine/src/kernels/cuda/native_mmvq.cu:4218-4234` — interleaved MMVQ からの振り分け。
- `engine/cmake/strata_gpu_engine.cmake:69-103` — CUDA/native kernel の build 登録。

