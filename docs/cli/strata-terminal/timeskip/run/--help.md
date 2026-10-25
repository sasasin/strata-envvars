# `strata timeskip run --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`strata timeskip run` の usage、説明、引数とオプションの一覧を表示します。これは `timeskip run` parser に対するヘルプであり、`strata timeskip --help` のサブコマンド一覧とはスコープが異なります。

## 使い方

```sh
strata timeskip run --help
strata timeskip run -h
```

ヘルプ表示だけなら `--workspace` と `--prompt` は不要です。通常の `run` はこの二つを必須にしますが、ヘルプ action は parser が必須引数の不足を検査する前に終了します。

## 値と既定値

値を取りません。`strata_cli.cli.parser()` は標準の `argparse.ArgumentParser` を使用し、`timeskip` と `run` を `add_parser()` で追加しています。`add_help` を無効にしていないため、Python `argparse` の標準 `-h` / `--help` action が各 parser に作られます。対象 parser は `--workspace` と `--prompt` を `required=True` として定義しています。

## 実行時の動作

`--help` または `-h` を指定すると、`argparse` がこの parser のヘルプを標準出力へ書き、成功終了します。`main()` は parser を構築して `parse_known_args()` を呼びますが、help action がそこで終了するため、通常の `_run()` dispatch や `_timeskip()` の run 処理には進みません。したがって、このオプション自身は workspace の checkpoint 作成、revision command 実行、state 保存を行いません。

CLI の `main()` は parser 構築より先に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でのみ現在のプロセスの既定 owner / DACL を設定し、Windows 以外では `False` を返して何もしません。これは `--help` 固有ではなく CLI 起動時の処理です。

## 適用条件と副作用

`--help` は `timeskip run` parser のヘルプに適用されます。保存先や workspace を変更するオプションではありません。ソース checkout の入口 `strata.py` は、CLI parser を呼ぶ前に updater の委譲判定を行い、その後 `_preflight()` を通します。`_preflight()` は `serve` / `bench` 以外では追加依存パッケージを検査しないため、`timeskip run --help` はその検査対象ではありません。

この調査では既存の配布 CLI による `--help` 実行は行っていません。ヘルプ本文の実際の折り返しやインストール済み wrapper の委譲先は確認対象外です。記載した parser 定義は上記 commit のソースに基づきます。

## 出力とエラー

ヘルプ本文は標準出力、通常の `argparse` help action の終了コードは `0` です。`--help` を付けずに必須引数を欠いた場合や、認識されない引数を渡した場合は通常の parser error となり、usage とエラーを標準エラーへ出して終了コード `2` になります。`main()` は `extras` が残った場合に `ap.error()` を呼びます。

## 根拠

- `strata_cli/cli.py:40-45` — 標準 `argparse.ArgumentParser` とトップレベル parser の構築。
- `strata_cli/cli.py:348-370` — `timeskip` / `run` parser、必須の `--workspace`・`--prompt`、`run` 固有オプションの定義。`add_help=False` の指定はありません。
- `strata_cli/cli.py:2217-2231` — `main()` の起動時処理、`parse_known_args()`、未知引数の `ap.error()` 経路。
- `strata_cli/cli.py:2147-2151` — `timeskip` が通常 dispatch で `_timeskip()` に渡される箇所。help action は parse 中に終了するためこの dispatch に到達しません。
- `strata_cli/cli.py:1467-1485` — 通常の timeskip 実行で store/state directory を準備する処理。
- `strata_control/private_files.py:349-385` — `adopt_user_defaults()` の説明と Windows 限定の処理。
- `strata.py:14-27,30-43` — CLI wrapper の preflight 条件と parser 呼び出し前の順序。
