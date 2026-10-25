# `STRATA_UI_MODE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。Strata 所有のデスクトップシェルとホスト実装を確認。外部ライブラリの動作は対象外。

## 役割

ホストがページの表示先をデスクトップアプリのウィンドウ（`window`）と通常のブラウザータブ（`browser`）のどちらとして扱うかを初期化します。ホストはこの状態を `/api/app/mode` でページに伝え、ブラウザーモードでの「Quit Strata」表示とアプリ本体の更新可否を切り替えます。

## 値と判定

ホストの `createAppUi()` は `process.env` から値を一度読み、文字列全体を大文字小文字を区別して比較します。trim、数値変換、真偽値変換は行いません。

| ホスト環境の値 | 初期 `mode` | 判定 |
|---|---|---|
| 未設定 | `null` | アプリシェルから起動された状態ではないものとして扱う |
| 空文字 | `null` | `window` / `browser` のいずれとも一致しない |
| `window` | `window` | デスクトップアプリのウィンドウとして扱う |
| `browser` | `browser` | ブラウザータブとして扱う |
| その他（`Window`、` browser `、`0` など） | `null` | 一致しない値は無効 |

この環境変数を設定して `window` を選ぶ経路では `STRATA_UI_REASON` は読みません。`browser` の場合だけ `STRATA_UI_REASON` を読み、空文字または未設定なら `chosen` にします。

## 有効になる条件

- Strata デスクトップシェルはホストの子プロセスを起動するとき、親プロセスから継承した環境を `STRATA_UI_MODE` で上書きし、`window` または `browser` を必ず渡します。シェル内の選択は、`STRATA_UI=browser` または `--browser` で `browser` になります。それ以外は `window` です。`STRATA_UI` の判定では trim と小文字化をしますが、これはホストが受け取る `STRATA_UI_MODE` 自身の判定規則ではありません。
- `--browser` は `STRATA_UI` の値にかかわらず browser を選びます。反対向きに `window` を強制する CLI オプションはこの引数解析にはありません。
- ホストを手動起動する場合など、シェルがこの変数を渡さない経路では初期値は `null` です。以前の互換経路として有効な `STRATA_SHELL_BRIDGE` / `STRATA_SHELL_TOKEN` があれば updater オブジェクトを作る場合がありますが、`STRATA_UI_MODE` による UI 状態自体は `null` のままです。

## 実行時の詳細

ホスト起動時に `apps/host/server/index.mjs` が `createAppUi()` を一度呼びます。初期 `mode` はその時点で確定し、環境を後から変更しても再読込しません。一方、シェル専用の `POST /api/control/ui` が `mode: "browser"` を送ると、`switchToBrowser()` が実行中の状態を `browser` に更新し、理由文字列を最大40文字にして保存します。これはウィンドウ起動失敗時にも使われます。

状態の観測と効果は次のとおりです。

- `GET /api/app/mode` は `mode`、`reason`、`canQuit`、`appUpdate` を返します。`browser` では `canQuit: true`、`appUpdate: "unavailable"` です。`window` では `canQuit: false`、`appUpdate: "available"` です。`null` は両方とも利用不可として返します。
- ページはこの API をページロード時に一度呼びます。ブラウザーモードではメニューに「Quit Strata」を表示します。タブを閉じるだけではホストが終了しないため、終了 API を提供します。ホスト側も終了要求を browser モードに限り受け付け、window モードでは HTTP 409 を返します。
- `/api/app/mode` の `appUpdate` は browser モードで利用不可を示します。通常の browser 起動では Tauri のウィンドウプロセスがないためアプリ自身の更新はできず、エンジンや Strata Control の更新とは別です。ただし、旧 bridge 環境が残っている場合は updater 呼び出しがその bridge にフォールバックする実装です。
- 初期値が有効な `window` / `browser`、または旧 bridge 環境がある場合に updater オブジェクトが作られます。初期値が `null` で旧 bridge もなければ作られません。

## 根拠

- `apps/host/server/app-ui.mjs:29,63-89,92-105` — 有効値、初期読み取り、`STRATA_UI_REASON` の fallback、状態/API と browser への実行時切替。
- `apps/host/server/index.mjs:124-128,1290-1305,1330-1331` — ホスト起動時の生成、状態 API、シェル認証付き切替、更新処理への updater 接続。
- `apps/desktop/src-tauri/src/supervisor.rs:29-55,350-364,386-400,429-432` — `STRATA_UI` と `--browser` の選択規則、子ホストに設定する値、失敗時の browser 切替。
- `apps/host/src/lib/app-mode.ts:4-24`, `apps/host/src/app/Sidebar.tsx:193`, `apps/host/server/updates.mjs:75-90` — ページ側の一回限りの読込、browser 時の終了 UI、アプリ更新表示。
- `apps/desktop/tester/README-linux.txt.in:43-44` は browser モードでタブを閉じても Strata が停止しないことを説明しています。`docs/DETAILS.md` に `STRATA_UI_MODE` の説明は見つからず、性能測定対象でもありません。
