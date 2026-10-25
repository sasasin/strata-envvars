# `STRATA_SHELL_BRIDGE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

デスクトップアプリの Tauri shell が起動した loopback update bridge の URL を App Host に渡します。Node 側はこの URL を `STRATA_SHELL_TOKEN` と組み合わせて app updater の有無を判断し、明示的な更新確認・インストール操作を shell に要求します。ブラウザーや通常のソース checkout では bridge が渡らず、App Host の updater は利用できません。

## 値と判定

| 値 | `createAppUpdater` の結果 |
|---|---|
| 未設定または空文字 | updater を作らず `null` |
| `http://127.0.0.1:<1桁以上の数字>` 以外 | updater を作らず `null` |
| 上記形式に一致し、`STRATA_SHELL_TOKEN` も truthy | updater オブジェクトを作る |
| URL が形式に一致しても token が未設定または空文字 | updater を作らず `null` |

URL は正規表現 `/^http:\/\/127\.0\.0\.1:\d+$/` で文字列全体を照合します。ポートは1桁以上の数字という形式だけを検査し、数値範囲やポートの実在性はここでは検証しません。`localhost`、IPv6 loopback、末尾 `/`、パス付き URL、HTTPS は受け付けません。値の大文字小文字変換、空白除去、数値 parse はありません。

## 有効になる条件

- デスクトップ shell が loopback listener の bind に成功し、その URL と token を App Host 起動コマンドの環境に設定すること。
- App Host で updater が生成される時点で、URL が上記形式に一致し token が空でないこと。
- 既定では `createAppUpdater()` が `process.env` を参照します。App UI は初期化時に現在の環境から updater を生成します。また shell から後で `setBridge({url, token})` を受け取った場合は、渡された値を明示的な環境オブジェクトとして updater を作り直します。
- shell の listener が起動できない場合、Rust 側は `None` を返し、この URL/token を設定しません。その場合アプリ内更新 bridge は使えません。

## 実行時の詳細

`STRATA_SHELL_BRIDGE` は `createAppUpdater` の呼び出し時に一度読みます。返された updater は URL を closure に保持します。以後 `process.env` を変更しても既存 updater の URL は変わりません。値は子プロセスに再転送されず、この変数を読むのは App Host の updater モジュールです。Tauri shell 側は listener を `127.0.0.1` の空きポートに bind し、`apply_env` が成功した bridge の URL を App Host の `Command` に設定します。

updater が存在すると `check()` は `GET /app-update/check`、`install()` は `POST /app-update/install` の後に `GET /app-update/status` を polling します。各要求には `STRATA_SHELL_TOKEN` 由来の Bearer authorization を付けます。HTTP 応答が成功でなければ本文の `error`、または status code を含む例外になります。更新確認・インストールは host 起動時には行わず、UI の明示操作で呼ばれます。

Rust bridge は受信 token を照合し、一致しない場合 `401 Unauthorized` を返します。既知の route 以外は `404 Not Found` です。これは `STRATA_SHELL_BRIDGE` 単独の設定で実行される機能ではなく、token と shell bridge の起動が必要です。

## 根拠

- `apps/host/server/app-updater.mjs:13-22` — 既定の `process.env`、URL/token の読み取りと検証、loopback HTTP 要求。
- `apps/host/server/app-updater.mjs:24-40` — bridge URL を使う check/install/status 要求と例外処理。
- `apps/host/server/app-ui.mjs:63-90` — App UI 初期化時の読み取り、および shell から bridge を受けた場合の updater 再生成。
- `apps/desktop/src-tauri/src/updater.rs:191-214` — token 検証と bridge の route/status。
- `apps/desktop/src-tauri/src/updater.rs:217-239` — loopback listener、URL 生成、App Host 子プロセス環境への設定。
- `apps/host/tests/component-updates.test.mjs:144-164` — unset・非 loopback の拒否、および loopback と token を使う client のテスト（実装根拠ではなく補助確認）。
