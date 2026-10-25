# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`strata config show` の使い方と、その parser に登録されたオプションを表示します。`config show` は接続先と credential の参照元を表示するコマンドです。

## 使い方

```console
strata config show --help
strata config show -h
```

## 値と既定値

値は不要です。`config show` の parser は `argparse` の `ArgumentParser` として作られ、ヘルプ追加を無効にしていません。Python `argparse` の既定では `-h` と `--help` が自動追加され、ヘルプ表示後に終了します。この parser には `--effective`、接続指定の `--url`・`--connection`・`--credential-env`・`--timeout`、出力関連の `--output`・`--json`・`--quiet` が登録されています。

## 実行時の動作

このオプションは `config show` の parser で処理され、通常の `_run()` / `monitor_commands.run()` による設定解決には進みません。したがって `connections.resolve()` を呼び出して設定を表示する経路は実行されません。

ただし `strata` の `main()` は parser の作成・引数解析より先に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でのみ働き、プロセスが以後作成するファイルの既定所有者と ACL をユーザー向けに設定します。Windows 以外では何もしません。これは `--help` 自体の効果ではなく、同 CLI の起動時処理です。

## 適用条件と副作用

`strata config show` に対するヘルプです。トップレベルの `strata --help` や `strata config --help` とは parser のスコープが異なります。ヘルプ表示に伴う出力は標準出力で、argparse のヘルプ action は終了コード `0` で終了します。独自の値 validation はありません。

## 根拠

- `strata_cli/monitor_commands.py:96-103` — `config show` parser とそのコマンド固有オプションの定義。`--help` の明示的な追加・上書きはありません。
- `strata_cli/monitor_commands.py:20-25` — 接続関連オプションの共通定義。
- `strata_cli/monitor_commands.py:106-113` — `strata-monitor` parser の生成。既定の `argparse.ArgumentParser` を使います。
- `strata_cli/cli.py:490-493` — 同じ parser 定義を `strata` のコマンド階層へ登録。
- `strata_cli/cli.py:2217-2225` — 起動時処理の後に parser を構築し、引数解析する順序。
- `strata_cli/cli.py:2165` と `strata_cli/monitor_commands.py:167-175` — ヘルプ action が終了せず通常解析が完了した場合の委譲先と、`config` の実行経路。
- `strata_control/private_files.py:349-389` — Windows での既定所有者・ACL の設定と、それ以外の OS での no-op 条件。

出力形式の詳細は実行時の Python `argparse` によって生成されます。この調査では既存 CLI を実行して表示文面を固定せず、同一 revision の parser 定義と標準ライブラリの既定動作を根拠にしています。
