# `STRATA_APP_VERSION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の Host、Desktop shell、Control/CLI を調査。外部 updater の内部動作は対象外。

## 役割

Strata Desktop の Host にアプリ自身のインストール済みバージョンを知らせます。Host はこれをセットアップ状態・更新確認に使い、Control の CLI にも引き継ぎます。単体の `strata update` CLI では、`--app-version` が指定されていない場合のインストール済みアプリ版として使われ、アプリ更新の要否を比較します。

Desktop shell は Host 子プロセス起動時に `STRATA_APP_VERSION` を設定します。Linux の supervisor 経由では Cargo の `CARGO_PKG_VERSION` を設定し、Windows/macOS の Host 起動経路では Tauri の package version を設定します。通常の Desktop 起動では、利用者の同名環境変数よりこの値が優先されます（`apps/desktop/src-tauri/src/supervisor.rs:361`, `apps/desktop/src-tauri/src/main.rs:495-504`, `apps/desktop/src-tauri/src/updater.rs:243-249`）。

## 値と判定

Host の `appVersionFrom()` は値を文字列化して前後空白を除き、次の形式に全体一致する場合だけ採用します: `数字.数字.数字` に、任意で `-` または `+` と英数字・`.`・`+`・`-` の1文字以上を続けた形式です。大文字小文字は問わず、先頭の `v`、空白を含む値、末尾の余分な文字は不一致です（`apps/host/server/app-version.mjs:8-18`）。

| `STRATA_APP_VERSION` | Host の表示・通常更新確認用 `appVersion()` |
|---|---|
| 有効形式 | trim 後の値を使用 |
| 未設定、空文字、空白だけ、不正形式 | `apps/desktop/src-tauri/Cargo.toml` の `version` を読み、同じ形式ならそれを使用 |
| Cargo.toml が読めない、またはその `version` が形式不一致 | `dev` |

このフォールバックは Host の `appVersionFrom()` に限られます。パッケージ版 Host の Control 更新確認経路では `process.env.STRATA_APP_VERSION || null` が渡されるため、空文字は未設定扱いになり、Host の Cargo.toml fallback は使われません（`apps/host/server/index.mjs:129-130,1372-1373`）。

CLI の `strata update` は `--app-version` の非空文字列を環境変数より優先します。CLI 引数が未指定または空文字なら `os.environ.get("STRATA_APP_VERSION")` を使い、環境変数もなければ `None` です。ここでは値を trim したり、Host と同じ形式検証をしたりしません（`strata_cli/update_cmd.py:49-62,183-206`）。

## 有効になる条件

- Desktop Host では、`/api/setup` が `setupState().app.version` を返す時点で `appVersionFrom()` を呼びます。パッケージ版では Desktop shell が設定した値が有効です。source checkout など shell の設定がない場合は Cargo.toml、さらに `dev` の順で決まります（`apps/host/server/index.mjs:129-130,290-301`）。
- パッケージ版の `GET /api/updates/check` で Control が使える場合、環境変数値を `checkComponentUpdates()` から Control の `strata update --check` に渡します。Control の子プロセス環境は親環境をコピーするので、この変数も継承されます（`apps/host/server/index.mjs:1372`, `apps/host/server/updates.mjs:52-60`, `apps/host/server/control-runtime.mjs:89-103,124-130,183-186`）。
- Control がない source checkout の更新確認では `setupState().app.version` を使い、`appVersionToShow()` でアプリ版が `dev` または利用可能でない場合に Control の版を選びます。これは `/api/updates/check` の別経路です（`apps/host/server/index.mjs:1372-1373`, `apps/host/server/app-version.mjs:21-25`）。
- 単体 CLI では `strata update` / `strata components update` の `--app-version` と `STRATA_APP_VERSION` が `updater.Context.app_version` に入ります。フィードに対象 platform のアプリ項目がある場合、値なしなら installed version は不明 (`unknown-installed`)、値があればフィード版と比較して `available` または `current` になります（`strata_cli/update_cmd.py:49-63,183-206`, `strata_control/updater.py:1402-1415`）。

## 実行時の詳細

Host の `appVersion()` はキャッシュされません。`setupState()` が呼ばれるたびに環境値を判定し、無効・未設定の場合は Cargo.toml の読み込みを試みます。通常、プロセス起動後の環境変更も次の呼び出しで反映されます（`apps/host/server/index.mjs:129-130,290-301`, `apps/host/server/app-version.mjs:10-18`）。ただし Desktop shell が起動時に渡した子プロセス環境は、親プロセスの環境をその場で再読込する仕組みではありません。

パッケージ版の更新確認は Host が Control の `update --check` を実行する際に `--app-version` を付けます。単体 CLI では app-version は `Context` 作成時に読み取られ、その値がフィード内のアプリ版比較に使われます。比較時の `app_version_key()` は `-` より前を通常のバージョンとして検査し、末尾の prerelease 部分は同じ数値版より低く扱います。不正値は `FeedError` になり、CLI は stderr に `strata: ...`（人間向け出力）または JSON エラーを出して終了コードを返します。フィードにアプリ項目がない場合はこの比較に入りません（`strata_control/feed.py:62-75`, `strata_control/updater.py:1402-1415`, `strata_cli/update_cmd.py:187-206,235-260`）。

パッケージ版 Host の `native-control.mjs` は起動時の環境値を未検証のまま更新ログに表示し、アプリ更新 job に `appUpdateFrom` として保存します。次回起動時、保存版と現在版が異なれば更新完了とし、同じなら更新失敗として表示します。値がないと `unknown` ログとなり、版の一致・不一致によるこの判定は行われません（`apps/host/server/native-control.mjs:43-49,433-449`）。

## 根拠

- Desktop shell から Host への設定: `apps/desktop/src-tauri/src/supervisor.rs:353-365`, `apps/desktop/src-tauri/src/main.rs:495-505`, `apps/desktop/src-tauri/src/updater.rs:243-249`。
- Host の形式判定・fallback と setup state: `apps/host/server/app-version.mjs:8-18`, `apps/host/server/index.mjs:129-130,290-301`。
- パッケージ版と checkout の更新確認分岐: `apps/host/server/index.mjs:1368-1373`, `apps/host/server/updates.mjs:52-60`, `apps/host/server/app-version.mjs:21-25`。
- Control への環境継承と `--app-version` 生成: `apps/host/server/control-runtime.mjs:89-103,124-130,171-195`。
- CLI の優先順位と app version の比較・無効値エラー: `strata_cli/update_cmd.py:49-63,183-206,235-260`, `strata_control/updater.py:1402-1415`, `strata_control/feed.py:62-75`。
- Host の更新 job ログ・再起動後の状態判定: `apps/host/server/native-control.mjs:43-49,433-449`。
