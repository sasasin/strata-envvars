# `STRATA_SHUTDOWN_TOKEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

デスクトップシェルが App Host に対して、UI 状態変更、正常終了、ウィンドウからのドロップファイル受け渡しを要求する際の共有秘密です。ホストはリクエストの `x-strata-shutdown` ヘッダーと環境変数を照合します。これは通常利用者が値を選ぶ設定ではなく、デスクトップアプリがプロセス間で渡すトークンです。

## 値と判定

| 状態 | ホストの判定 |
|---|---|
| 未設定 | `process.env.STRATA_SHUTDOWN_TOKEN ?? ''` により空文字となり、拒否 |
| 空文字 | 長さが 32 未満のため拒否 |
| 32 文字未満 | 拒否 |
| 32 文字以上 | ヘッダー値と文字列長が同じで、`timingSafeEqual` による Buffer 比較が一致したときだけ許可 |

数値や真偽値として parse せず、特定の固定文字列とも比較しません。ヘッダー照合は大文字小文字を区別します。ホストが受け取るアプリ生成値は 16 進文字列 64 文字です。Linux ウィンドウ子プロセス側では `std::env::var` で読み、環境変数が未設定または Unicode 文字列として取得できない場合は `unwrap_or_default()` により空文字を使います。

デスクトップ起動では親シェルが新しい値を生成して子プロセスへ明示設定するため、起動元の同名環境変数や CLI 引数による上書きはありません。手動で App Host を起動する場合は、そのプロセスに設定された値がそのまま照合対象になります。

## 有効になる条件

- Windows/macOS の埋め込みシェルは `host_command()` が生成値を Node App Host の環境へ設定します。Linux では supervisor が同じくホストへ設定し、ウィンドウ子プロセスにも設定します。
- Node 側の認証は、`POST /api/control/ui`、`POST /api/control/shutdown`、`POST /api/app/drop` で使われます。正しいトークンがなければ `403` と `Not allowed.` を返します。
- `/api/app/mode` はこの認証関数を使わず、`/api/app/quit` は別の `x-strata-client` ヘッダー有無で判定します。
- プロセスが起動し、対象ルートへリクエストが来た場合に適用されます。Node はリクエストごとに `process.env` を参照し、値を独自キャッシュしません。Linux の Rust ウィンドウ子プロセスは `run_window_process()` の開始時に一度読み、その後 updater bridge 登録などのリクエストヘッダーへ使います。

## 実行時の詳細

Windows/macOS の `start_host()` は `random_token()` を呼び、結果を `host_command()` に渡して App Host の `STRATA_SHUTDOWN_TOKEN` として設定します。Linux supervisor も起動ごとに `random_token()` を作り、ホストコマンドと `--window-child` の環境へ渡します。生成関数は `RandomState` のハッシュ値を4個連結した64桁の16進文字列を作ります。値はシェルの終了処理や Linux の session 情報にも保持され、シェルからホストへ送る `x-strata-shutdown` ヘッダーに載ります。

認証に失敗した場合、保護された各 POST は処理を進めず `403 Not allowed.` を返します。成功した `/api/control/shutdown` は `202 { stopping: true }` を返した後、非同期に `shutdown()` を呼びます。ホストは task を閉じ、サーバー接続を閉じ、共有・native・agent 等の停止処理を行って終了します。シェルの `--quit` は要求失敗を `[strata] could not ask Strata to stop (...)` と stderr に出して終了コード 1 を返し、成功時は停止を待ちます。終了処理が期限内に完了しない場合はシェル側の終了処理がホストを kill します。

トークンが未設定・不一致のとき、それ自体について専用の警告ログはありません。応答は HTTP 403 です。別のシェル内 HTTP helper は非 200/202 応答をエラー文字列として扱います。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:200-215` — Windows/macOS のトークン状態と64桁16進値の生成。
- `apps/desktop/src-tauri/src/main.rs:442-492,497-505` — App Host コマンドへの環境変数設定、起動時の生成と保持。
- `apps/desktop/src-tauri/src/main.rs:544-588` — 保持したトークンを `x-strata-shutdown` に付ける正常終了要求と timeout 後の kill。
- `apps/desktop/src-tauri/src/main.rs:1134-1143,1165-1179` — Linux ウィンドウ子プロセスの読み取りと updater 登録ヘッダー。
- `apps/desktop/src-tauri/src/supervisor.rs:104-123,155-173,229-239,241-264,341-383,390-399` — Linux session への保持、ヘッダー送信、ホストとウィンドウ子プロセスへの設定、`--quit` の結果処理。
- `apps/host/server/index.mjs:1305-1310,1319-1342` — Node ホストの値読み取り・比較、認証対象ルート、拒否と正常終了応答。
- `apps/host/server/index.mjs:2268-2287` — ホストの正常終了処理と終了期限。
