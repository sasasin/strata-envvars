# `STRATA_SHELL_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

デスクトップシェルが起動した App Host から、シェルの loopback bridge を呼び出すときに送る Bearer 認証値。App Host は `STRATA_SHELL_BRIDGE` とこの値の両方がそろい、bridge URL が `http://127.0.0.1:<port>` 形式の場合にだけ updater client を作る。作成された client はアプリ更新の確認・実行、helper window の起動に使われる。`createShellNotifier` も同じ環境変数ペアから通知 client を作る（`app/host/server/app-updater.mjs:19-24,30-37`、`app/host/server/shell-prefs.mjs:66-77`）。

通常の設定用 token や CLI 引数ではない。シェルは bridge 起動時に token を生成し、Windows/macOS では App Host 子プロセスに環境変数として渡す。Linux では shell が登録 API の JSON body に bridge の URL と token を入れ、App Host の `setBridge` がインメモリの client を設定する（`app/desktop/src-tauri/src/main.rs:243-253,554-568,1335-1347`、`app/desktop/src-tauri/src/updater.rs:441-455,457-464`、`app/host/server/index.mjs:1451-1460`）。

## 値と判定

| 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| App Host の起動時 client (`createAppUpdater`, `createShellNotifier`) | `STRATA_SHELL_BRIDGE` または token が未設定なら client を作らない | JS の truthy な token 文字列と、`http://127.0.0.1:<数字>` に完全一致する bridge URL の組み合わせ | token の空文字、bridge 未設定、または URL が正規表現に一致しない場合。token 自体は形式・長さ・数値としての妥当性を検査しない |
| `appUi.setBridge` による登録 | 該当なし（登録 body に bridge があるとき呼ばれる） | URL が同じ loopback 形式で、token が文字列かつ `length >= 16` | 空文字や 16 文字未満、非文字列、無効 URL は `That is not a bridge address.` で拒否 |

この値は `process.env` / 渡された `env` object から文字列として読み、trim、大小文字変換、数値変換はしない。直接環境に空文字がある場合も未設定と同じく client を作らない。空白だけの値は JS では truthy なので形式検査を通るが、shell が保持する token との一致は別に認証される。`setBridge` 経由では空白を含め 16 JS 文字以上であれば形式上受理されるが、shell 側 token と一致しなければ認証されない（`app/host/server/app-updater.mjs:19-22`、`app/host/server/shell-prefs.mjs:67-69`、`app/host/server/app-ui.mjs:91-95`、`app/desktop/src-tauri/src/updater.rs:357-359,392-398`）。

## 有効になる条件

- App Host の updater client には `STRATA_SHELL_BRIDGE` も必要で、URL は `http://127.0.0.1:<port>` でなければならない。HTTPS、`localhost`、IPv6 loopback は client 作成条件に一致しない（`app/host/server/app-updater.mjs:19-22`）。
- bridge listener はシェルが `updater::start` を呼び、`127.0.0.1` の空き port に bind できた場合に限り存在する。bind できない場合 `None` となり、in-app update bridge はない（`app/desktop/src-tauri/src/updater.rs:441-455`）。
- リクエスト token は bridge 起動時にシェルが保持する値と完全一致する必要がある。token 単独の設定や誤った値では認証されない（`app/desktop/src-tauri/src/updater.rs:357-359,392-398`）。
- Windows/macOS の shell 起動経路では bridge が存在するときだけ `apply_env` が `STRATA_SHELL_TOKEN` と URL を App Host 子プロセスに設定する。shell の起動処理と連携しない standalone / browser / source-checkout 実行では、通常は bridge がなく client は作られない（`app/desktop/src-tauri/src/main.rs:554-567`、`app/desktop/src-tauri/src/updater.rs:457-464`、`app/host/server/app-updater.mjs:7,19-22`）。
- Linux の desktop setup は環境変数ではなく `/api/control/ui` の JSON body で token を渡して `appUi.setBridge` を呼ぶ。この client は updater 用であり、起動時に `process.env` から一度だけ作られる `createShellNotifier` には登録 body の token は反映されない（`app/desktop/src-tauri/src/main.rs:1335-1347`、`app/host/server/index.mjs:1451-1460,152`）。
- `createAppUpdater` と `createShellNotifier` は App Host 初期化時に作られ、値をその client 閉包に保持する。環境を後から変更しても既存 client の token は更新されない。一方 `setBridge` は渡された URL/token で updater client を置き換える（`app/host/server/app-ui.mjs:64-69,91-95`、`app/host/server/index.mjs:148-152`）。

## 実行時の詳細

Windows/macOS では `start_host` が bridge token を生成し、`updater::start` が別の token で listener を起動する。bridge が作れた場合に限り `updater::apply_env` が URL と token を Node 子プロセス環境へ設定する。Linux では setup 内で bridge を開始し、URL と token を shutdown token 認証付きの `POST /api/control/ui` body に載せて App Host に登録する（`app/desktop/src-tauri/src/main.rs:554-568,1335-1347`）。

Host の updater client は各 bridge 呼び出しに `Authorization: Bearer <token>` を付ける。shell は受信した `authorization` header から Bearer 値を取り出し、長さと全 byte の XOR 比較で token と照合する。不一致は `401 Unauthorized` と `{"error":"not allowed"}` を返し、router の処理には進まない。認証後、未知の route は `404 Not Found` となる（`app/host/server/app-updater.mjs:23-28`、`app/desktop/src-tauri/src/updater.rs:357-359,379-400,401-438`）。

Host 側では app update check/install/status の bridge request に既定 120 秒、status polling に 15 秒、helper 起動に 10 秒の AbortSignal timeout を指定する。通知 client は通知 request に 5 秒を指定する。これらは token の parse ではなく各 request の待ち時間である（`app/host/server/app-updater.mjs:23,31-34,41-49`、`app/host/server/shell-prefs.mjs:71-77`）。

## ログと測定値

環境変数 token の未設定・形式不一致を記録するログは見当たらず、Host client が `null` になる。`setBridge` が無効な URL/token を受けると上記のエラー文で例外になり、`/api/control/ui` handler は 400 を返す。認証不一致では shell bridge が 401 を返す。Linux shell が host への bridge 登録 request 自体に失敗した場合、stderr に `[strata] the app updater could not be registered with the host: {e}` を出す（`app/host/server/app-updater.mjs:19-22`、`app/host/server/app-ui.mjs:91-95`、`app/host/server/index.mjs:1451-1460`、`app/desktop/src-tauri/src/updater.rs:392-398`、`app/desktop/src-tauri/src/main.rs:1338-1347`）。

測定値の記載は該当なし。

## 根拠

- `app/desktop/src-tauri/src/main.rs:243-253,554-568,1335-1347` — token 生成、Windows/macOS の環境設定、Linux の bridge 登録。
- `app/desktop/src-tauri/src/updater.rs:357-359,379-455,457-464` — 認証比較、route 応答、loopback listener、子プロセス環境への設定。
- `app/host/server/app-updater.mjs:19-67` — 環境値の採用条件、Authorization header、更新 client の処理。
- `app/host/server/shell-prefs.mjs:66-78` — shell notification client の採用条件と request。
- `app/host/server/app-ui.mjs:64-95`、`app/host/server/index.mjs:1451-1460,152` — 初期 client、登録 API と動的 bridge client の設定。
