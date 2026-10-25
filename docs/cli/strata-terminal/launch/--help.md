# `strata launch --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。コマンド説明、`launch` のオプション一覧、使用例を表示する。 |

## 役割

`strata launch` の使い方を表示して終了します。Python 標準の `argparse` が各 subparser に標準で追加するヘルプ action によるもので、`launch` parser は `add_help=False` を指定していません。`--help` と `-h` は同じ action の別名です（`strata_cli/launch/cmd.py:75-82`）。

## 使い方

```sh
strata launch --help
```

トップレベルの `strata --help` とは別のスコープで、`launch` 固有の説明と選択肢を表示します。索引もこのコマンド階層で個別文書に分けています（`strata_cli/cli.py:40-46,486-490`、[CLI 索引](../../README.md)）。

## 値と既定値

値は不要なフラグです。`launch` parser には formatter と説明・例が設定され、モデル実行、アクセス設定、管理操作などの option 群が登録されています（`strata_cli/launch/cmd.py:75-82,83-146`）。

## 実行時の動作

CLI entry point `main()` は parser を作り、`parse_known_args()` で引数を解析します。`--help` action が処理されると `argparse` がヘルプを stdout に出力して正常終了するため、`_run()` の `run_launch()` には進みません。従って help 表示自体はモデル起動・preset 管理を実行しません（`strata_cli/cli.py:2217-2237`）。

起動前に `main()` は `strata_control.private_files.adopt_user_defaults()` を呼びます。実装上、これは Windows 以外では何もせず、Windows ではプロセスの既定 owner/DACL を設定しようとし、失敗時は `False` を返します。この呼び出しはヘルプ解析より前です（`strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-389`）。

## 出力とエラー

ヘルプ本文は標準出力に表示され、`argparse` の help action は終了コード `0` で終了します。独自の help 出力・例外処理は Strata 側にありません。ソースでは `launch` parser の説明、カテゴリ別 option、例が設定されています（`strata_cli/launch/cmd.py:16-31,75-146`）。

## 根拠

- `strata_cli/launch/cmd.py:75-82` — `launch` subparser の生成、説明、formatter。標準 help action を無効化する指定はありません。
- `strata_cli/launch/cmd.py:83-146` — `launch` 固有の option 登録。
- `strata_cli/cli.py:40-46,486-490` — 最上位 parser と `launch` 登録位置。
- `strata_cli/cli.py:2217-2237` — entry point の事前処理、引数解析、実行分岐。
- `strata_control/private_files.py:349-389` — help 解析前に呼ばれる Windows 向け既定 owner/DACL 設定。

この調査では CLI を実行していません。表示文の実出力は同一 revision の parser 定義に基づいており、ビルド済み配布物との照合はしていません。
