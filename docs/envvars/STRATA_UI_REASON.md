# `STRATA_UI_REASON`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

ホストが起動した時点ですでにブラウザモードなら、その理由を `reason` として保持し、アプリモード状態 API の応答に含める文字列です。生成、モデル選択、アップデータ可否などをこの変数が制御するコードはありません。ブラウザモード自体は `STRATA_UI_MODE` が正確に `browser` の場合に限り成立し、`STRATA_UI_REASON` は理由欄だけに使われます（`app/host/server/app-ui.mjs:64-72,82-86`）。

通常のデスクトップ起動では Rust supervisor がホスト子プロセスに `STRATA_UI_MODE` を設定し、CLI で browser mode を選択した場合に限って `STRATA_UI_REASON=chosen` も設定します（`app/desktop/src-tauri/src/supervisor.rs:515-526`）。

## 値と判定

ホスト起動時に `env.STRATA_UI_REASON || 'chosen'` と評価します。JavaScript の truthy 判定なので、未設定・空文字列は `chosen` に置き換わり、空でない文字列はそのまま採用されます。文字列の形式・大文字小文字・数値としての妥当性・長さを検査したり正規化したりする処理はありません（`app/host/server/app-ui.mjs:64-66`）。

| 起動時の `STRATA_UI_MODE` | `STRATA_UI_REASON` が未設定または空文字 | 空でない値の例 | 無効になる値の例 |
|---|---|---|---|
| 正確に `browser` | `chosen` | `chosen`、`window-failed`、`anything` をそのまま採用 | 値自体に無効値は定義されない。値は検証されない |
| `window` または `browser` 以外 | `null` | 値を読まず理由は `null` | 理由の値は適用されない |

`0`、`false`、前後に空白のある文字列も、環境変数として空でなければ理由欄にそのまま入ります。これは真偽値として解釈する設定ではありません（`app/host/server/app-ui.mjs:30,64-66`）。

## 有効になる条件

- 起動時の `STRATA_UI_MODE` が `browser` と完全一致すること。そうでなければこの変数は読み取られず、初期 `reason` は `null` です（`app/host/server/app-ui.mjs:30,64-66`）。
- 通常のデスクトップ supervisor 経由で browser mode を選ぶ場合、supervisor はホスト子プロセスへ `STRATA_UI_REASON=chosen` を渡します（`app/desktop/src-tauri/src/supervisor.rs:523-526`）。
- ホストを手動起動するなど supervisor を介さない場合でも、`STRATA_UI_MODE=browser` なら読み取りは行われます。`STRATA_UI_REASON` が空または未設定なら `chosen` になります（`app/host/server/app-ui.mjs:64-66`）。
- 起動後、desktop shell が認証済みの `/api/control/ui` に `mode: "browser"` を送る経路は、環境変数由来の理由を `switchToBrowser` の理由で置き換えます。この後続遷移では理由は最大 40 文字に切り詰められ、要求側の `reason` が省略された場合は `window-failed` です（`app/host/server/index.mjs:1438-1460`; `app/host/server/app-ui.mjs:99-104`）。

## 実行時の詳細

`createAppUi` がホスト起動時に `process.env` を受け取り、モジュール初期化時に `mode` と `reason` を一度設定します。環境変数を後から変更しても再読込しません（`app/host/server/index.mjs:147-151`; `app/host/server/app-ui.mjs:64-67`）。初期状態の `reason` は `/api/app/mode` の GET 応答 JSON に含まれ、ページが表示状態を判断するために使います（`app/host/server/app-ui.mjs:82-86`; `app/host/server/index.mjs:1444`）。

アプリが起動後に browser mode へ切り替わる際は、shell からの `/api/control/ui` POST に含まれる理由が現在値を上書きします。状態 API は以後その値を返します（`app/host/server/index.mjs:1451-1460`; `app/host/server/app-ui.mjs:99-104`）。

## ログと測定値

`STRATA_UI_REASON` 自体を出力するログや標準出力・標準エラーの記述はありません。理由を観測できる経路は `/api/app/mode` の JSON 応答にある `reason` フィールドです（`app/host/server/index.mjs:1444`; `app/host/server/app-ui.mjs:82-86`）。この変数による終了・失敗経路や測定値もありません。

## 根拠

- `app/desktop/src-tauri/src/supervisor.rs:515-526` — 起動モードと browser 選択時の子プロセス環境設定。
- `app/host/server/app-ui.mjs:30,64-67` — 対応する mode と理由文字列の初期読取・fallback。
- `app/host/server/app-ui.mjs:82-104` — API 状態用データと起動後の browser 切替による更新。
- `app/host/server/index.mjs:1438-1460` — 状態取得 API と shell からの切替 API。
- `app/host/server/index.mjs:147-151` — ホストの初期化時に `createAppUi` を生成。
