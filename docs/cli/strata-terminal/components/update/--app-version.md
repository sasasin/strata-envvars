# `strata components update --app-version`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--app-version` |
| 別名 | なし |
| 値 | 値を取る。インストール済みデスクトップアプリの版文字列 |

## 役割

更新フィードが提示するデスクトップアプリ版と、インストール済みアプリ版を比較するための値です。配布される版を指定するオプションではありません。`--app` と併用すると、比較結果に応じてアプリのインストーラーをダウンロード・検証します。

## 使い方

```sh
# アプリ版の更新状況を確認する（フィードを読み、確認結果を状態に記録する）
strata components update --check --app-version 0.2.12

# アプリのインストーラーも取得する。インストール作業は取得後に別途行う
strata components update --app --app-version 0.2.12
```

## 値と既定値

- 引数 parser は値を文字列として受け取り、既定値は `None` です。CLI で指定された値が truthy なら環境変数 `STRATA_APP_VERSION` より優先されます。未指定または空文字なら環境変数の値を使い、環境変数も未設定なら `None` になります。環境変数については [`STRATA_APP_VERSION`](../../../../envvars/STRATA_APP_VERSION.md) を参照してください。
- 比較時の版は、数字3区分または4区分（例: `0.2.12`、`0.2.12.1`）で、インストール済み版に限って `-beta` のような英数字・ピリオドのプレリリース接尾辞も受理します。プレリリースは同じ数字部分の通常版より低く扱われます。`+build` 形式は受理されません。
- CLI parser 段階では形式検査しません。比較が行われるときに形式が不正なら `FeedError` となり、終了コード5で失敗します。空の CLI 値は falsy のため環境変数へフォールバックします。

## 実行時の動作

`strata components update --check` はアプリ版の状態も含めて確認し、通常の確認出力または `--output json` / `jsonl` の結果に反映します。確認処理はフィードをダウンロードする一方、エンジンや Control の更新は行いません。確認結果の `last_check` はコンポーネント状態に保存されます。

通常の更新では `--app-version` だけではアプリのインストーラーを取得しません。取得処理には `--app` が必要です。既知のインストール版よりフィードの版が新しければ取得し、同じか古ければアプリ分は `current` として取得しません。版が不明（値が未設定または空）なら、`--app` を指定した際にインストーラー取得の対象になります。取得後もアプリ自体はインストールせず、検証済みインストーラーをコンポーネントディレクトリ内の `.updates/app` に置きます。

## 適用条件と副作用

- フィードにアプリ項目があり、現在のプラットフォーム用エントリーがある場合に、インストール版との比較が行われます。フィードにアプリがない、またはそのプラットフォーム用エントリーがない場合は比較されません。
- `--app` による取得では、アプリ更新用の公開鍵がビルドに含まれていない場合、インストーラーをダウンロードせずエラーコード5になります。ダウンロード後の minisign 検証に失敗した場合、取得ファイルを削除してエラーコード5になります。取得先で同名ファイルがある場合は原子的な置換が行われます。
- `--app-version` は `strata update` にも別途登録されています。索引上は別スコープです。この文書は `strata components update` のオプションを対象とします。

## 出力とエラー

不正な版文字列を比較しようとした場合、通常出力では `strata: <エラー>` を標準エラーに出し、終了コード5を返します。`--output json` または `jsonl` では、CLI の共通失敗形式 `{"schema_version":1,"ok":false,"error":{"code":5,"message":"..."}}` を標準出力に出します。アプリのダウンロード自体が失敗した場合も、更新結果に失敗として含まれ、終了コードは失敗コードになります。

## 根拠

- `terminal/strata_cli/update_cmd.py:70-79` — `strata components update` parser の登録と `--app-version` の既定値。`terminal/strata_cli/update_cmd.py:60-69` — `strata update` における別スコープの登録。
- `terminal/strata_cli/update_cmd.py:323-325` — CLI 値、環境変数の順に `Context.app_version` を設定。
- `terminal/strata_control/feed.py:45,69-82` — 版の形式、比較キー、プレリリースの扱い。
- `terminal/strata_control/updater.py:2002-2015` — アプリのフィード項目・プラットフォーム判定、未知版の扱い、インストール版と提示版の比較。
- `terminal/strata_cli/update_cmd.py:361-377`、`terminal/strata_control/updater.py:778-789` — 確認モードの出力経路と `last_check` の保存。
- `terminal/strata_control/updater.py:50,191-193,2018-2049,2118-2139`、`terminal/strata_cli/update_cmd.py:371-390` — `.updates` の場所、アプリ更新の実行条件、署名検証・取得先、失敗の集約と CLI エラー処理。
