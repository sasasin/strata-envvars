# `STRATA_FUSE_CONVAB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP で GDN の畳み込み・L2 norm と alpha/beta 投影を同じ GPU kernel launch にまとめる、開発・性能調整用の opt-in 変数です。GDN の speculative VERIFY 経路で使われます。通常は `gdn_conv_l2_multi()` と `gdn_ab_multi()` の別々の呼び出しを行いますが、有効時は `gdn_conv_ab_multi()` に置き換えます。QKV 投影など、それ以外の処理はこの変数では融合しません。

## 値と判定

`src/core/verify.cpp` で `std::getenv()` と `std::atoi()` を使い、結果が 0 以外なら有効とします。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数字で始まらない文字列 | `atoi` が 0 を返すため無効 |
| `0`、`0abc`、`-0` | 無効 |
| `1`、`-1`、`2abc`、`  +2tail` | 先頭の整数変換結果が非ゼロのため有効 |

`atoi` は先頭の空白と符号を許し、数字列の後ろにある文字は変換時に読み飛ばします。したがって `2abc` も有効です。小数や真偽値の語としては解釈せず、たとえば `1.0` は整数部分が 1 なので有効、`true` は 0 なので無効です。境界外の整数に対する `atoi` の動作は文書化された設定値として扱えません。

判定は関数内の `static const bool` に保存されます。プロセス内で最初に `fuse_convab_on()` が呼ばれた後に環境を書き換えても再評価されません。

## 有効になる条件

- HIP バックエンドであること。`STRATA_USE_HIP` が定義されている場合だけ環境変数を読みます。CUDA など HIP 以外のビルドでは関数が常に `false` を返します。
- GDN 層の VERIFY 処理に入ること。QSA 層ではこの分岐を通りません。
- VERIFY の分岐条件 `!br && !batch_rec_ && !prof_on_` を満たすこと。branch 経路、batch recurrence、profiler が有効な場合は、変数が有効値でも融合しません。

コード上は GPU 世代による追加の実行時判定をしていません。注釈に gfx1201 の測定値はありますが、gfx1201 専用の機能ゲートはありません。

## 実行時の詳細

VERIFY の GDN 処理では、先に `mm(wqkv, ...)` で QKV 投影を行います。その後 `fuse_ab` が真なら `gdn_conv_ab_multi()` を呼び、従来の `gdn_conv_l2_multi()` と `gdn_ab_multi()` の個別呼び出しを省略します。結合 kernel は grid 内の block を使い分け、畳み込み・L2 norm と a/b 投影を同じ launch で実行します。計算後は後続の GDN recurrence に進みます。

`gdn_conv_ab_multi()` は引数の null、channel 数、token 数、commit 条件などを検査します。不正な引数なら stderr に `gdn_conv_ab_multi: invalid arguments` を出して `exit(1)` します。通常の GPU kernel 実行エラーは `check("gdn_conv_ab_multi")` に渡されます。この環境変数専用の有効化ログは見当たりません。

## 文書・測定値

`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。ソースコメントには「gfx1201 で -0.3% を測定」とありますが、同コメントにはモデル、測定条件、回数などが示されていません。この値はソースコメントにある記述としてのみ扱い、一般的な性能差や他環境での結果とはみなしません。

## 根拠

- `src/core/verify.cpp:249-257`: HIP 限定の `getenv` / `atoi` 判定と static cache。
- `src/core/verify.cpp:1116-1127,1140-1157`: VERIFY の GDN 処理、融合条件、融合・通常経路の選択。
- `src/kernels/cuda/verify_kernels.cu:151-167,942-964`: 1 launch にまとめる kernel と launcher、引数検査・エラー処理。
- `include/strata/kernels/verify_kernels.hpp:23-35`: kernel API と VERIFY token window の上限（`kVerifyMaxT = 8`）。
- `CMakeLists.txt:292-294,334-376,472-478`、`cmake/hip_backend.cmake:85-100`: GPU backend の対象ソースと HIP compile definition。
