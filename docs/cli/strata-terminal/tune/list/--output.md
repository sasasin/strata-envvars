# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune list` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

記録済み tuning job の一覧を、人が読むテキストまたは JSON で標準出力へ出します。表示形式だけを選び、job の作成・更新・削除は行いません。

## 使い方

```sh
strata tune list
strata tune list --output json
```

## 値と既定値

`--output` は `human` / `json` のみを受け付けます。省略時は `human` です。別の値や値なしは parser の選択肢制約で拒否されます。短縮 alias はありません。

## 実行時の動作

`human` では job ごとに ID の先頭12文字、状態、backend、objective を1行ずつ表示します。job がなければ `no tuning jobs recorded` と表示します。`json` では `{"schema_version":1,"ok":true,"jobs":[...]}` 形式を出し、各 job は `id`、`state`、`backend`、`objective` を含みます。JSON と人向けテキストはいずれも標準出力です。

一覧対象の state root は `--state-dir`、環境変数 `STRATA_TUNE_DIR`、既定のユーザー state directory 配下の `tuning/` の順に選ばれます。`--output` はこの選択に影響しません。root がディレクトリでなければ空の一覧として扱われます。ディレクトリ直下の各項目にある `job.json` を読み、ファイルを読めない場合または JSON として不正な場合はその job を一覧から飛ばします。

## 適用条件と副作用

このオプションは `strata tune list` の parser に属します。他の `strata tune` サブコマンドとは別スコープです。出力先ファイルを作成せず、選択した state root の既存 `job.json` を読むだけです。

## 出力とエラー

選択肢にない値や値の欠落は argparse の引数エラーになります。job ファイル単位の `OSError` と JSON decode error は握りつぶされ、その項目だけ表示されません。通常経路では成功終了コード `0` を返します。state root の走査で起きるエラーの個別表示・終了コードは、この一覧分岐内では処理されていないため、ここでは断定しません。

## 根拠

- `strata_cli/cli.py:482-484` — `list` parser の `--state-dir` と `--output` 定義、値の選択肢と既定値。
- `strata_cli/cli.py:1643-1650` — `--state-dir`、`STRATA_TUNE_DIR`、既定 state directory の解決順。
- `strata_cli/cli.py:1655-1676` — `job.json` の列挙・読み込み、無効ファイルの除外、human/JSON の出力分岐と成功終了。
- `strata_cli/cli.py:535-542` — JSON 成功レスポンスの `schema_version` / `ok` 包装と標準出力。
- `strata_control/paths.py:13-21` — OS ごとの state base directory。
