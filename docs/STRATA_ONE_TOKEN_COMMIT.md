# `STRATA_ONE_TOKEN_COMMIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

検証窓が1 token のとき、GDN の convolution history と recurrent state をその窓の GPU 計算で確定させ、後続の `Verifier::commit()` が commit graph を起動しない経路を選びます。これによりこの条件下で commit graph を省略します。コード上、CUDA は既定で有効、HIP は opt-in、SYCL は既定で有効です。

## 値と判定

判定は `std::atoi()` の戻り値がゼロかどうかです。文字列全体の妥当性確認や範囲チェックはありません。`atoi` は先頭の空白と符号の後の数字列を読み、数字以降の文字は判定に使いません。数字が始まらない文字列と空文字は 0 になります。したがって `2junk` や `-1` は有効、`0junk`、`true`、空文字は無効です。大文字小文字は判定されません。

| ビルド | 未設定 | 設定値が有効となる条件 |
|---|---|---|
| CUDA（`src/core/verify.cpp` の非 HIP 分岐） | 有効 | `atoi(value) != 0` |
| HIP（同ファイルの HIP 分岐） | 無効 | `atoi(value) != 0` |
| SYCL（`sycl/src/core/verify.cpp`） | 有効 | `atoi(value) != 0` |

判定値は関数内の `static const bool` に保存されます。各実行ファイル内で初回に `one_token_self_commit()` が呼ばれた時点で一度評価され、そのプロセス内で後から環境を変更しても反映されません。

## 有効になる条件

- `record_window()` が受け取る窓の token 数 `T` が 1 であること。
- CUDA/HIP 実装では、さらに `always_publish_` が偽、`batch_rec_` が偽、`g_qfuse()` が偽であること。SYCL 実装の `record_window()` 側では `batch_rec_` と `g_qfuse()` が偽であること（この実装には `always_publish_` の条件がありません）。
- 環境変数のビルド別判定が有効であること。

この条件が満たされない場合、`record_window()` は自己 commit 用の引数を GDN convolution/recurrent kernels に渡しません。commit graph の省略条件は `Verifier::commit()` にも別途あります。CUDA/HIP では `last_t_ == 1 && !always_publish_ && one_token_self_commit()`、SYCL では `last_t_ == 1 && one_token_self_commit()` のとき省略します。二つの判定箇所の条件は同一ではないため、自己 commit 用 state 更新の条件と commit graph 省略の条件を混同できません。

## 実行時の詳細

`record_window()` は単一 token かつ上記条件を満たすと `self_commit` を true にし、GDN convolution kernel と recurrence kernel にその情報を渡します。CUDA/HIP では通常経路の `gdn_conv_l2_multi`（fused A/B projection 経路では `gdn_conv_ab_multi`）と `gdn_step_norm_multi` が対象です。SYCL では `gdn_conv_l2_multi` と `gdn_step_norm_multi` が対象です。各呼び出しは token 窓の計算時に state を確定するためのフラグ／出力先を受け取ります。

その後 `Verifier::commit()` は、上記の commit 側条件に一致すれば `commit_exec_` の graph launch を行わず、通常の commit graph 経路なら CUDA/HIP は `cudaGraphLaunch(commit_exec_, cs_)`、SYCL は queue の `ext_oneapi_graph(*commit_exec_)` を起動します。省略分岐専用のログ出力は確認できません。通常経路では commit graph launch 失敗時に `verify: commit launch: ...` をエラーとして返します。

環境変数を子プロセスへ渡す、または実行中に読み直す処理はこの実装箇所にはありません。

## 根拠

- `src/core/verify.cpp:277-291`: CUDA/HIP での値取得、既定値、`atoi` 判定。
- `src/core/verify.cpp:844`: CUDA/HIP 側 `record_window()` の自己 commit 条件。
- `src/core/verify.cpp:1139-1148,1162-1176`: GDN convolution と recurrence への自己 commit 情報の伝達。
- `src/core/verify.cpp:2497-2510`: CUDA/HIP 側 `Verifier::commit()` の graph 省略と通常 launch。
- `sycl/src/core/verify.cpp:191-201`: SYCL 側の値取得と既定値。
- `sycl/src/core/verify.cpp:824,1038-1063`: SYCL 側の自己 commit 条件と GDN kernel 呼び出し。
- `sycl/src/core/verify.cpp:2617-2629`: SYCL 側 `Verifier::commit()` の graph 省略と通常 launch。
- `docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。
