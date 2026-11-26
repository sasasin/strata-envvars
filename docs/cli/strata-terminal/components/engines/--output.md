# `strata components engines --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

インストール済み engine の一覧を、人が読む表示か機械処理向けの JSON で出力します。このサブコマンドは engine の切り替えやダウンロードを行わず、一覧表示だけを行います。

## 使い方

```sh
# 端末向けの一覧
strata components engines --output human

# スクリプトから読み取る JSON
strata components engines --output json

# jsonl もこのコマンドでは一覧全体を表す JSON オブジェクト1個を出力する
strata components engines --output jsonl
```

## 値と既定値

- 値は `human`、`json`、`jsonl` に限定されます。省略時は `human` です。
- これら以外の値は `argparse` の choices 検証で拒否され、usage とエラーが表示されます（`terminal/strata_cli/update_cmd.py:56`、`terminal/strata_cli/cli.py:2325-2334`）。
- このサブコマンドの `jsonl` は行ごとのイベント出力ではありません。`json` と同じ分岐で、一覧を包む JSON オブジェクト1個を出力します（`terminal/strata_cli/update_cmd.py:309`、`terminal/strata_cli/update_cmd.py:454-458`）。

## 実行時の動作

`--output` が `json` または `jsonl` なら機械可読モードとなり、`schema_version: 1`、`ok: true` と `list_engines` の戻り値を含むオブジェクトを stdout に出します。`human` では総容量、family ごとの engine、バージョン・容量・backend、使用中・最新版・ローカルビルド・この PC で利用できるかを表示します（`terminal/strata_cli/update_cmd.py:449-468`）。

JSON の一覧には `components_dir`、`families`、`total_bytes`、`serving` が含まれます。各 engine の `fits` や `why_not` などの情報は、検出した hardware と対象 engine の情報から作られます。出力形式自体は `--backend` や `--components-dir` を変えませんが、これらを指定すると一覧対象のディレクトリや適合性判定に使う backend が変わります（`terminal/strata_cli/update_cmd.py:318-324`、`terminal/strata_control/engine_library.py:98-122`、`terminal/strata_control/engine_library.py:152-167`）。

## 適用条件と副作用

一覧処理は engine パッケージを読み取り、ファイル容量や実行適合性を調べます。稼働状況の確認も行います。文書化された処理では一覧のためにファイル変更やダウンロードはしません（`terminal/strata_control/engine_library.py:98-123`、`terminal/strata_control/engine_library.py:139-167`）。

## 出力とエラー

- `human` は人向けの複数行表示、`json` と `jsonl` は stdout に一覧オブジェクトを1個出力し、正常時は終了コード `0` です（`terminal/strata_cli/update_cmd.py:454-469`）。
- 実行中に `ValueError`、`OSError`、`ClientError` などが送出された場合、共通処理は `human` では `strata: ...` を stderr に、機械可読モードでは `schema_version: 1`、`ok: false`、エラー情報を持つ JSON を stdout に出力します。対応する終了コードはエラーに付随する値（`OSError` は `6`）です（`terminal/strata_cli/update_cmd.py:311-316`、`terminal/strata_cli/cli.py:2248-2270`）。個々のファイル状態や OS による具体的なエラー発生条件は、ここでは網羅していません。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における `--output` の値候補と既定値。
- `terminal/strata_cli/update_cmd.py:82-83` — `components engines` の parser 登録と共通オプションの適用。
- `terminal/strata_cli/cli.py:2210-2212`、`terminal/strata_cli/update_cmd.py:307-324` — サブコマンドの dispatch と実行 context の作成。
- `terminal/strata_cli/update_cmd.py:449-469` — 一覧取得後の human / JSON 出力。
- `terminal/strata_control/engine_library.py:98-134`、`terminal/strata_control/engine_library.py:139-167` — engine 情報と適合性・稼働状態の一覧化、および読み取りのみという動作。
- `terminal/strata_cli/cli.py:2248-2270` — 実行中の例外を人向けまたは JSON エラーに変換する共通経路。
