# `strata tune list --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。指定すると、このサブコマンドの usage と option 説明を表示する |

## 役割

`strata tune list` の引数構文を表示します。`strata tune` の他のサブコマンドやトップレベル CLI 全体ではなく、記録済み tuning job を一覧する `list` parser のヘルプです。索引でも `tune/list` の `--help` として個別に登録されています。

## 使い方

```sh
strata tune list --help
```

短縮形も同じ parser action です。

```sh
strata tune list -h
```

## 値と既定値

`--help` と `-h` は値を取りません。`argparse.ArgumentParser` が各 parser に標準の help action を作るため、`tune list` 専用の明示的な `add_argument` 宣言はありません。`tune list` parser 自身には `--state-dir`（既定値 `None`）と `--output {human,json}`（既定値 `human`）が定義され、これらが help の引数一覧に含まれます。

## 実行時の動作

`strata tune list --help` は `tune list` parser の usage と説明 `list recorded jobs`、その parser に登録された引数の help を標準出力へ表示し、終了コード 0 で終了します。標準の argparse help action が parser の実行を終了させるため、通常の `tune list` 処理に進まず、保存済み job の検索・読み込みや human/JSON の一覧出力は行いません。

ただし CLI の `main()` は parser を構築して引数解析する前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows ではプロセス token の既定 owner と DACL の設定を試み、Windows 以外では `False` を返して何もしません。したがって help 表示だけでも Windows ではこの token 設定処理が先に走ります。確認した実装上、そこでファイルの作成や tuning 状態の変更はありません。

## 適用条件と副作用

この option は `tune list` parser の引数です。`list` が親の `tune` parser で required subcommand として登録されているため、通常は `strata tune list --help` の形で使います。値の validation や tuning 設定の変更はありません。上記の Windows token 既定値設定の試行が CLI 起動時の副作用です。

## 出力とエラー

成功時は usage と option 説明を標準出力へ出し、argparse の help action により終了コード 0 で終了します。通常の一覧実行時に使う `--state-dir` と `--output` も usage に現れますが、help 指定時にはそれらを使った一覧処理は行われません。ソース checkout の CLI を実行して出力文面を採取することはせず、parser 定義と Python `argparse` の標準 help 動作から記述しています。

## 根拠

- `docs/cli/README.md:796-802` — `strata tune list` の階層とこの option の索引リンク。
- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` によるトップレベル parser の生成と subcommand 登録。
- `strata_cli/cli.py:395-396` — `tune` parser と required な `tune_command` subparser の登録。
- `strata_cli/cli.py:482-484` — `list recorded jobs` の parser と `--state-dir`、`--output` の定義・既定値。
- `strata_cli/cli.py:2217-2231` — CLI 起動時の既定 owner 設定、parser 構築・引数解析、余分な引数のエラー処理。
- `strata_cli/cli.py:1655-1676` — help action を通らず通常実行した場合の job 読み込みと human/JSON 出力。
- `strata_control/private_files.py:349-389` — Windows のみ行う token owner/DACL 設定と失敗時の扱い。
