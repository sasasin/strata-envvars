# `STRATA_SHUTDOWN_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

App Host の制御 API で、シェルまたは Linux のウィンドウ子プロセスからの要求を認証する共有値です。`/api/control/ui`（アップデータ bridge の登録、ブラウザーへの切替、ページを開く）、`/api/control/shutdown`（ホストの正常終了）、`/api/app/drop`（アプリウィンドウからのファイル受け渡し）の POST は、`x-strata-shutdown` ヘッダーがこの値と一致しない場合に拒否されます（`app/host/server/index.mjs:1438-1473`）。通常のデスクトップ起動では Rust のシェルが token を生成し、ホストと Linux のウィンドウ子プロセスに渡すため、利用者が起動前に指定する動作設定ではありません（`app/desktop/src-tauri/src/main.rs:243-255,503-540,554-560`; `app/desktop/src-tauri/src/supervisor.rs:503-555`）。

## 値と判定

ホスト側は文字列の値を parse せず、保護対象 API の要求ごとに `process.env.STRATA_SHUTDOWN_TOKEN ?? ''` を読みます。値の JavaScript `length` が 32 未満なら、ヘッダー照合に進まず認証失敗です。32 以上なら `sameSecret` がヘッダー値と token の両方を SHA-256 でハッシュして比較します。空でない文字列同士だけが一致し、空白除去・大文字小文字変換・数値や真偽値への変換はありません（`app/host/server/index.mjs:1438-1441`; `app/host/server/util.mjs:27-35`）。

| 実行経路 | unset | 認証に使われる値 | 認証に使われない値 |
|---|---|---|---|
| デスクトップが起動した App Host | 通常起動では該当しない。シェルが生成した token を `.env(...)` で設定する | シェルが渡した token（Rust の生成値は 64 桁の小文字 16 進文字列） | 呼び出し元環境にあった値は、ホスト起動時にシェルが上書きする。32 文字未満ならホスト側の長さ条件も満たさない |
| 単独起動など、ホスト起動側で値を渡さない場合 | `''` として扱い、常に認証失敗 | 32 文字以上で、要求ヘッダーが同じ文字列のとき | 空文字、31 文字以下、またはヘッダーと異なる文字列 |
| Linux `--window-child` | Rust 側では `std::env::var(...).unwrap_or_default()` により空文字 | 起動時に取得した値を `x-strata-shutdown` ヘッダーへ付ける | 値が空でも起動時にエラーにはならないが、ホストが要求を認証しない |

ホストの長さ条件は UTF-16 コード単位による JavaScript の `.length` です。たとえば ASCII の 31 文字は無効、32 文字は照合対象です。空白や `true`、`1` なども特別扱いせず、32 文字未満なら無効、32 文字以上ならヘッダーとの完全一致だけで判定されます。Rust の `random_token()` は 4 個の 16 桁小文字 16 進文字列を連結します（`app/desktop/src-tauri/src/main.rs:243-255`）。

## 有効になる条件

- ホストで認証されるには、対象 API が POST であり、実行中ホストの環境値が 32 文字以上で、`x-strata-shutdown` ヘッダーと一致する必要があります。条件を満たさないと対象ルートは HTTP 403 と `Not allowed.` を返します（`app/host/server/index.mjs:1438-1473`）。
- デスクトップアプリは起動時に token を生成してホストの環境へ設定します。Linux では同じ token を `--window-child` にも渡します。Linux のウィンドウ子プロセスは updater bridge 登録とファイル受け渡しでこのヘッダーを使います（`app/desktop/src-tauri/src/main.rs:503-540,1295-1302,1335-1349`; `app/desktop/src-tauri/src/supervisor.rs:503-555`）。
- ホストの認証対象は `/api/control/ui`、`/api/control/shutdown`、`/api/app/drop` の各 POST です。`/api/app/quit` は別の `x-strata-client` ヘッダーを検査し、この token を使いません（`app/host/server/index.mjs:1443-1473`）。
- デスクトップ以外のホスト起動でこの環境値を渡さない場合、認証付きの上記 API は成功しません。Strata のコードには、一般 CLI オプションや設定ファイルから token を補う処理はありません。

## 実行時の詳細

Rust シェルは起動ごとに token を生成します。Windows/macOS の `start_host` と Linux の `supervisor::run` は `host_command` を使い、子ホストの `STRATA_SHUTDOWN_TOKEN` を設定します。したがって親プロセスから同名の値を継承してもデスクトップホストでは置き換えられます（`app/desktop/src-tauri/src/main.rs:243-255,503-540,554-560`; `app/desktop/src-tauri/src/supervisor.rs:503-527`）。Linux のウィンドウ子プロセスは `run_window_process` の開始時に一度読み、updater 登録や drop 要求に使います。親がいない updater 再起動経路では `restart_after_update` が元の環境を復元できない場合、この変数を含む窓口用環境値を削除します（`app/desktop/src-tauri/src/main.rs:1295-1302,1335-1349`; `app/desktop/src-tauri/src/supervisor.rs:332-367,390-400`）。

ホスト側は token をモジュール初期化時にキャッシュせず、`fromShell` が呼ばれるたびに `process.env` から読みます（`app/host/server/index.mjs:1438-1441,1451-1473`）。認証済みの shutdown 要求は HTTP 202 を返してから終了処理を開始します。終了処理はタスクを閉じ、チャット保存を drain し、サーバー接続と各サービスを閉じてプロセスを終了します（`app/host/server/index.mjs:1462-1467,2578-2590`）。

## ログと測定値

この変数について専用の診断ログや測定値はありません。認証失敗は対象 API が HTTP 403 と `Not allowed.` を返します。認証成功時は shutdown で HTTP 202 と `{ stopping: true }` を返した後に終了処理へ進みます（`app/host/server/index.mjs:1451-1473`）。

## 根拠

- `app/desktop/src-tauri/src/main.rs:243-255,501-540,554-568,1295-1302,1335-1349` — token 生成、ホストへの設定、Linux 子ウィンドウの読み取りと要求ヘッダー。
- `app/desktop/src-tauri/src/supervisor.rs:332-367,390-400,503-555` — Linux の起動・子プロセスへの転送と updater 再起動時の環境整理。
- `app/host/server/index.mjs:1438-1473,2578-2590` — リクエストごとの認証、保護対象ルート、正常終了処理。
- `app/host/server/util.mjs:27-35` — secret 比較の入力条件と比較方法。
