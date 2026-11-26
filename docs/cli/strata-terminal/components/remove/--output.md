# `strata components remove --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` |

## 役割

削除結果の表示形式を選ぶ。`json` と `jsonl` はこのサブコマンドではどちらも機械可読出力として扱われ、削除成功時に JSON オブジェクトを stdout に1つ出力する。エンジンの選択・削除対象・削除可否はこの値では変わらない。

## 使い方

```sh
strata components remove 0.1.54 --output json
```

指定した版のエンジンを削除し、結果を JSON で受け取る。対象の版が複数のフォルダーに一致する場合はフォルダー名を指定する。

## 値と既定値

- 省略時は `human`。
- `human`、`json`、`jsonl` のいずれかを1つ指定する。別の値は argparse の選択肢検証で拒否され、usage とエラーになり、終了コードは2。
- オプションを複数回指定したときの扱いは、argparse の通常の単一値引数に従い、最後に指定した値が使われる。

## 実行時の動作

parser は `components remove` に共通オプションを登録する。実行時に `json` / `jsonl` を `machine=True` と判定し、インストール済みエンジン一覧から位置引数の版またはフォルダー名と、任意の `--family` に一致する対象を検索して削除する。`human` では削除した版と解放容量を文章で stdout に表示し、機械出力では `schema_version: 1`、`ok: true` と削除結果のフィールドを含む JSON オブジェクトを stdout に出す。

このコマンドでは `jsonl` も `json` と同じ成功出力経路を通り、行ごとの進捗イベントは出さない。`--output` は削除処理の対象や副作用に影響しない。

## 適用条件と副作用

削除対象は `strata components remove` の位置引数 `engine` で指定する。`--family` には `qwen` またはインストール済みモデル形状に対応する `shape:<shape>` を指定できる。省略時は全 family から検索され、同名・同版が複数あればフォルダー名の指定が必要になる。

削除対象が現行エンジン、実行中プロセスが使用中のエンジン、または未インストールのエンジンなら削除されない。実際の削除では更新ロックを取り、対象フォルダーを `.deleting-*` に rename してから削除を試みる。モデルと設定は削除対象外。`--output` の変更自体はファイルやプロセスに副作用を起こさない。

## 出力とエラー

- `human` の成功時は `Engine <版> deleted (<容量> freed). Models and settings were not touched.` を stdout に出す。
- `json` / `jsonl` の成功時は成功結果を JSON オブジェクト1件として stdout に出す。
- 処理中に捕捉された `UpdateError` は、`human` では `strata: <メッセージ>` を stderr に、機械出力では `schema_version: 1`、`ok: false`、エラーコードとメッセージを含む JSON を stdout に出す。対象がない、曖昧、削除禁止の対象などは終了コード2。rename に失敗した場合は「何も変更していない」旨を含むエラーと終了コード6。
- 引数の値が選択肢外の場合は削除処理に入らず、argparse が終了コード2で拒否する。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-57` — 共通 parser における値の選択肢と `human` 既定値。
- `terminal/strata_cli/update_cmd.py:88-91` — `remove` サブコマンド、位置引数、`--family`、共通オプションの登録。
- `terminal/strata_cli/update_cmd.py:307-318` — `json` / `jsonl` を機械出力扱いにする判定とエラー出力。
- `terminal/strata_cli/update_cmd.py:341-342`、`449-470` — `remove` の実行経路と対象エンジンの検索。
- `terminal/strata_cli/update_cmd.py:496-501` — 削除呼び出し後の human / JSON 成功出力。
- `terminal/strata_control/engine_library.py:184-197` — 版・フォルダー名の検索、未一致・曖昧時のエラー。
- `terminal/strata_control/engine_library.py:317-366` — 削除条件、rename と削除、状態記録、削除結果。
