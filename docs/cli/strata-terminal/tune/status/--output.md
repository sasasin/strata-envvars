# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune status` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

保存済み tuning job の状態を人向けの要約、または機械処理向け JSON で表示します。このオプションは表示形式を選び、対象 job の実行状態や保存内容を変更しません。

## 使い方

```sh
strata tune status JOB_ID --output json
```

`JOB_ID` は status を調べる job の ID です。`--output` を省略した場合は `human` です。

## 値と既定値

- `human`: 既定値です。job ID と state を表示し、plan の backend/objective、report があれば測定指標、試行数、baseline、recommendation または理由、失敗 trial を標準出力に表示します。
- `json`: `schema_version: 1`、`ok: true`、および job の保存データ全体を `job` に含む JSON オブジェクトを標準出力へ1件出力します。
- それ以外の値は `argparse` の `choices` 制約で拒否されます。値は必須で、同じオプションを複数回指定した場合の専用処理はありません（通常の `argparse` の値処理に従います）。

## 実行時の動作

`--output` の値を `machine` として判定し、status handler の出力分岐に渡します。job は `<state-dir>/<JOB_ID>/job.json` から読み込みます。state directory は `--state-dir` が指定されていればその値、なければ `STRATA_TUNE_DIR`、どちらもなければ OS ごとの Strata state base 下の `tuning/` です。JSON 形式を選んでもこの場所の選択や読み込み内容は変わりません。

`human` 形式は保存データの一部を整形します。`json` 形式は `job.json` の読み込み結果を丸ごと `job` に格納し、成功時は終了コード `0` です。status handler は job ファイルの存在確認と読み込みだけを行い、チューニングを再実行したり job を書き換えたりしません。

## 適用条件と副作用

`--output` は `strata tune status` parser に属します。`strata tune` 配下の他サブコマンドは別 parser 設定であり、同名でも個別に定義されています。status 自体はローカル state の job record を読むコマンドで、ネットワーク・engine・GPU 実行はこの経路にありません。ファイルアクセス権などに起因する OS エラーは通常の読み込み失敗経路になります。

## 出力とエラー

- job が見つからない場合は終了コード `2`。human 形式では `strata: no tuning job <JOB_ID>` を標準エラーへ出し、JSON 形式では `{"schema_version":1,"ok":false,"error":{"code":2,"message":"no tuning job <JOB_ID>"}}` を標準出力へ出します。
- job JSON の構文エラーは `ValueError` として捕捉され、選択した形式に応じたエラー出力になります（通常の終了コードは `2`）。ファイル操作等の `OSError` は終了コード `6` のエラー経路です。
- 不正な `--output` 値は handler に入る前に parser が拒否し、argparse の usage/error 表示と終了コード `2` になります。

## 根拠

- `strata_cli/cli.py:477-480` — `status` parser、位置引数 `job_id`、`--state-dir`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:1643-1650` — `--state-dir`、`STRATA_TUNE_DIR`、既定 state base の優先順。
- `strata_cli/cli.py:1678-1706` — job ファイルの選択・読込、JSON と human の出力内容、および job 不在時の終了コード。
- `strata_control/paths.py:13-21` — OS ごとの per-user state base の解決。
- `strata_cli/cli.py:527-542` — machine error / success の出力先、JSON envelope と終了コード。
- `strata_cli/cli.py:2166-2183` — `ValueError` と `OSError` の捕捉およびエラーコード処理。
- `strata_cli/cli.py:2223-2237` — parser 実行後に command handler へ進む経路。

調査範囲はこの checkout のソースです。CLI help の実行や Release 配布物との照合は行っていません。
