# `STRATA_ROUTE_TAIL_RENORM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

partial-residency の verify window で、`STRATA_ROUTE_TAIL_SKIP` が落とす missed expert の routing weight をゼロにし、同じ token row に残った routing weight を元の合計に戻す opt-in です。Router の expert ID や skip rank 自体は変更しません。残る expert への重みが変わるため、expert の出力と後段の結果は変わり得ます。`Verifier::record_window` が CUDA/HIP kernel を起動します（`engine/src/core/verify.cpp:2681-2684`、kernel の契約は `engine/include/strata/kernels/verify_kernels.hpp:148-152`）。

## 値と判定

`route_tail_renorm_env_on` は null でない文字列に `std::atoi` を適用し、結果が 0 以外なら有効とします（`engine/include/strata/core/device_hits_plan.hpp:29-31`）。文字列全体の検証はありません。したがって、未設定と空文字は無効、`1`・`-1`・`+1`・`1tail` は有効、`0`・`0anything`・`true`・`false`・空白だけは無効です。先頭空白は `atoi` の変換対象として無視されます。数値の後ろは判定されず、大文字小文字も比較しません。整数として表現できない入力の結果は、この実装から保証できません。

| ビルド経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP | 無効 | `atoi` の結果が非ゼロ（例: `1`, `-1`, `1tail`） | `atoi` の結果がゼロ（例: 空文字, `0`, `0anything`, `true`） |
| Metal (`STRATA_GPU_METAL`) | 常に無効 | なし | すべて |
| SYCL | この環境変数を読む参照が SYCL 実装にない | なし | 適用なし |

## 有効になる条件

- 対象は CUDA/HIP の verify window です。Metal build では `tail_renorm_env` が compile-time false です（`engine/src/core/verify.cpp:1533-1536`）。CUDA/HIP kernel の宣言は両 backend 向けで、共通 GPU engine の kernel source に `verify_kernels.cu` が含まれます（`engine/include/strata/kernels/verify_kernels.hpp:148-152`、`engine/cmake/strata_gpu_engine.cmake:93-107`）。SYCL の別実装には対象名の読み取りも処理もありません。
- 環境変数が有効に parse されても、実行時には `!ar_on()`、`!batch_rec_`、`remote_opt_ == nullptr`、`hits_.d_res != nullptr`、および `tail_skip_rank() > 0` がすべて必要です（`engine/src/core/verify.cpp:2681-2684`）。条件に合わない window はこの処理を飛ばします。
- `STRATA_ROUTE_TAIL_SKIP` は連携する別の環境変数です。unset は rank 0、1〜9 はその rank、それ以外は 0 になり、正の rank がないと再正規化は実行されません（`engine/include/strata/core/tail_skip_default.hpp:11-20`、`engine/src/core/expert_source.cpp:5416-5424`）。
- 対象変数を上書きする専用 CLI 引数や別設定の読み取りは、このソース範囲では見つかりません。環境変数の判定結果が使われます。

## 実行時の詳細

`Verifier::record_window` 内の関数ローカル `static const bool` として、最初の window 記録時に `getenv` と `atoi` で一度だけ読みます。その後プロセス内で環境を変更しても判定は更新されません（`engine/src/core/verify.cpp:1468-1469,1533-1537`）。Metal は同じ箇所で環境を読まず常に false です。

条件がそろうと、layer/group の routing ID・weight と residency table を使う kernel を expert plan より前に起動します（`engine/src/core/verify.cpp:2681-2697`）。kernel は各 missed expert（`res_layer[e] < 0`）について、window 内でその expert が現れる最小 rank を調べます。最小 rank が `tail_rank` 以上なら、その expert の該当 weight を skip 対象にします。各 token row では元の weight 合計と skip 後の合計を計算し、skip 後の合計が正かつ元の合計より小さい場合、skip 対象を 0 にして残りを `orig_sum / kept_sum` 倍します。それ以外は row の weight を変更しません（`engine/src/kernels/cuda/verify_kernels.cu:1703-1749`）。

## ログと測定値

有効化や正常実行を知らせる専用ログはありません。kernel の入力 entry 数が `kResidentPlanMax` を超える場合、stderr に `route_tail_renorm: %d entries, at most %d` を出して `exit(1)` します（`engine/src/kernels/cuda/verify_kernels.cu:1868-1879`）。CUDA/HIP の kernel error があれば共通 `check` が stderr に `route_tail_renorm: <エラー文字列>` を出して `exit(1)` します（`engine/src/kernels/cuda/verify_kernels.cu:37-40,1880-1884`）。この変数の測定値は該当資料に見つかりません。

## 根拠

- 候補名の直接読み取り: `engine/src/core/verify.cpp:1536`。値判定 helper: `engine/include/strata/core/device_hits_plan.hpp:29-31`。
- 適用条件と起動位置: `engine/src/core/verify.cpp:2681-2697`。
- 重みの skip 判定と再正規化: `engine/include/strata/kernels/verify_kernels.hpp:148-152`、`engine/src/kernels/cuda/verify_kernels.cu:1703-1749`。
- 連携する skip rank の既定・範囲・cache: `engine/include/strata/core/tail_skip_default.hpp:11-20`、`engine/src/core/expert_source.cpp:5411-5424`。
- backend 条件: `engine/src/core/verify.cpp:1533-1537`、`engine/metal/CMakeLists.txt:93`、`engine/cmake/strata_gpu_engine.cmake:93-107`。
