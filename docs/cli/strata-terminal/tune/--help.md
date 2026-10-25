# `strata tune --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。ヘルプを表示して終了する |

## 役割

`strata tune` のサブコマンド一覧と各サブコマンドの短い説明を表示します。索引上のスコープは `strata tune` であり、個別サブコマンドの引数説明はそれぞれ `strata tune <サブコマンド> --help` で確認します。

## 使い方

```console
strata tune --help
```

## 値と既定値

`--help` は値を取りません。`argparse.ArgumentParser` は既定で `-h` / `--help` のヘルプ action を登録し、ヘルプ表示後に終了します。明示的な既定値や値の validation はありません。`strata tune` parser は `plan`、`run`、`apply`、`rollback`、`status`、`list`、`auto` の各サブコマンドを登録し、サブコマンドを必須にしています。

## 実行時の動作

トップレベル parser の生成後に引数を解析します。`strata tune --help` は `tune` parser のヘルプを出して終了するため、通常のコマンド dispatch（tune の測定・状態読込・設定適用など）には進みません。`--help` の引数位置をサブコマンドの後にすると、そのサブコマンド固有のヘルプになります。

CLI の起動処理は引数解析前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でのみプロセストークンの既定 owner / DACL を設定し、その他の OS では何もしません。これは tune ヘルプ固有の処理ではありません。

## 出力とエラー

正常なヘルプ表示は標準出力に usage、サブコマンド一覧、`-h, --help` の説明を出し、終了コード 0 で終了します（Python `argparse` の標準 help action）。`strata tune` だけを実行してサブコマンドを省略すると、`required=True` の parser 検証で usage とエラーを標準エラーに出し、終了コード 2 になります。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` とトップレベル subparser の生成。
- `strata_cli/cli.py:395-397` — `tune` parser と、必須の `tune_command` subparser。
- `strata_cli/cli.py:398-412`, `414-459`, `461-484`, `486-487` — tune 配下の各 subcommand の登録。`auto` は `tune_commands` から登録。
- `strata_cli/cli.py:2223-2231` — parser 作成、`parse_known_args`、未知引数のエラー経路。
- `strata_cli/cli.py:2156-2157`, `1632-1653` — tune の通常 dispatch と実行処理。ヘルプ action が終了する場合はここに進まない。
- `strata_cli/cli.py:2217-2224` — 引数解析前の Windows user-default 設定呼び出し。
- `strata_control/private_files.py:349-389` — user-default 設定は Windows 限定で、失敗時も例外を送出しない実装。
- `strata.py:30-43` — `main()` の戻り値を `SystemExit` に渡す CLI wrapper。

配置は `docs/cli/README.md:720-725` の索引と一致します。調査補助としての CLI help 実行は行わず、指定 revision の parser と dispatch をソースで確認しました。
