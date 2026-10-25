# `strata connection set --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプ表示用のフラグ。 |

## 役割

`strata connection set` の構文と、その parser に登録された引数を標準出力へ表示します。`set` 用 parser に `argparse` が既定で追加する help action です。トップレベルや他の `connection` サブコマンドのヘルプとはスコープが異なります。

## 使い方

```sh
strata connection set --help
strata connection set -h
```

ソース上で `set` parser に登録されている引数は、位置引数 `name` と `KEY=VALUE` 形式の `assignment`、および `--plan`、`--if-revision REVISION`、`--output {human,json}`、`--json`、`--quiet` です。従って help の usage にはこれらと `-h, --help` が示されます。

## 値と既定値

値は不要です。`-h` は `--help` の短縮別名です。`connection` の `set` parser は `actions.add_parser("set", ...)` で作成されており、help action を無効化する指定はありません。`argparse.ArgumentParser` の既定設定により両表記が有効です。

## 実行時の動作

`strata_cli.cli` は `monitor_commands.add_connections()` を呼び、Terminal CLI の parser に connection コマンド群を追加します。そこで `set` parser とその通常実行用引数が定義されます。`argparse` が help action を処理すると、ヘルプを表示して解析を終了するため、`monitor_commands.run()` や接続の提案・保存処理には進みません。

ヘルプに併記される通常実行用オプションは、`set` では `--plan`、`--if-revision`、`--output`、`--json`、`--quiet` です。help action はそれらの値に依存せず、接続記録を読み書きしたりネットワーク通信したりしません。

## 適用条件と副作用

この parser は Strata Terminal CLI の `strata connection set` に適用されます。help action 自体はコマンド処理を実行しません。一方、CLI の `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。したがって、help action 固有の接続変更はありませんが、CLI 起動全体でこの事前処理が行われる点は区別が必要です。事前処理の個々のファイルへの影響は、このオプション文書の範囲では追跡していません。

## 出力とエラー

`argparse` の help action は対象 parser の usage と引数説明を標準出力へ表示して終了コード 0 で終了します。この調査では CLI を実行せず、出力内容は parser 定義から確認しています。未知の引数など通常の解析エラーでは `main()` が `ap.error()` に渡し、usage とエラーを標準エラーへ表示して終了コード 2 になります。

## 根拠

- Strata `strata_cli/cli.py:40-46` — `prog="strata"` のトップレベル parser とサブコマンド parser の設定。help action を無効化していません。
- Strata `strata_cli/cli.py:490-493` — Terminal CLI に connection parser 群を登録。
- Strata `strata_cli/monitor_commands.py:75-95` — `connection set` parser、位置引数、`--plan`、`--if-revision` と共通出力オプションを定義。`set` parser 作成時に `add_help=False` は指定されていません。
- Strata `strata_cli/monitor_commands.py:140-164` — `connection` の通常処理と、`set` 時の提案・plan・保存経路。help action は引数解析中に終了するためこの処理へ到達しません。
- Strata `strata_cli/cli.py:2217-2231` — 引数解析前の `adopt_user_defaults()`、parser による解析、および余剰引数のエラー処理。
- Strata `strata_cli/cli.py:2165` — 通常処理の fallback dispatch。help action は解析時に終了するため到達しません。

索引: [`strata connection set`](../../../README.md#strata-terminal)。索引に掲載された `--help`（alias: `-h`）と現行 parser の内容は一致します。
