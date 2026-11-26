# `--app-version`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--app-version` |
| 別名 | なし |
| 値 | インストール済みデスクトップアプリの版を表す文字列 |

## 役割

更新フィードにアプリ版がある場合、フィードの版と比較する「インストール済み版」を Strata に伝えます。比較結果はアプリ更新の確認表示と、`--app` で installer を取得するかの判定に使われます。この値を指定してもアプリ更新は有効にならず、installer の取得には別途 `--app` が必要です（`terminal/strata_cli/update_cmd.py:62-64,323-325,361-372`、`terminal/strata_control/updater.py:2002-2015,2018-2025`）。

## 使い方

```sh
# フィードを確認し、インストール済みアプリ版との比較結果を表示する（installer は取得しない）
strata update --check --app-version 0.2.0

# アプリ installer も取得・検証する（インストール自体は行わない）
strata update --app --app-version 0.2.0
```

## 値と既定値

`--app-version` は値を1つ取ります。parser には型変換や選択肢の制限がなく、既定値は `None` です（`terminal/strata_cli/update_cmd.py:59-65`）。実行時は truthy な CLI 値を優先し、それが未指定または空文字なら環境変数 `STRATA_APP_VERSION` を使います。両方とも未設定なら `None` です（`terminal/strata_cli/update_cmd.py:323-325`）。環境変数の詳しい仕様は [`STRATA_APP_VERSION`](../../../envvars/STRATA_APP_VERSION.md) を参照してください。

アプリ版の比較に使われる値は、数字3区分または4区分の版（例 `0.2.0`、`0.2.0.1`）に、任意で `-` と英数字・ドットからなる prerelease suffix を付けた形式です（例 `0.2.0-beta`）。基底版は `\d+\.\d+\.\d+(?:\.\d+)?` に一致する必要があります。比較では各版を最大4区分にゼロ埋めし、同じ基底版なら prerelease 付きが通常版より小さいものとして扱います（`terminal/strata_control/feed.py:45,69-82`）。`+build` 形式はこの比較関数では受理されません。

値の検査は parser 時ではなく、アプリ版比較に到達したときに行われます。フィードにアプリがない場合、または実行 platform 用 installer がない場合は比較されません。空文字は CLI から渡しても環境変数へ fallback するため、空文字そのものを「インストール済み版」として渡せません（`terminal/strata_control/updater.py:2002-2015`、`terminal/strata_cli/update_cmd.py:323-325`）。

## 実行時の動作

`strata update --check` は署名付きフィードを読み、アプリ版が指定されていれば offered 版との比較結果をレポートします。これは installer をダウンロードしませんが、確認結果を `last_check` として状態に保存します（`terminal/strata_cli/update_cmd.py:361-367`、`terminal/strata_control/updater.py:778-789`）。

通常更新では `--app` がある場合に限りアプリ installer の処理が追加されます。指定版がフィード版より古ければ `available`、同じか新しければ `current` となり、`current` なら取得を行いません。インストール済み版が未知なら `unknown-installed` として取得対象になります（`terminal/strata_control/updater.py:2002-2015,2018-2025,2119-2122`）。取得した installer は SHA-256 と minisign 署名を検証して `.updates/app` 配下へ置きますが、Terminal はアプリをインストールしません（`terminal/strata_control/updater.py:2018-2021,2026-2049`）。

## 適用条件と副作用

この値がアプリ更新判定に影響するのは、フィードにアプリ項目があり、現在の platform に対応する installer がある場合です。エンジンや Control の版比較には使われません（`terminal/strata_control/updater.py:2002-2015`）。`--app-version` だけでは installer を取得せず、`--app` と組み合わせた場合のみ取得処理が実行されます。アプリ版が未知のときは `--app` により最新版候補を取得しますが、取得したファイルのインストールは別操作です（`terminal/strata_cli/update_cmd.py:63-64,371-372`、`terminal/strata_control/updater.py:2022-2049`）。

## 出力とエラー

`--check` の人間向け出力では、既知のアプリ版を `installed -> offered` と状態付きで示します。版が不明なら、Terminal はインストール済みアプリ版を判定できない旨を示します（`terminal/strata_cli/update_cmd.py:217-247`）。不正な版が比較対象になった場合は `FeedError` となり、既定の終了コード `5` で失敗します。人間向け出力は stderr の `strata: <エラー>`、JSON/JSONL 出力ではエラーオブジェクトになります（`terminal/strata_control/feed.py:50-55,69-82`、`terminal/strata_cli/update_cmd.py:307-316,378-384`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-75`: `strata update` と `strata components update` の parser 定義。後者にも同名オプションがあるが、本書のスコープは索引上の `strata update`。
- `terminal/strata_cli/update_cmd.py:307-325,361-377`: 環境変数 fallback、Context への設定、確認と更新の分岐。
- `terminal/strata_control/feed.py:45,69-82`: 比較対象の版形式・比較キー。
- `terminal/strata_control/updater.py:778-789,1987-2049,2109-2139`: 確認レポート、アプリ版判定、installer の取得・検証、実行順。
