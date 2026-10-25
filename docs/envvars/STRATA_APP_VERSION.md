# `STRATA_APP_VERSION`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

デスクトップアプリのバージョンを App Host に伝えます。Host はこれをセットアップ状態と更新確認に使い、Control の `strata update --check` にも渡します。engine 自体のバージョンや実行条件は変更しません。

## 値と判定

Host の表示用バージョン取得 (`appVersionFrom`) と、Control CLI に渡す値では処理が異なります。

| 経路 | 値の扱い |
|---|---|
| `appVersionFrom`（`/api/setup` などの `setupState`） | `null` / 未設定は空文字として扱い、前後空白を trim。`数字.数字.数字` に任意の `-` または `+` suffix（英数字、`.`、`+`、`-`）を付けた全体一致だけを受理。空文字・不一致なら checkout 内の `apps/desktop/src-tauri/Cargo.toml` を読む。そこから同じ形式の `version = "..."` が得られなければ `dev`。 |
| `/api/updates/check`（Control がある packaged 経路） | `process.env.STRATA_APP_VERSION || null` をそのまま渡す。未設定または空文字は `null`、空白のみや不正形式の非空文字列は trim・検証されず渡る。 |
| Control CLI の `strata update` / `strata components update` | `--app-version` が truthy ならそれを使い、そうでなければ `os.environ[STRATA_APP_VERSION]` を使う。CLI では環境変数の trim や形式検査をしない。 |

Python 側でアプリ版を比較するとき、`app_version_key` は `-` suffix の pre-release を受け付け、同じ数値版の通常版より下に並べます。`+` suffix はこの比較形式では受理されず、feed の版比較時に `FeedError` になります。Node の表示用形式判定とは許容形式が一致しません。

## 有効になる条件

- デスクトップアプリから起動した Host では、親プロセスがこの変数をセットします。Linux の supervisor は `CARGO_PKG_VERSION` を設定し、Windows/macOS の Host 起動は Tauri の package version を設定します。
- ソース checkout から Host を直接起動し、変数が unset / 空 / 不正な場合、表示用の値は Cargo.toml の version に fallback します。該当ファイルを読めない、または version が形式に合わない環境では `dev` です。
- Control が利用できない場合の `/api/updates/check` は、表示用 `appVersion()` と native の version を `appVersionToShow` に渡します。`dev` は実バージョン扱いされず、native version があればそちらが表示用 fallback になります。
- `STRATA_APP_VERSION` が有効な値でも、更新確認に渡されるだけで、ユーザーが更新確認を呼ばない限り feed 確認は発生しません。`createControl().updateCheck()` は `/api/updates/check` から呼ばれ、`--check` と `--app-version` を付けて Control CLI を起動します。

## 実行時の詳細

`appVersionFrom` は呼び出すたびに渡された env object を読む。Host では `appVersion()` が `setupState()` 内で呼ばれるため、表示値はその状態を作るたびに取得され、static cache されません。デスクトップ shell は子 Host の起動時に値を設定するので、通常は親アプリの package version が渡ります。

Control の更新確認経路では、`control-runtime.mjs` が `env.STRATA_APP_VERSION` を `--app-version` に追加し、Python の `update_cmd.py` がそれを `Context.app_version` に格納します。updater は feed にアプリ項目があり、その platform 用 entry がある場合に限り、`ctx.app_version` と feed version を比較して `available` / `current` を返します。installed version が falsy なら `unknown-installed` です。アプリのインストーラをダウンロードする `strata update --app` もこの値を参照しますが、通常の app update check とは別の明示的な CLI 操作です。

`appVersionFrom` の fallback は「不正な env 値を無視して Cargo.toml を読む」一方、packaged 更新確認は不正な非空 env 値も CLI へ渡します。後者では比較時の形式エラーになり得ます。空文字は両方で fallback / 未指定相当ですが、空白だけの値は前者では trim 後に fallback、後者では truthy のためそのまま渡されます。

## 根拠

- `apps/host/server/app-version.mjs:8-18` — Node 側の許容形式、trim、Cargo.toml fallback、`dev` fallback。
- `apps/host/server/app-version.mjs:21-25` — 表示値における `dev` の扱いと native version fallback。
- `apps/host/server/index.mjs:126-127,270-281,1329-1331` — Host 起動時の説明、setup state の取得、更新 endpoint の分岐。
- `apps/desktop/src-tauri/src/supervisor.rs:352-365` — supervisor が Host 子プロセスへ `CARGO_PKG_VERSION` を設定。
- `apps/desktop/src-tauri/src/main.rs:480-490` と `apps/desktop/src-tauri/src/updater.rs:233-239` — Windows/macOS の Host 起動と package version の環境設定。
- `apps/host/server/control-runtime.mjs:160-180` — update check / update 呼び出しで環境値を `--app-version` に渡す。
- `strata_cli/update_cmd.py:42-59,163-185` — CLI option と、引数または環境から `Context.app_version` を決める規則。
- `strata_control/feed.py:40,59-72` — Python updater 側の版形式と pre-release 比較規則。
- `strata_control/updater.py:1210-1223,1274-1286` — app update 判定と `--app` 時の更新処理。
- `apps/host/server/updates.mjs:47-60,73-91` — packaged Host が Control の結果を UI 用の app status にする処理。
