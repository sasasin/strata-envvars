# `STRATA_UI_MODE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

App Host がページをアプリ内 window で表示しているか、通常のブラウザーで表示しているかを UI と host 間で共有する内部モード値。`app-ui.mjs` は `window` / `browser` のときにだけモードを認識し、`/api/app/mode` が返す `mode`、`canQuit`、`appUpdate` などに反映する。モデル推論の選択や実行条件はこの変数では変えない。読み取りは `app/host/server/app-ui.mjs:64-86`、API は `app/host/server/index.mjs:1443-1449`。

デスクトップアプリ起動時は Rust shell が host の子プロセスにこの値を設定する。Windows/macOS は常に `window`、Linux は `--browser` または別変数 `STRATA_UI=browser` で選ばれた起動モードを設定する。したがって packaged desktop 起動では、呼び出し元の `STRATA_UI_MODE` は子 host 向けの値で上書きされる。Linux の `STRATA_UI` と CLI 判定は `app/desktop/src-tauri/src/main.rs:929-944`、`app/desktop/src-tauri/src/supervisor.rs:29-55`、host への設定は `supervisor.rs:503-526`、Windows/macOS の設定は `app/desktop/src-tauri/src/main.rs:554-568`。

## 値と判定

host 起動時に `process.env.STRATA_UI_MODE` を文字列として一度読み、`Set.has` による完全一致で判定する。文字列変換、trim、大文字小文字の正規化はしない。`window` と `browser` だけが有効。未設定、空文字、`WINDOW`、` Browser `、`0`、その他の値はすべて `null` 相当となり、拒否ログや fallback 選択ログはこの判定箇所からは出ない（`app/host/server/app-ui.mjs:29-30,64-68`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効な値の例 |
|---|---|---|---|
| App Host が環境から直接起動 | `null` | `window`, `browser` | `WINDOW`, ` Browser `, `0`, `true` |
| Linux desktop shell が host を起動 | shell が値を `window` または `browser` で上書き | `--browser` または `STRATA_UI=browser` なら `browser`、それ以外は `window` | 呼び出し元の `STRATA_UI_MODE` は判定に使われず上書きされる |
| Windows/macOS desktop app が host を起動 | shell が `window` で上書き | `window` | 呼び出し元の `STRATA_UI_MODE` は判定に使われず上書きされる |

Linux shell の browser 選択は `STRATA_UI` を trim し ASCII 小文字化して `browser` と比較し、その後 `--browser` が指定されれば browser を有効化する。`STRATA_UI_MODE` 自体は desktop CLI の入力として parse されない（`app/desktop/src-tauri/src/supervisor.rs:43-55`、`app/desktop/src-tauri/src/main.rs:929-944`）。

## 有効になる条件

- 値が App Host のプロセス環境に届き、host の `createAppUi` 初期化時に読まれること。アプリ起動中に環境を書き換えても初期 mode には反映されない。`app/host/server/index.mjs:147-151`、`app/host/server/app-ui.mjs:64-68`。
- desktop 起動では shell が値を明示設定するため、親環境から `STRATA_UI_MODE` を指定しても選択を変えない。Linux で browser 起動を選ぶ入力は `--browser` または `STRATA_UI=browser`（trim と小文字化を適用）であり、`--browser` は browser を有効にするだけで解除オプションはない（`app/desktop/src-tauri/src/supervisor.rs:43-55,515-526`）。
- `window` の mode が `appUpdate: 'available'` を示しても、更新操作に使う shell bridge が必ず利用可能とは限らない。bridge がまだ登録されず、初期 bridge もない場合、更新操作は `APP_UPDATER_NOT_READY` で失敗する。`browser` では updater を unavailable として扱い、browser mode 用の説明を返す（`app/host/server/app-ui.mjs:67-79,86,91-95`）。
- shell が window 起動失敗後に `/api/control/ui` で browser へ切り替えた場合、初期値が `window` でも runtime mode が `browser` に変わる。この更新 API は shutdown token による認証を要求する（`app/host/server/index.mjs:1438-1460`、`app/host/server/app-ui.mjs:99-110`）。

## 実行時の詳細

`createAppUi` の初期化時に mode を変数へ保持し、`state()` が現在値を返す。ページ側の `loadAppMode()` は `/api/app/mode` をページロードにつき一度取得し、失敗時や旧 host の 404 は `mode: null` 等の `NONE` 状態にする（`app/host/server/app-ui.mjs:64-86`、`app/host/server/index.mjs:1443-1444`、`app/host/src/lib/app-mode.ts:12-27`）。そのため host 内では切替後の状態が返るが、すでに読み込んだページ側の mode は自動再取得されない。

`browser` は `canQuit: true` となり、ページに「Quit Strata」が出る。`POST /api/app/quit` は `x-strata-client` がないと 403、window mode なら 409 と `Close the Strata window to quit.` を返し、browser mode なら 202 を返して shutdown を予約する。window mode の終了はウィンドウを閉じる経路に委ねられる（`app/host/server/app-ui.mjs:86,106-110`、`app/host/server/index.mjs:1445-1449`、`app/host/src/components/QuitStrata.tsx:12-27`）。

Linux shell は通常起動時に host を `window` として開始する。`--browser` / `STRATA_UI=browser` の場合は `browser` として起動し、session に mode を記録する。window の起動失敗または異常終了時は host に browser mode への切替を依頼してブラウザーを開き、通知と crash log を出す。browser を開けなければ URL を手動で開くよう stderr に案内する。これらは `STRATA_UI_MODE` の文字列 parse による出力ではなく、shell の起動・切替経路の出力（`app/desktop/src-tauri/src/supervisor.rs:27,184-203,465-475,503-563,581-594`）。

## ログと測定値

`STRATA_UI_MODE` の未設定・無効値を理由にしたログはない。Linux shell は意図的な browser 起動時に URL と `Quit Strata` / `--quit` の案内を出し、window の開始失敗時は `Strata opened in your browser because the app window couldn't start on this computer.` を記録する。browser を開けない場合の stderr 文言は `No browser could be opened. Open http://127.0.0.1:<port>/ in your browser.`（`app/desktop/src-tauri/src/supervisor.rs:27,75-83,184-203,466-475,548-550`）。この環境変数についての測定値は資料にない。

## 根拠

- `app/host/server/app-ui.mjs:29-30,64-110` — 値の完全一致、初期状態、API state に使うフラグ、browser 切替と quit。
- `app/host/server/index.mjs:1438-1465` — mode API、shell 認証付き更新、quit の HTTP status。
- `app/desktop/src-tauri/src/supervisor.rs:29-55,503-563,581-594` — Linux CLI / `STRATA_UI` 判定、host 子プロセスへの設定、browser 起動と window 失敗時の切替。
- `app/desktop/src-tauri/src/main.rs:554-568,929-944` — Windows/macOS host の `window` 設定、Linux supervisor 起動。
- `app/host/src/lib/app-mode.ts:12-27` — ページ側の取得回数、エラー時の fallback。
- `app/host/src/components/QuitStrata.tsx:5-27` — browser mode の終了 UI。
