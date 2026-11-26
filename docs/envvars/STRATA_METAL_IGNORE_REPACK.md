# `STRATA_METAL_IGNORE_REPACK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査対象 checkout は `## main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

## 役割

Metal decode window の初期化時、モデル shard の隣でモデル repack または setup のモデル準備が実行中と検出された場合に、初期化を拒否する安全確認を `=1` で通過させます。変数はモデル準備処理を停止・待機させず、検出された状況でも Metal engine を初期化しようとする選択を表します。読み取りと拒否分岐は `Window::init`、ロック検出は `repack_pid_running` にあります（`engine/metal/src/engine/window.cpp:692-710,714-736`）。

## 値と判定

`Window::init` は、モデル shard の隣に有効な準備ロックが見つかったときだけ `std::getenv` で値を調べ、値全体を文字列 `"1"` と比較します。存在するかどうかだけの判定や数値変換ではありません。大文字小文字を区別し、空白除去・数値 parse・接頭辞比較も行いません（`engine/metal/src/engine/window.cpp:731-735`）。

| 条件 | unset | 判定を通過する値 | 判定を通過しない値 |
|---|---|---|---|
| `Window::init` で有効な準備ロック PID を検出 | 起動拒否 | `1` のみ | 空文字、`0`、`true`、`false`、`01`、`1anything`、` 1`、`1 `、`TRUE` など |

有効なロックを検出しない場合、この変数は読み取られず、設定値に関係なくこの拒否分岐には入りません。既定値は実質 unset と同じで、別の CLI 引数・設定ファイル・環境変数による値の置換や優先順位はこの判定にはありません。モデル shard のパスは `g_shard1` から渡され、ロックを探すディレクトリを決めます（`engine/metal/src/engine/window.cpp:700-710,731-735,3627-3633`）。

## 有効になる条件

- Apple 向け Metal build の経路であること。Metal エンジンの CMake は Apple 以外で構成を拒否し、`Verifier::init` は `STRATA_GPU_METAL` build の分岐から Metal window を初期化します（`engine/metal/CMakeLists.txt:1-2,18-20`; `engine/src/core/verify.cpp:978-985`）。
- `Window::init` に到達し、モデル geometry がその build の対応条件を満たすこと。geometry 不一致時は環境変数の判定より先にエラーで戻ります（`engine/metal/src/engine/window.cpp:714-735`）。
- shard と同じディレクトリに `.preparing.lock` または末尾が `.repack.lock` のファイルがあり、その先頭から PID を `%ld` で読み取れて、PID が正数・自プロセス以外で、`kill(pid, 0)` が成功するか `errno == EPERM` であること。この条件を満たすロックが見つかった場合に限り、`=1` が拒否を解除します。ロックが読めない、PID が不正・終了済み・自プロセスの場合は拒否条件になりません（`engine/metal/src/engine/window.cpp:697-710`）。
- 値の判定は `Window::init` ごとです。ただし `window_init` は既に window が ready なら `Window::init` を再実行しません。したがって、初期化完了後に環境を変更しても、同じ ready window の状態は変わりません（`engine/metal/src/engine/window.cpp:3627-3638`）。

## 実行時の詳細

Metal verifier の初期化から `window_init` に入り、window が未初期化なら `Window::init` を呼びます。初期化は geometry の検査後、モデルファイルを開く前に隣接ディレクトリのロックを走査します（`engine/src/core/verify.cpp:978-985`; `engine/metal/src/engine/window.cpp:714-736,3627-3635`）。

ロックが有効で値が厳密に `1` でなければ、`Window::init` は `err` に `metal window: a model repack or setup's preparation is running here (pid <PID>): the engine is not started beside it (it froze a 128 GB Mac twice); wait for it to finish, or set STRATA_METAL_IGNORE_REPACK=1` を設定し、`false` を返します。値が `1` ならこの拒否だけを迂回して次の `f_.open(shard1, err)` に進みます。ファイルオープンや後続の Metal 初期化が成功する保証はこの変数にはありません（`engine/metal/src/engine/window.cpp:731-737`）。

値は固定の起動時キャッシュには保存されず、該当する初期化分岐で直接読み取られます。環境変数を確認する独立した helper や子プロセスへの転送処理はありません（`engine/metal/src/engine/window.cpp:731-735`）。

## ログと測定値

この分岐自体はログを出力せず、エラー文字列を呼び出し元へ返して初期化を失敗させます。ロックが見つからない場合や `=1` で拒否を解除した場合、この分岐からのログはありません（`engine/metal/src/engine/window.cpp:731-735`; `engine/src/core/verify.cpp:984`）。測定値は該当しません。

## 根拠

- `engine/metal/src/engine/window.cpp:692-710` — 隣接ロックファイルの名前、PID 読み取り、有効 PID の判定。
- `engine/metal/src/engine/window.cpp:714-737` — geometry 判定、環境変数比較、拒否エラーと後続のモデル open。
- `engine/metal/src/engine/window.cpp:3627-3638` — 未初期化 window に対する初期化呼び出しと ready 状態の扱い。
- `engine/src/core/verify.cpp:978-985` — Metal build の verifier 初期化経路。
- `engine/metal/CMakeLists.txt:1-2,18-20` — Metal build の Apple 限定。
