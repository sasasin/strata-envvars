# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示する argparse 標準 action。 |

## 役割

`strata ops` のサブコマンド一覧と使用法を表示します。この文書の対象は `ops` 親コマンドです。各サブコマンドのヘルプは別スコープです（例: `strata ops run --help`）。

## 使い方

```sh
strata ops --help
strata ops -h
```

## 値と既定値

値は不要です。`ops` parser は `add_help=False` を指定せず生成されるため、`argparse` の既定のヘルプ action として `-h` と `--help` が使えます。`--help=...` のような値指定はありません。

## 実行時の動作

表示されるヘルプには `ops` の説明と `init`、`list`、`create`、`show`、`edit`、`set`、`history`、`rollback`、`plan`、`run`、`runs`、`result` のサブコマンドが含まれます。ヘルプ action は parser が引数を解析している間に表示と正常終了を行うため、`_run()` の `ops` 分岐やレシピ・実行履歴の処理には進みません。

## 適用条件と副作用

`strata ops` を起動したときに適用されます。ops のレシピやプロファイルを変更する副作用はありません。ただし CLI の `main()` は引数解析前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では現在のプロセスの既定 owner と DACL を設定し、以降そのプロセスが作成するファイルの既定 ACL に影響します。POSIX では何もしません。

## 出力とエラー

ヘルプ本文は標準出力へ表示され、正常終了（終了コード `0`）します。`ops` 直下でサブコマンドを省略すると、必須のサブコマンドがないため parser が usage とエラーを標準エラーへ出し、終了コード `2` になります。未認識引数も同じ parser error 経路です。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` を既定設定で作り、トップレベル parser を構成。
- `strata_cli/cli.py:255-267` — `ops` parser と必須 subparser、サブコマンド一覧、共通引数を定義。`ops` に `add_help=False` の指定や明示的な help action はない。
- `strata_cli/cli.py:2217-2231` — `main()` が既定 ACL 処理の後に `parse_known_args()` を実行し、余分な引数を `ap.error()` へ渡す。
- `strata_cli/cli.py:2158-2162` — parse 後の `ops` dispatch。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の Windows 限定の動作と失敗時の扱い。
- `strata.py:30-43` — エントリーポイントは updater handover 判定と preflight の後に `main()` を呼ぶ。今回の調査では安全な実行時 `--help` は実行せず、parser と呼び出し経路をソースで確認した。

