# `strata bench report --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench report` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。指定するとこのサブコマンドの usage と引数説明を表示する |

## 役割

`strata bench report` の引数・オプションを確認するためのヘルプ表示です。レポートを読む・要約する通常処理とは別の parser action です。

## 使い方

```sh
strata bench report --help
```

短縮形は `strata bench report -h` です。

## 値と既定値

値は不要です。`strata_cli.cli.parser()` は `argparse.ArgumentParser` からトップレベル parser を作り、`bench`、`report` の各サブパーサーも通常の `add_parser()` で作成しています。`add_help=False` の指定はなく、Python `argparse` の標準ヘルプ引数 `-h` / `--help` が有効です（`strata_cli/cli.py:40-41, 339-343`）。

表示される `report` 固有の構文は位置引数 `path`、`--output {human,json,markdown}`（既定値 `human`）、および `--out NEW_FILE` です。さらに one-shot コマンド共通の `--json` と `--quiet` も同じ parser に追加されます（`strata_cli/cli.py:339-343, 508-515`）。これらはヘルプ表示自体の値ではなく、通常実行時の別オプションです。

## 実行時の動作

`argparse` が help action を処理すると、`report` parser の usage とオプション説明を標準出力へ表示して終了します。`main()` はその後に行う余分な引数処理や `_run()` の呼び出しに進みません。したがって、`path` のレポート読み込み・形式判定・要約・Markdown 出力は行いません（`strata_cli/cli.py:2217-2237`、レポート処理は同 `:1129-1162`）。

ただし `main()` は parser の構築・解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows 以外では何もせず、Windows ではプロセストークンの既定 owner と DACL をユーザー向けに設定しようとします。失敗時は `False` を返し、例外を送出しない実装です（`strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-385`）。ヘルプ表示のためにレポートファイルを作成・変更する処理はありません。

## 適用条件と副作用

Terminal CLI の `strata bench report` parser に適用されます。引数なしの `strata bench report` は位置引数 `path` がないため通常の argparse usage error になりますが、`--help` / `-h` を指定した呼び出しはヘルプ表示で終了します。未知の引数は `main()` の `parse_known_args()` 後にトップレベル parser の `error()` に渡されます（`strata_cli/cli.py:2217-2231`）。

ヘルプ表示によるレポート読み込み・ファイル出力・ベンチマーク実行はありません。前述の Windows 初期化はプロセスの既定ファイル作成権限に関する副作用です。

## 出力とエラー

正常なヘルプ表示は標準出力に usage と説明を出し、argparse の help action により終了コード `0` で終了します。引数不足や未知の引数など parser エラーでは usage とエラーメッセージが標準エラーに出て、argparse が終了コード `2` で終了します。`main()` の parser 解析は `ap.parse_known_args(argv)` です（`strata_cli/cli.py:2217-2231`）。

## 根拠

- `strata_cli/cli.py:40-41` — `argparse.ArgumentParser` によるトップレベル parser の作成。
- `strata_cli/cli.py:339-343` — `bench report` parser と引数定義。
- `strata_cli/cli.py:508-515` — one-shot parser に追加される `--json` / `--quiet`。
- `strata_cli/cli.py:1129-1162` — 通常実行時の report 処理。help action で終了した場合は到達しない。
- `strata_cli/cli.py:2217-2237` — CLI 初期化、parser 解析、未知引数処理、通常 dispatcher への移行。
- `strata_control/private_files.py:349-385` — Windows での既定 owner / DACL 設定と失敗時の戻り値。
