# `STRATA_SHELL_BRIDGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata Desktop の Rust shell が App Host に渡す、shell 側 loopback bridge の URL です。Host の `app-updater.mjs` はこの値と対になる `STRATA_SHELL_TOKEN` を使って Tauri updater の確認・インストール API を呼びます。`shell-prefs.mjs` も同じ bridge を使って shell 通知を試みます。これは利用者が任意の機能を切り替える設定ではなく、shell が作成した bridge の接続先を Host に渡す内部値です。通常の Terminal やソース checkout では shell が bridge を渡さないため、アプリ自身の更新機能は利用できません（`app/desktop/src-tauri/src/updater.rs:1-14,441-464`、`app/host/server/app-updater.mjs:1-10,19-22`、`app/host/server/shell-prefs.mjs:66-77`）。

## 値と判定

Strata 内で数値や真偽値への変換はしません。App Host の updater と通知 helper は、渡された `env` オブジェクトから bridge と token を読み、両方が JavaScript の truthy 値で、bridge が `/^http:\/\/127\.0\.0\.1:\d+$/` に完全一致するときだけ client を作ります（`app/host/server/app-updater.mjs:19-28`、`app/host/server/shell-prefs.mjs:66-70`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `createAppUpdater` / `createShellNotifier` の `env` | bridge または token がない場合は client を作らない | `http://127.0.0.1:5555` と、空でない token | 空文字、`http://localhost:5555`、`http://[::1]:5555`、末尾 `/`、port なし、空 token |
| Linux window process から `setBridge` で登録 | 登録前は bridge 未設定 | URL は同じ loopback 形式、token は文字列かつ 16 文字以上 | URL 不一致、token が文字列でない、15 文字以下。`setBridge` は `That is not a bridge address.` を投げる |

URL の正規表現は port を数字列としてしか確認せず、数値範囲や URL 全体を別途 parse しません。環境値経由では token の長さや文字種も検査せず、truthy かどうかだけです。Desktop shell は空き port で listener を開き、`127.0.0.1:<port>` を作り、random token とともに host へ渡すため、通常のアプリ起動ではこの内部生成値が使われます（`app/desktop/src-tauri/src/updater.rs:443-454,457-464`、`app/host/server/app-ui.mjs:29,91-95`）。

## 有効になる条件

- updater が動くには `STRATA_SHELL_TOKEN` も必要です。Host は token を `Authorization: Bearer ...` に設定し、shell bridge は一致しない・欠けた認証値に `401 Unauthorized` と `not allowed` を返します（`app/host/server/app-updater.mjs:20-24`、`app/desktop/src-tauri/src/updater.rs:389-398`）。
- Windows/macOS の Desktop は Host の起動コマンドへ bridge URL と token を設定します。listener の bind または port 取得に失敗した場合 `start` は `None` を返し、2つの値を Host に設定しません（`app/desktop/src-tauri/src/main.rs:554-568`、`app/desktop/src-tauri/src/updater.rs:441-464`）。
- Linux では shell が updater bridge を開き、Host の `/api/control/ui` に `{bridge:{url,token}}` を送って登録します。登録前の updater client がない場合、window mode でも呼び出しは `APP_UPDATER_NOT_READY` で失敗します。browser mode では updater は利用不可です（`app/desktop/src-tauri/src/main.rs:1295-1297,1335-1349`、`app/host/server/index.mjs:1438-1460`、`app/host/server/app-ui.mjs:64-80,91-104`）。
- `STRATA_SHELL_BRIDGE` があっても `STRATA_SHELL_TOKEN` がなければ client は作られません。通常の process environment 以外に、Linux `setBridge` は同名キーを持つオブジェクトを updater factory に渡して client を作り直します（`app/host/server/app-ui.mjs:91-95`）。
- 通知 client は同じ値を使いますが、shell bridge の `/shell/notify` は Linux build では常に `shown: false` を返します。したがって Linux で URL/token があっても、この経路からの shell 通知は表示されません（`app/desktop/src-tauri/src/updater.rs:427-435`）。
- bridge が開いても、アプリ更新の check/install はユーザーによる更新確認・更新操作から呼ばれるもので、Host 起動だけでは updater feed へ問い合わせません（`app/desktop/src-tauri/src/updater.rs:11-14`、`app/host/server/app-updater.mjs:9-10,35-42`）。

## 実行時の詳細

`app-updater.mjs` は `createAppUpdater` 呼び出し時に `env.STRATA_SHELL_BRIDGE` と token をローカル変数へ読み込みます。`shell-prefs.mjs` の `createShellNotifier` も同様に生成時の値を保持するため、これらの client は環境変更を後から再読込しません。Host の `index.mjs` は起動時に両 factory を呼びます（`app/host/server/app-updater.mjs:19-24`、`app/host/server/shell-prefs.mjs:66-70`、`app/host/server/index.mjs:148-152`）。

Windows/macOS では Rust が listener を起動し、Host の子プロセス環境へ URL/token を設定してから spawn します。Linux では Host 起動時の環境変数設定ではなく、window process が認証付き POST で URL/token を登録し、`app-ui.mjs` の bridge client を差し替えます。Host は `/api/control/ui` を受け取った時点で登録値を検査します（`app/desktop/src-tauri/src/main.rs:554-578,1335-1349`、`app/desktop/src-tauri/src/updater.rs:443-464`、`app/host/server/index.mjs:1438-1460`、`app/host/server/app-ui.mjs:91-95`）。

updater client は `/app-update/check`、`/app-update/install`、`/app-update/status` を呼び、通常の各 request には 120 秒、status polling には 15 秒の timeout を設定します。shell updater listener は接続読み取りに 5 秒の timeout を設定します。通知 client は `/shell/notify` を 5 秒で呼びます。Host の更新確認では失敗詳細を `appCheckFailed` に入れ、画面用の一般文言 `Strata couldn't check for a new version of the app itself. Try again later.` と details を返します。更新処理では `app check: ...` を update log に記録します。認証失敗は HTTP 401、更新 check 内の失敗は HTTP 502、実行中の二重 install 要求は HTTP 409 になります（`app/host/server/app-updater.mjs:23-28,41-65`、`app/host/server/shell-prefs.mjs:71-77`、`app/desktop/src-tauri/src/updater.rs:379-417`、`app/host/server/updates.mjs:84-105`、`app/host/server/native-control.mjs:811-829`）。

## 根拠

- `app/desktop/src-tauri/src/updater.rs:1-14,218-230,379-464` — bridge の用途、loopback listener、環境への設定、認証と route。
- `app/desktop/src-tauri/src/main.rs:554-578,1295-1297,1335-1349` — OS ごとの Host 起動と Linux window からの bridge 登録。
- `app/host/server/app-updater.mjs:19-67` — bridge 値の判定、読み取り時期、Host updater request。
- `app/host/server/shell-prefs.mjs:66-77` — 通知 client の bridge 読み取り。
- `app/host/server/app-ui.mjs:64-104`、`app/host/server/index.mjs:1438-1460` — app mode、Linux bridge setter、登録 API。
- `app/host/server/updates.mjs:84-105`、`app/host/server/native-control.mjs:808-829` — 更新 check の UI 結果と update log。
