# `strata ops runs --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main`（`git status --short --branch` に未コミット変更の表示なし）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない（ヘルプ表示アクション） |

## 役割

`strata ops runs` の使用法を表示します。このコマンドは保存済み operator recipe の実行履歴を一覧するもので、`--help` を指定した場合は一覧処理をせず、コマンド固有の引数を確認できます。索引では `ops/runs` の `--help`（alias: `-h`）として登録されています。

## 使い方

```sh
strata ops runs --help
# 短縮形
strata ops runs -h
```

通常の実行では `--profile NAME` が必須です。履歴件数を制限する `--limit` は既定値 `20`、出力形式を選ぶ `--output` は `human` / `json`（既定 `human`）です。ヘルプ表示ではこれらの必須値を指定する必要はありません。

## 値と既定値

`--help` は値を受け取りません。各サブパーサーは `argparse` の既定設定で生成されており（`add_help=False` の指定なし）、`-h` と `--help` が組み込まれます。これは `ops runs` のパーサーにも適用されます（`strata_cli/cli.py:255-269`）。

## 実行時の動作

パーサーが `ops runs` を組み立てる際、`--profile`、`--output`、およびこのサブコマンド固有の `--limit` を登録します（`strata_cli/cli.py:255-269`）。`--help` を解析すると `argparse` がヘルプを標準出力へ出して正常終了するため、通常の dispatch と `_ops` の履歴読み出しには進みません。通常経路で履歴を読む処理は `journal.list_runs(a.profile, limit=a.limit)` です（`strata_cli/cli.py:1404-1408, 2217-2237`）。

## 適用条件と副作用

ヘルプアクション自体は履歴を読み書きせず、recipe 実行や外部プロセス起動も行いません。終了コードは `argparse` のヘルプアクションによる正常終了（0）です。

ただし入口 `strata.py` は、CLI parser を作る前に updater の拒否・新しい Control への引き継ぎを確認します（`strata.py:30-42`）。また `main()` は引数解析前に `private_files.adopt_user_defaults()` を呼びます。これは Windows で、プロセスが以後作るファイルの既定 owner/DACL をユーザー向けに調整する処理であり、Windows 以外では何もしません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-357, 372-389`）。従って「ヘルプ表示自体」にファイル副作用はありませんが、入口初期化にはこの条件付きプロセス設定があります。

## 出力とエラー

通常は `ops runs` の使用法と利用可能な引数を標準出力に表示して 0 で終了します。`--help` を付けず `--profile` を省略した通常呼び出しは必須引数違反となり、`argparse` のエラー経路になります。解析後に未知の引数が残った場合は `ap.error(...)` によりエラー終了します（`strata_cli/cli.py:2223-2231`）。ヘルプアクションは解析中に終了するため、その後の dispatch は実行されません。

## 根拠

- `strata_cli/cli.py:255-269` — `ops` / `runs` の階層と、`--profile`、`--output`、`--limit` の登録。`ops_sp.add_parser(action)` は既定の help action を使用。
- `strata_cli/cli.py:1404-1408` — 通常の `runs` 実行時に journal を読み、結果を出力する箇所。
- `strata_cli/cli.py:2217-2237` — 初期化、引数解析、dispatch の順序。
- `strata.py:30-42` — parser 前の updater 引き継ぎ確認と CLI 入口。
- `strata_control/private_files.py:349-357, 372-389` — Windows における既定 owner/DACL 調整と非 Windows での no-op 条件。
