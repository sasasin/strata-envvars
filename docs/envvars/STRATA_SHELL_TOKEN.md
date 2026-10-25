# `STRATA_SHELL_TOKEN`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

デスクトップ shell の Tauri updater と App Host 間にある loopback HTTP bridge の bearer 認証値です。Host がこの値を `Authorization: Bearer ...` として送信し、shell 側は受信値を bridge 起動時に保持した token と照合します。更新確認・インストール・進捗取得の各 API を保護します。

この変数は Strata の通常 CLI や単独で起動した Host の設定ではありません。デスクトップ shell が起動した Host で更新 bridge が利用可能な場合に使われます。

## 値と判定

| 場所 | 未設定・空文字 | 設定時の判定 |
|---|---|---|
| Host の `createAppUpdater()` | `STRATA_SHELL_BRIDGE` ともに必要なため updater を作らず `null` | JavaScript の truthiness のみで確認し、文字列形式・長さ・内容は検査しない。空文字は無効、その他の truthy 値は token として保持する |
| Host の `setBridge()` | `token` 欠落時は既定値 `{}` の destructuring により `undefined`。型検査で拒否 | `typeof token === 'string'` かつ `token.length >= 16` が必要。文字種や形式は制限しない |
| shell の bridge | token は bridge 起動時に引数で受け取る | 比較対象 token と HTTP Authorization header の bearer 値を比較する。長さが一致し、全バイト一致した場合のみ認証する |

Host の環境変数経路では、bridge URL も truthy で、かつ文字列全体が `http://127.0.0.1:<数字のport>` に一致しなければ updater は生成されません。`STRATA_SHELL_TOKEN` 単独では機能しません。URL 正規表現にパス・末尾スラッシュ・localhost は含まれません。

環境変数経路では評価時に値を一度取得して updater closure に保存するため、その後プロセス環境を変更しても既存 updater の token は更新されません。Linux の `setBridge()` 経路は API 呼び出しごとに渡された URL/token で updater を作り直し、こちらでは token が16文字以上であることも確認します。

## 有効になる条件

- updater bridge の loopback listener が起動できること。shell は `127.0.0.1` の空き port に bind し、失敗時は bridge を返さない。
- Windows/macOS では shell が Host の `Command` に bridge URL と token を設定して Host を起動すること。
- Linux では独立した window process が bridge を起動し、shell 認証付き `POST /api/control/ui` で Host に `{bridge:{url,token}}` を登録すること。Host の `setBridge()` は URL を `BRIDGE_URL` で、token を文字列かつ16文字以上で検査する。
- Host が bridge URL と token を持っていても、ブラウザ UI で updater が使えるとは限らない。browser mode では updater 操作が unavailable として扱われる。

## 実行時の詳細

Windows/macOS の shell は `random_token()` で token を作り、`updater::start()` に渡して listener を開始し、成功した場合に限って `updater::apply_env()` が `STRATA_SHELL_TOKEN` を子 Host の環境へ設定します。`random_token()` は4個の64-bit hash 値を16進連結した文字列を返します。bridge bind に失敗すると `apply_env()` はこの変数を設定せず、Host 側の `createAppUpdater()` は updater を返しません。

Linux では Host 自体を shell が起動し、window process が別途 updater bridge を開始します。window process は bridge token と URL を `/api/control/ui` に送信し、Host が `setBridge()` から `createAppUpdater({env:{STRATA_SHELL_BRIDGE:url, STRATA_SHELL_TOKEN:token}})` を呼びます。この経路では値は Node の `process.env` に設定されず、同じ updater factory に渡す一時的な env object のプロパティとして使われます。

Host は updater の各呼び出しで `Authorization: Bearer ${token}` を送信します。shell は `authorization: ` または `Authorization: ` で始まる header を探し、値の前後空白を除去し、先頭の `Bearer ` を除いて比較します。token が一致しない、または header がなければ `401 Unauthorized` と JSON `{"error":"not allowed"}` を返します。一致すると `/app-update/check`、`/app-update/install`、`/app-update/status` を処理します。Host の `check()` と `install()` はユーザー操作から呼ばれる経路であり、Host 起動時に自動で更新確認する処理ではありません。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:203-215` — token の生成。
- `apps/desktop/src-tauri/src/main.rs:480-490,1135-1149` — Windows/macOS の環境設定経路と Linux window process による bridge 登録。
- `apps/desktop/src-tauri/src/updater.rs:217-240` — loopback listener と `STRATA_SHELL_TOKEN` の子 Host への設定。
- `apps/desktop/src-tauri/src/updater.rs:170-213` — Authorization header の読み取り、token 照合、HTTP 応答。
- `apps/host/server/app-updater.mjs:13-39` — 値の確認、Authorization header の送信、更新 API 呼び出し。
- `apps/host/server/app-ui.mjs:63-90` — 起動環境からの初期化、browser mode の状態、Linux からの bridge 登録と追加検査。
- `apps/host/server/index.mjs:1298-1307` — shell 限定の bridge 登録 API。
- `docs/DETAILS.md` にはこの変数の個別説明や測定値を確認できなかったため、性能・正確性に関する主張は記載していません。
