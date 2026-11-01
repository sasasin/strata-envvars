# `STRATA_SHELL_BRIDGE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で未コミット変更なし。

## 役割

デスクトップシェルが App Host に渡す、シェル内 loopback bridge の URL です。App Host はこの URL と対になる `STRATA_SHELL_TOKEN` を使い、デスクトップアプリのアップデーターやシェル通知へ HTTP 要求を送ります。Strata 自身が bridge listener を `127.0.0.1` の空きポートで開き、その URL を子プロセス環境に設定します。通常の推論エンジンやモデル設定を制御する変数ではありません。

## 値と判定

Rust 側では `STRATA_SHELL_BRIDGE` を読みません。bridge の起動に成功した場合だけ、生成した `http://127.0.0.1:<port>` を App Host 子プロセスの環境に設定します。起動に失敗した場合は URL を設定せず、アプリ内アップデーターは利用できません（Windows/macOS の Host 起動経路）。

Node 側の `createAppUpdater` と `createShellNotifier` は、値を文字列として変換せず、`STRATA_SHELL_TOKEN` とともに判定します。両方が truthy で、URL 全体が `^http://127\.0\.0\.1:\d+$` に一致した場合だけクライアントを作ります。

| 値 | Strata 側の扱い |
|---|---|
| 未設定または空文字 | falsy のためクライアントを作らない。通常の子 Host 起動時は、bridge が起動できなければ Rust もこの変数を設定しない。 |
| `http://127.0.0.1:<数字>` | token も truthy ならクライアントを作る。ポートは正規表現上、1 桁以上の数字であれば一致する。 |
| `http://localhost:<port>`、別ホスト、HTTPS、末尾 `/`、パス付き、空白入り | 正規表現に一致せずクライアントを作らない。 |
| その他の非空文字列 | URL parse や数値変換をせず、完全一致しない限り使わない。 |

この判定自体に CLI 引数や設定ファイルとの優先順位はありません。Windows/macOS のシェル起動経路では `Command::env` が生成 URL で同名の既存環境値を上書きします。環境を明示的に消去する処理はなく、bridge がない場合は通常の子プロセス環境継承の対象です。Node の `createAppUpdater` にはポート範囲検査がないため、正規表現に合っても接続できない URL は要求時に失敗し得ます。

## 有効になる条件

- Windows/macOS のデスクトップシェルは App Host コマンドを起動する際、listener の起動に成功したとき `STRATA_SHELL_BRIDGE` と `STRATA_SHELL_TOKEN` を設定します。Host はそれを updater と notifier の作成に使います。
- Linux では `run_window_process` が別プロセスで bridge listener を起動し、Host の `/api/control/ui` に URL/token を POST します。Host の `app-ui.mjs` はこの通知から updater を作るため、アップデーター登録は環境変数とは別経路です。`shell-prefs.mjs` の notifier は起動時の `process.env` から作られるため、この API 登録だけでは notifier に bridge は入りません。さらに Rust の `/shell/notify` は Linux では `shown: false` を返します。
- Host を手動起動する場合など、環境から受け取った値を利用するには、URL が上記の loopback 形式で token も空でない必要があります。
- `app-ui.mjs` の `setBridge` で後から登録する updater は、同じ URL 形式に加えて token が文字列で16文字以上であることを要求します。通常の起動時 `createAppUpdater` にはこの長さ検査はありません。

## 実行時の詳細

Windows/macOS の `start_host` は listener を開始し、成功時の `Bridge.url` を `apply_env` で Host 子プロセスへ渡します。`createAppUi` の初期化時に `createAppUpdater` が環境を読み、URL/token をクロージャに保持します。後から Linux ウィンドウプロセスが `/api/control/ui` で bridge を登録する場合は、`setBridge` が受け取った値から別の updater を作り、現在の updater として優先します。プロセス環境を再読み込みする処理はありません。

アップデーターは明示的な更新確認・インストール時だけ bridge の `/app-update/check`、`/app-update/install`、`/app-update/status` に要求します。HTTP 応答が成功でなければ応答 JSON の `error`、または状態コードを含むエラーになります。インストール処理の失敗は status の `error` として Host に返ります。Host 起動時に変数が無効なら updater がなく、UI は「アプリ更新不可」として扱います。

通知では `createShellNotifier` が同じ URL/token を使って `/shell/notify` を呼びます。HTTP 要求や応答 JSON の取得が失敗した場合は通知結果を `shown: false` として返し、Host の `/api/shell/notify` も例外を捕捉して `shown: false` を返します。bridge は認証 token の不一致に `401 Unauthorized`、未対応 route に `404 Not Found` を返します。

## 根拠

- `apps/desktop/src-tauri/src/updater.rs:227-240,243-250` — loopback の空きポートで listener を開き、bridge が存在する場合に子プロセス環境へ URL/token を設定。
- `apps/desktop/src-tauri/src/main.rs:497-505` — Windows/macOS の Host 起動時に bridge を作り、環境へ適用。
- `apps/desktop/src-tauri/src/main.rs:1165-1178` — Linux の別ウィンドウプロセスが bridge 情報を `/api/control/ui` に登録。
- `apps/host/server/app-updater.mjs:13-22,24-40` — bridge URL/token の判定、値の保持、HTTP 要求と失敗判定。
- `apps/host/server/app-ui.mjs:63-90` — 起動時 updater の作成、動的 bridge 登録の検証と置き換え。
- `apps/host/server/shell-prefs.mjs:64-75` — notifier の起動時判定、通知要求と失敗時の結果。
- `apps/host/server/index.mjs:128-143,1319-1328,1958-1962` — Host 起動時の notifier 作成、shell bridge 登録、通知 API の応答。
- `apps/desktop/src-tauri/src/updater.rs:174-224` — bridge の認証、update/status/notify route の応答。Linux 通知は `shown` を false にする。
