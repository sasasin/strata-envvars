# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`strata runtime` の説明と直下のサブコマンド一覧を表示します。ここでの help は親コマンド専用です。`start`、`status` など個別サブコマンドのオプション一覧は、それぞれ `strata runtime <サブコマンド> --help` で表示します（索引の [各サブコマンド文書](../../README.md) を参照）。

## 使い方

```sh
strata runtime --help
```

短縮形も同じです。

```sh
strata runtime -h
```

## 値と既定値

値は取りません。`strata_cli/cli.py` は `runtime` を `argparse` の `add_parser` で登録し、独自の `-h` / `--help` 定義や `add_help=False` を指定していません。そのため Python `argparse` の標準 help action が有効です。親 parser に追加のユーザー定義オプションはありません。子 parser は別々に作られ、それぞれ独自の help を持ちます（`strata_cli/cli.py:197-203`）。

## 実行時の動作

help action は解析時に説明・usage・`runtime` 直下の `start`、`status`、`verify`、`stop`、`cleanup`、`restart` の一覧を標準出力へ表示して終了します。親 parser の説明は、`runtime start` がバックグラウンドサービスを開始し、`runtime stop` または `--die-with-pid` の指定プロセス終了まで動作すること、および `strata serve` がフォアグラウンド形式であることを記述しています（`strata_cli/cli.py:197-202`）。

通常の CLI 起動では parser 構築後に引数解析します（`strata_cli/cli.py:2217-2225`）。この action で終了するため、`_run()` の runtime 実行処理やサーバー操作には進みません（dispatch は `strata_cli/cli.py:1331-1346`、`strata_cli/cli.py:2119-2120`）。Windows では引数解析より前にプロセスの token default owner / DACL をユーザー向けに設定しようとしますが、これは `--help` 固有の動作ではなく、通常の CLI 起動共通の処理です。Windows 以外では即座に `False` を返します（`strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-357`）。

`runtime` のサブコマンド parser は `required=True` です（`strata_cli/cli.py:202`）。したがって `strata runtime` のみを実行するとサブコマンド不足として parser error になります。親の `--help` / `-h` はその必須条件を満たす前に help 表示で終了する用途です。

## 適用条件と副作用

子コマンドを指定しない `strata runtime` スコープに適用されます。値を受け取らず、設定ファイルや環境変数との優先順位もありません。ソース上、help 表示から runtime の起動・停止・検証・cleanup を呼ぶ経路は確認できません。通常の argparse help action は usage/help を表示して正常終了します。親コマンド名や引数に誤りがある場合は argparse のエラー経路となり、help action とは別です。

## 根拠

- `strata_cli/cli.py:197-202` — `runtime` 親 parser、説明、必須サブコマンド parser。
- `strata_cli/cli.py:203-254` — 子 parser の登録と親子の scope。
- `strata_cli/cli.py:2217-2225` — CLI の parser 構築と引数解析の順序。
- `strata_cli/cli.py:1331-1346`、`strata_cli/cli.py:2119-2120` — runtime 処理の dispatch。
- `strata_control/private_files.py:349-357` — 起動時の Windows 専用 token default 設定処理。
