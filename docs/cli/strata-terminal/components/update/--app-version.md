# `--app-version`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの作業ツリーは clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--app-version` |
| 別名 | なし |
| 値 | インストール済み Strata アプリのバージョン文字列 |

## 役割

更新フィードにあるデスクトップアプリ版と、インストール済みアプリ版を比較するための値です。更新先のバージョンを選ぶオプションではありません。`strata update` にも同じ引数が定義されていますが、この文書は索引に記載された `strata components update` のスコープを扱います（`strata_cli/update_cmd.py:42-56`）。

## 使い方

```sh
strata components update --check --app-version 0.2.0
strata components update --app --app-version 0.1.9
```

`--check` はフィードの内容と更新見込みを表示し、アプリインストーラの取得を行いません。実際にアプリのインストーラ取得も行う場合は `--app` を指定します（`strata_cli/update_cmd.py:50-56, 203-209, 213`; `strata_control/updater.py:624-632, 1274-1285`）。

## 値と既定値

- 値は必須の文字列で、parser では `default=None` として受け取ります。未指定、または空文字列を指定した場合は `STRATA_APP_VERSION` 環境変数の値にフォールバックします。空でないコマンドライン値は環境変数より優先されます（`strata_cli/update_cmd.py:27, 54, 182-184`）。
- parser 自体は形式を検証しません。アプリ版の比較時には、数値部分が `X.Y.Z` または `X.Y.Z.W` 形式である必要があります。末尾に `-` と英数字・ピリオドからなるプレリリース識別子を付けられます（例: `0.2.0-beta`）。比較では識別子の文字列同士は区別せず、同じ数値部分のプレリリース版を通常版より低く扱います（`strata_control/feed.py:40, 59-72`）。
- 空でない値の前後空白は除去されません。形式不正の値は、フィードにアプリ項目があり、この PC 向け配布物もある場合に比較処理で `FeedError` になります（`strata_control/updater.py:1210-1223`; `strata_control/feed.py:59-72`）。

## 実行時の動作

parser が値を受け取り、`run` が CLI 値または `STRATA_APP_VERSION` を `updater.Context.app_version` に渡します（`strata_cli/update_cmd.py:42-56, 163-184`; `strata_control/updater.py:316-331`）。

- `--check` ではフィードのアプリ版との比較結果がレポートに含まれ、human 出力ではインストール済み版・提供版・状態が表示されます。JSON 出力にも同じ `app` レポートが含まれます（`strata_control/updater.py:624-639, 1210-1223`; `strata_cli/update_cmd.py:132-159, 203-209`）。
- 通常の更新では `--app` がない限りアプリ更新処理は実行されず、この値はアプリのダウンロード判定に使われません。`--app` を指定すると、値が提供版より古ければ取得対象となり、同じか新しければアプリ処理はスキップされます。インストール済み版が不明なら `unknown-installed` として取得対象になります（`strata_control/updater.py:1210-1233, 1274-1288`）。
- 値はダウンロード先のアプリ版を選びません。取得対象は署名済みフィードのアプリ項目と、この PC の platform に対応する配布物です。取得時はアーカイブを検証して `.updates/app` 以下へ置き、Terminal CLI 自身はインストールしません（`strata_control/updater.py:1226-1257`）。
- `--check` は更新結果を状態ファイルに記録します。アプリが `available` と判定された場合、提供版が `last_check.app` に記録されます（`strata_control/updater.py:624-639`）。

## 適用条件と副作用

フィードにアプリ項目がない場合は `not-in-feed`、この PC の platform 向け配布物がない場合は `none-for-this-pc` となり、インストール済み版の比較は行いません（`strata_control/updater.py:1210-1218`）。

`--app` による取得では、フィードの署名済み SHA-256 とアプリ更新用 minisign 署名を検証してからファイルを `.updates/app` に保存します。検証用公開鍵がない場合は終了コード 5 で拒否されます。これは `--app-version` 自体の副作用ではなく、アプリ取得を有効にした場合の処理です（`strata_control/updater.py:1226-1257`）。

## 出力とエラー

形式不正な値はアプリ版比較時に `FeedError`（既定終了コード 5）となります。人向け出力では `strata: <エラー>` を stderr に出し、JSON/JSONL 指定時はエラーオブジェクトを stdout に出します（`strata_control/feed.py:44-49, 59-72`; `strata_cli/update_cmd.py:163-172, 225-230`）。`--check` で比較を行う条件を満たさない場合や、通常更新で `--app` を付けない場合には、この値の形式検証は発生しません（`strata_control/updater.py:1210-1223, 1274-1285`）。

## 根拠

- parser 定義・既定値・環境変数へのフォールバック: `strata_cli/update_cmd.py:27, 42-56, 163-184`
- CLI コマンドの振り分け: `strata_cli/cli.py:2135-2137`
- バージョン形式と比較規則: `strata_control/feed.py:40, 59-72`
- フィード内アプリ版の検証: `strata_control/feed.py:243-263`
- check レポート、状態記録、アプリ判定: `strata_control/updater.py:624-639, 1210-1223`
- アプリ取得条件と保存・署名検証: `strata_control/updater.py:1226-1257, 1274-1288`

調査は上記 commit のソース checkout に限定しました。既存バイナリの `--help` や Release 配布物は実行・照合していません。
