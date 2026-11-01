# `STRATA_SHELL_TOKEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

desktop shell が host に渡す loopback bridge の bearer token です。host はこの値を `Authorization: Bearer ...` に載せ、shell の updater bridge と通知 bridge に要求します。通常の Strata engine 環境設定ではなく、desktop shell と同梱 host 間の認証情報です。

Windows/macOS の shell は host 子プロセスの環境に bridge URL と token を設定します。Linux では shell が bridge を起動した後、host の `/api/control/ui` に bridge URL と token を登録し、host の updater クライアントがその値を使います。bridge を作れない場合は updater を登録・提供できません（`apps/desktop/src-tauri/src/main.rs:495-505,1165-1177`, `apps/desktop/src-tauri/src/updater.rs:227-249`, `apps/host/server/index.mjs:1319-1328`）。

## 値と判定

Strata は値を数値や真偽値として parse しません。JavaScript の通常の truthy 判定で存在を確認し、受け取った文字列を bearer token としてそのまま送ります。

| 状態 | host の動作 |
|---|---|
| 未設定（`undefined`） | bridge URL または token が falsy なら updater/notifier を作らず `null`。 |
| 空文字 | 未設定と同じく falsy なので `null`。 |
| 空でない文字列 | token 自体の形式・長さは環境変数読み取り時には検査せず、Authorization header にそのまま設定する。bridge URL が別途 `http://127.0.0.1:<数字のport>` の正規表現に合わない場合は `null`。 |

updater bridge のハンドラーは token 全体を比較し、不一致または header がない要求に `401 Unauthorized` と `{"error":"not allowed"}` を返します。長さが異なる値も一致しません（`apps/host/server/app-updater.mjs:13-22`, `apps/host/server/shell-prefs.mjs:64-74`, `apps/desktop/src-tauri/src/updater.rs:170-192`）。

## 有効になる条件

- **desktop shell 起動時**: Windows/macOS の host 起動経路は `random_token()` の戻り値を bridge の token に使い、bridge が起動できたときだけ `STRATA_SHELL_BRIDGE` と `STRATA_SHELL_TOKEN` を子プロセス環境に設定します。環境変数の値は shell が生成します（`apps/desktop/src-tauri/src/main.rs:204-216,495-505`, `apps/desktop/src-tauri/src/updater.rs:229-249`）。
- **Linux の app updater**: setup 時に shell が token を作って bridge を開始し、URL/token を含む JSON を host の `/api/control/ui` に送ります。この route は shell shutdown token で認証し、`appUi.setBridge()` に渡します。`setBridge()` は URL が loopback 形式で token が文字列かつ16文字以上であることを確認し、その bridge client を設定します。これは環境変数から読む経路ではありませんが、候補変数が表す同じ token の動的な受け渡し経路です（`apps/desktop/src-tauri/src/main.rs:1165-1177`, `apps/host/server/index.mjs:1308-1328`, `apps/host/server/app-ui.mjs:63-90`）。
- **updater の優先関係**: host 起動時に `createAppUi()` が環境変数から作る updater が初期値です。shell から bridge が後で登録されると `current()` は登録済み bridge を優先し、元の環境 bridge よりそちらを使います。CLI 引数や他の環境変数による token の上書きはありません（`apps/host/server/app-ui.mjs:63-90`）。
- **desktop notification**: `createShellNotifier()` は host 起動時に環境の bridge URL/token を読み取ります。URL/token がそろわなければ notifier は作られず、`/api/shell/notify` は `{shown:false}` を返します。shell の bridge は Linux では通知の `shown` を常に false とするコンパイル条件があります（`apps/host/server/index.mjs:127-142,1958-1962`, `apps/desktop/src-tauri/src/updater.rs:213-222`）。
- 通常ブラウザーやソース checkout のように desktop shell が bridge を供給しない場合、環境に両方の値がなければ app updater/notifier は使えません。app updater はユーザーが更新確認・更新を要求したときに呼ばれ、host 起動だけでは update check を行いません（`apps/host/server/app-updater.mjs:4-10,24-40`, `apps/host/server/updates.mjs:48-51,79-88`）。

## 実行時の詳細

環境変数経由では `createAppUi()` と `createShellNotifier()` の初期化時に値を取り込みます。その後プロセス環境を書き換えても既存 client の値は再読込されません。app updater は shell の `/api/control/ui` による `setBridge()` で別値へ差し替えられます。通知 client には同様の setter はありません（`apps/host/server/app-ui.mjs:63-90`, `apps/host/server/index.mjs:128-132`）。

app updater client は `/app-update/check`、`/app-update/install`、`/app-update/status` へ同じ bearer token を付けます。HTTP 応答が成功でなければ応答 JSON の `error`、なければ status を含む既定エラーを throw します。通知 client は `/shell/notify` に POST し、通信例外は `/api/shell/notify` の呼び出し元で握りつぶして `{shown:false}` を返します（`apps/host/server/app-updater.mjs:17-39`, `apps/host/server/shell-prefs.mjs:69-75`, `apps/host/server/index.mjs:1958-1962`）。

環境変数が欠けている場合、app updater の状態は unavailable になります。`checkComponentUpdates()` は app updater がないと shell の app update check を行わず、Control 側の component 更新結果を返します。app updater を呼んだ際の失敗は設定画面の app update check error として表示対象になります（`apps/host/server/app-ui.mjs:69-79`, `apps/host/server/updates.mjs:75-96`）。

## 根拠

- 環境変数の読み取り、falsy 判定、bearer header: `apps/host/server/app-updater.mjs:13-22`, `apps/host/server/shell-prefs.mjs:64-74`
- shell bridge の token 保持・認証・HTTP 失敗応答: `apps/desktop/src-tauri/src/updater.rs:45-49,170-223,227-249`
- shell による生成と Windows/macOS 子プロセスへの設定: `apps/desktop/src-tauri/src/main.rs:204-216,495-505`
- Linux の bridge 引き渡しと host 側登録: `apps/desktop/src-tauri/src/main.rs:1165-1177`, `apps/host/server/index.mjs:1308-1328`, `apps/host/server/app-ui.mjs:63-90`
- 更新確認・失敗の伝播と通知の結果: `apps/host/server/updates.mjs:75-96`, `apps/host/server/index.mjs:1958-1962`
