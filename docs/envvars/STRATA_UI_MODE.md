# `STRATA_UI_MODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

App Host に、ページを表示する主体がデスクトップアプリのウィンドウか通常のブラウザーかを伝えます。値に応じて `/api/app/mode` の状態、ブラウザーモードの「Quit Strata」操作、デスクトップアプリ本体の更新可否が変わります。

Linux デスクトップアプリは host 子プロセスを起動するときにこの変数を `window` または `browser` に設定します。ユーザーが起動方法を選ぶ入力は別名の `STRATA_UI=browser` または `--browser` です。`STRATA_UI_MODE` はその選択結果を App Host に渡す変数です（`apps/desktop/src-tauri/src/supervisor.rs:353-364`、`apps/desktop/src-tauri/src/main.rs:865-873`）。

## 値と判定

App Host は `process.env` から起動時に値を取り、`window` と `browser` のいずれかに文字列が完全一致する場合だけモードとして採用します。大文字小文字変換、空白除去、真偽値・数値への変換はありません（`apps/host/server/app-ui.mjs:28-29,63-65`）。

| 値 | 判定と初期状態 |
|---|---|
| `window` | window モード。`reason` は `null`、`canQuit` は `false`、`appUpdate` は `available`。 |
| `browser` | browser モード。`STRATA_UI_REASON` が truthy ならその値、そうでなければ `chosen` が `reason`。`canQuit` は `true`、`appUpdate` は `unavailable`。 |
| 未設定、空文字、その他（例: `Window`, ` browser `, `0`） | モードは `null`。`reason` は `null`、`canQuit` は `false`、`appUpdate` は `unavailable`。 |

`STRATA_UI_REASON` は `STRATA_UI_MODE=browser` のときだけ初期 reason に使われます。空文字は `|| 'chosen'` により `chosen` に置き換わります。Linux supervisor は起動時に `--browser` / `STRATA_UI=browser` が選ばれた場合 `STRATA_UI_REASON=chosen` も host に設定します（`apps/host/server/app-ui.mjs:64-65`、`apps/desktop/src-tauri/src/supervisor.rs:361-364`）。

## 有効になる条件

- Linux デスクトップアプリの supervisor は host 起動時、親プロセス環境を継承する `Command` に対して `STRATA_UI_MODE` を毎回明示設定します。通常起動は `window`、`--browser` または `STRATA_UI=browser` なら `browser` です。したがって、デスクトップアプリの親環境に同名変数を設定しても host にはその値が引き継がれず、supervisor の選択結果で上書きされます（`apps/desktop/src-tauri/src/supervisor.rs:43-55,341-365`）。
- Linux 以外の desktop 実行経路は `run_embedded()` に進み、Linux supervisor の host 子プロセス設定は通りません（`apps/desktop/src-tauri/src/main.rs:875-876`）。
- App Host を単独起動する場合は `process.env.STRATA_UI_MODE` の値が直接判定されます。unset や認識されない値は `null` となり、ページ側にデスクトップウィンドウの終了・更新機能を示しません（`apps/host/server/app-ui.mjs:63-85`）。
- Linux の通常ウィンドウ起動でも、ウィンドウプロセスが起動失敗または正常終了以外で終了すると shell は host を維持し、host のモードを browser に切り替えます。したがって初期値 `window` は実行中に `browser` へ変わることがあります（`apps/desktop/src-tauri/src/supervisor.rs:303-314,385-431`）。

## 実行時の詳細

Host の `server/index.mjs` は起動時に `createAppUi()` を呼び、そこで環境を一度読み取ります。環境変数をプロセス起動後に変更しても再読込しません。モードの変更は shell から認証済み `POST /api/control/ui` を受けて `switchToBrowser()` が状態を更新する別経路です（`apps/host/server/index.mjs:127-131,1305-1328`、`apps/host/server/app-ui.mjs:63-67,81-99`）。

- `GET /api/app/mode` は `{ mode, reason, canQuit, appUpdate }` を返します。ブラウザーモードのページにだけ Quit メニューが表示されます（`apps/host/server/index.mjs:1311-1312`、`apps/host/server/app-ui.mjs:81-85`、`apps/host/src/app/Sidebar.tsx:193`）。
- `POST /api/app/quit` は browser モードなら 202 を返し、次の immediate callback で host の shutdown を呼びます。window / `null` モードでは 409 と `Close the Strata window to quit.` を返します。ルートには `x-strata-client` ヘッダーの検査もあります（`apps/host/server/index.mjs:1313-1317`、`apps/host/server/app-ui.mjs:101-106`）。
- browser モードでは App Host にウィンドウプロセスがなく、アプリ本体の Tauri updater は利用できません。updater の `unavailable` は `The Strata app itself can't be updated in browser mode. Start Strata from its icon, without --browser, to update it.` です。エンジンと Strata Control の更新は別に扱われます（`apps/host/server/app-ui.mjs:26-27,69-79`、`apps/host/server/updates.mjs:73-96`）。`window` モードの updater はウィンドウプロセスが bridge を登録するまで待ち、未登録なら `The app updater is not ready yet. Try again in a moment.` のエラーになります（`apps/host/server/app-ui.mjs:67-79,86-90`）。
- Linux supervisor が明示 browser 起動を選ぶと、host の起動・health check 後に端末へ URL と「タブを閉じても Strata は停止しない」旨を出し、ブラウザーを開くよう host に依頼します（`apps/desktop/src-tauri/src/supervisor.rs:372-388,75-80,182-200`）。ブラウザーを開けなかった場合は `No browser could be opened. Open http://127.0.0.1:<port>/ in your browser.` を stderr に出します（同 `supervisor.rs:82-84,195-200`）。
- window の起動・実行失敗時は supervisor がクラッシュ理由と browser への切替をログに出し、host に `mode: browser` と `reason: window-failed` を通知します。host はモードを更新してページを開き、通知を要求します。`switchToBrowser()` は通知処理の結果を待たず、起動したブラウザーの成否を `opened` として返します（`apps/desktop/src-tauri/src/supervisor.rs:303-314,398-431`、`apps/host/server/index.mjs:1319-1328`、`apps/host/server/app-ui.mjs:94-99`）。

## 根拠

- 候補一覧には `STRATA_UI_MODE` がありますが、実際の環境値の読取箇所は `apps/host/server/app-ui.mjs:63-65` です。完全一致の判定結果がモード状態、API、Quit 動作、updater の可否に使われるため、Strata の App Host が読む環境変数です。
- Strata ソース内の完全一致参照は、本番コードでは App Host の読取と Linux supervisor の子プロセスへの設定です。`apps/host/tests/app-ui.test.mjs` にも名前がありますが、値や挙動の根拠は本番コードに基づいています。
- `docs/DETAILS.md` にこの変数の仕様説明は見つかりませんでした。ここでは調査対象 commit の実装を根拠としています。
