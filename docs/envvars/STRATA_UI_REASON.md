# `STRATA_UI_REASON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

App Host が browser mode の理由を保持する文字列です。Linux 版 Strata デスクトップの supervisor は、利用者が browser mode を選んだ起動時に App Host の子プロセスへ `STRATA_UI_REASON=chosen` を設定します。App Host は browser mode の場合にこの値を `reason` として読み、`GET /api/app/mode` の JSON に含めます。モデル計算や engine の挙動は制御しません。

## 値と判定

App Host は環境変数を数値や列挙値として parse せず、JavaScript の論理 OR (`||`) で空値を fallback します。

| 環境値 | browser mode での初期 `reason` |
|---|---|
| 未設定 (`undefined`) | `chosen` |
| 空文字 (`''`) | `chosen` |
| 空でない文字列 | その文字列をそのまま保持。trim、大小文字変換、長さ制限、許容値チェックなし |
| browser mode 以外 | `null`。環境値は使わない |

デスクトップ supervisor の browser mode 起動では子プロセスへ `"chosen"` を設定するので、親プロセスに別の値があってもこの値で置き換わります。`STRATA_UI_REASON` 自体が browser mode を選択することはありません。起動モードは `STRATA_UI=browser` または `--browser` で選択されます。

## 有効になる条件

- Linux 版 `apps/desktop` の supervisor が host を起動する経路では、browser mode を選択した場合に限り `STRATA_UI_REASON=chosen` を子プロセス環境に追加します。window mode ではこの変数を設定しません。
- App Host は `STRATA_UI_MODE` が `window` または `browser` のどちらかと一致する場合だけアプリ起動として扱い、`browser` の場合にだけ `STRATA_UI_REASON` を参照します。`STRATA_UI_MODE` の値は大文字小文字を変換しません。無効値なら mode は `null` です。
- supervisor では `STRATA_UI=browser` が初期 browser 選択を設定し、`--browser` はそれを有効化します。`STRATA_UI_REASON` はこの選択に関与しません。
- App Host をデスクトップ supervisor を介さず起動し、`STRATA_UI_MODE=browser` を与えた場合は、継承された `STRATA_UI_REASON`（なければ `chosen`）が初期値になります。Windows/macOS のデスクトップ起動では `main.rs` の host 起動処理はこの変数を明示設定しません。

## 実行時の詳細

App Host の `createAppUi()` が呼ばれるときに `process.env` から一度読み、初期 `mode` と `reason` に保存します。したがって、起動後にプロセス環境だけを変更しても初期 `reason` は再読込されません。`GET /api/app/mode` は現在の state を返します。browser mode への切替を shell が `POST /api/control/ui` で指示した場合は、そちらの request body の `reason` が使われ、`String(why).slice(0, 40)` で最大40文字に切られます。これは環境変数の値判定とは別の実行時更新経路です。

フロントエンドの app mode 型には `reason` フィールドがあります。確認したコードでは `useAppMode()` が `/api/app/mode` をページロードにつき一度取得します。環境値に対する専用ログ、警告、終了、エラー処理はありません。`reason` は API 応答で観測できます。

## 根拠

- `apps/desktop/src-tauri/src/supervisor.rs:43-55` — `STRATA_UI` と `--browser` による起動モード選択。`--browser` は有効化のみ。
- `apps/desktop/src-tauri/src/supervisor.rs:361-365` — Linux supervisor が App Host 子プロセスへ `STRATA_UI_MODE` を渡し、browser 選択時に `STRATA_UI_REASON=chosen` を設定。
- `apps/desktop/src-tauri/src/main.rs:463-468` — App Host の host command は環境を継承し、ここでは `STRATA_UI_REASON` を明示設定しない。browser 選択時の明示設定は Linux supervisor 側。
- `apps/host/server/app-ui.mjs:63-66` — `process.env` を既定入力として mode と reason を初期化し、browser mode 以外では reason を `null` にする。
- `apps/host/server/app-ui.mjs:81-99` — state の返却と、shell による browser 切替時の reason 更新・40文字制限。
- `apps/host/server/index.mjs:1311-1327` — `GET /api/app/mode` と shell 専用 UI 切替 API。
- `apps/host/src/lib/app-mode.ts:4-24` — API 応答型とページロード中の取得・cache。
