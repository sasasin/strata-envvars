# `strata monitor --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（指定すると monitor parser のヘルプを表示） |

## 役割

`strata monitor` の使用法と、このコマンドで受理されるオプションを表示します。トップレベルの `strata --help` や他のサブコマンドのヘルプとは別の parser スコープです。

## 使い方

```sh
strata monitor --help
strata monitor -h
```

## 値と既定値

値は取りません。`monitor` の parser は `argparse` のサブコマンドとして作られ、`add_help=False` などで既定のヘルプ action を無効にしていません。そのため標準の `--help` と短縮形 `-h` が使えます。ヘルプ action は表示後に parser を終了するため、コマンド実行用の引数や接続先を指定する必要はありません。

## 実行時の動作

表示対象は `strata monitor` の usage と説明、共通接続オプション（`--url`、`--connection`、`--credential-env`、`--timeout`）、monitor 固有オプション（`--once`、`--output`、`--json`、`--quiet`、`--theme`、`--color`、`--glyphs`、`--interval`、`--requests`）です。値の選択肢や既定値も parser の定義に沿って表示されます。

ヘルプ action は引数解析中に終了するため、`monitor_commands.run()` へは進まず、接続先解決、telemetry の HTTP 要求、snapshot の取得、monitor TUI の起動は行いません。

## 適用条件と副作用

- `strata monitor` の parser でのみ、そのコマンド固有のヘルプを表示します。
- CLI の `main()` は引数を解析する前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows ではプロセスが後で作成するファイルの owner / default ACL をユーザーに合わせようとし、Windows 以外では何もしません。従って `--help` 自体は monitor 接続やファイル作成を行いませんが、Windows ではヘルプ解析より前にこの共通処理が実行されます。

## 出力とエラー

標準 `argparse` の help action により、usage とオプション一覧を標準出力へ表示して終了コード `0` で終了します。通常の monitor 実行時に行う interval / requests の範囲検証、非 TTY の拒否、接続エラー処理はヘルプ表示には適用されません。ヘルプ以外の未知引数は `parse_known_args()` の後に `ArgumentParser.error()` で拒否され、usage とエラーを表示して終了コード `2` になります。

## 根拠

- Strata `strata_cli/cli.py:40-45,488-493` — トップレベル parser とサブコマンド群、および `monitor` parser の登録。
- Strata `strata_cli/monitor_commands.py:20-25,49-60` — monitor parser、共通接続引数、monitor 固有引数の定義。`add_parser()` は既定の help action を無効にしていません。
- Strata `strata_cli/cli.py:2119-2165,2217-2238` — 通常処理の dispatch と、引数解析・エラー処理の順序。help action は解析中に終了するため、通常の dispatch より前に終了します。
- Strata `strata_cli/monitor_commands.py:167-194,195-229` — monitor 実行時の検証、接続先解決、snapshot / TUI 起動経路。
- Strata `strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389` — 引数解析より前に呼ばれる Windows 向けユーザー既定値設定と、その処理が Windows 以外で何もしない条件。

調査範囲は上記 commit の parser と呼び出し経路です。同一 revision の配布済みバイナリによる `--help` 出力、Release artifact、Windows 実機での ACL 変更結果は確認していません。標準 `argparse` の help 表示・終了動作は Python 標準ライブラリの仕様に基づき、ソースの parser 定義と照合しました。ビルド、ソース変更、GPU 実行、性能測定、テストは行っていません。
