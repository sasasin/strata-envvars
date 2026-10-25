# `STRATA_UI_REASON`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。Strata 所有のデスクトップシェルとホスト実装を確認。外部ライブラリの動作は対象外。

## 役割

ホストが初期状態から browser mode で起動した理由を文字列で保持し、`GET /api/app/mode` の `reason` フィールドに含めます。この値は `mode` の選択、終了可否、アプリ更新可否を変えません。コード上、`reason` を使った画面表示やログ出力も確認できません。

## 値と判定

ホストの `createAppUi()` が起動時に `process.env` から読みます。`mode` が厳密に `browser` のときだけ参照し、JavaScript の `||` で fallback します。

| 起動時の状態 | 初期 `reason` |
|---|---|
| `STRATA_UI_MODE=browser` かつ `STRATA_UI_REASON` が未設定または空文字 | `chosen` |
| `STRATA_UI_MODE=browser` かつ `STRATA_UI_REASON` が空でない文字列 | その文字列をそのまま保持 |
| `STRATA_UI_MODE=window` または `null` | `null`。環境変数は参照しない |

値の trim、大小文字変換、文字列検証はありません。たとえば `0`、`false`、空白だけの文字列も空ではないため、そのまま `reason` になります。変数を設定しても `STRATA_UI_MODE` が `browser` でなければ効果はありません。

## 有効になる条件

- 通常のデスクトップ起動では、シェルが `STRATA_UI_MODE` に `window` または `browser` を設定します。`--browser` 等で明示的に browser 起動する場合、シェルは子ホストの `STRATA_UI_REASON` を `chosen` に設定するため、親環境に設定した値を上書きします。
- アプリウィンドウが実行中に失敗して browser に切り替わる場合、この環境変数は再読込されません。シェルから `/api/control/ui` に渡される理由（`window-failed`）が使われます。
- ホスト起動後にプロセス環境を変更しても、初期値は更新されません。シェル経由の切替時だけ、`switchToBrowser()` が `reason` を更新します。

## 実行時の詳細

ホスト起動時、`apps/host/server/index.mjs` が `createAppUi()` を一度呼び出します。初期 `mode` と `reason` はその時点で決まり、`GET /api/app/mode` が `{ mode, reason, canQuit, appUpdate }` として返します。初期 browser mode の `reason` は長さ制限されません。

シェル認証付き `POST /api/control/ui` が `mode: "browser"` を受けると、`switchToBrowser()` は環境変数ではなくリクエストの `reason` を使います。省略時は `window-failed`、指定時は `String()` で文字列化して先頭40文字を保存します。シェルは明示的に browser を選んだ場合は `chosen`、ウィンドウ異常終了時は `window-failed` を送ります。この切替後も `canQuit` は `true`、`appUpdate` は `unavailable` です。

## 根拠

- `apps/host/server/app-ui.mjs:63-66` — 初期値の読み取り、browser mode 限定、空文字時の `chosen` fallback。
- `apps/host/server/app-ui.mjs:81-99` — API 状態への含有、browser 切替時の理由文字列と40文字制限。
- `apps/host/server/index.mjs:124-128,1290-1306` — 初期化、状態 API、シェル認証付き切替の接続。
- `apps/desktop/src-tauri/src/supervisor.rs:183-192,303-314,350-364,386-400` — 子ホストへの `chosen` 設定、明示 browser 起動と window 異常終了時にシェルが送る理由。
- `apps/host/src/lib/app-mode.ts:4-18` — ページ側の状態型と `/api/app/mode` の一回限りの取得。`docs/DETAILS.md` に本変数の説明や性能測定は見つかりません。
