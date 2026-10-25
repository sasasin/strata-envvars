# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata logs` の使い方と、その parser が受け付けるオプションを表示して終了します。これは `strata` のトップレベル `--help` や、別コマンドの help とは別スコープです。

## 使い方

```sh
strata logs --help
```

短縮形も使えます。

```sh
strata logs -h
```

## 値と既定値

値は不要です。`strata_cli.monitor_commands.add_logs()` は `sp.add_parser("logs", ...)` でサブコマンド parser を作成し、`add_help=False` を指定していません。そのため Python `argparse` の既定 help オプション `-h` / `--help` が使われます。Strata 側で別の既定値、値変換、または `--help` 固有の validation は定義していません。

同じ `logs` parser に属する表示対象には、接続指定の `--url`、`--connection`、`--credential-env`、`--timeout` と、ログ取得用の `--source`、`--follow`、`--interval`、`--output`、`--json`、`--quiet` が含まれます。実行した `python strata.py logs --help` の出力は `usage: strata logs [-h] ...` と `options:` を表示し、`-h, --help` を「show this help message and exit」と案内しました。

## 実行時の動作

`logs` parser は Terminal CLI のトップレベル parser に登録されます。`--help` が parser によって処理されると usage と option 説明を stdout に出し、終了コード `0` で終了します。通常の引数解析後に行う `_run()` への dispatch には進まないため、ログ snapshot の取得や follow polling は開始しません。

help 自体は入力値・設定ファイル・環境変数・他の `logs` オプションとの優先順位を持ちません。help 表示には `--url` 等の指定も不要です。

## 適用条件と副作用

- help の内容はこの revision の `logs` parser に登録された引数に基づきます。現行の `--source` は `runtime` / `harness`、`--interval` の parser 既定値は `2.0` 秒で、範囲 validation（0.5–30 秒）や各出力モードの組み合わせ検査は通常実行経路側にあります。help を出すだけではそれらの検査も実行されません。
- `strata.py` の起動時には、parser 作成前に `private_files.adopt_user_defaults()` が呼ばれます。この関数は Windows でユーザー既定の owner / DACL を設定しようとし、Windows 以外では何もしません。従って「help は処理 dispatch 前に終了する」ことは、起動前段の処理が一切ないことを意味しません。
- checkout からの起動では、handover 処理は `running_from_checkout()` が真ならインストール済み Control への引き継ぎを行わず、現在のソース CLI が続行します。

## 出力とエラー

確認した同一 revision の `python strata.py logs --help` は stdout に usage と option 一覧を出し、終了コード `0` で終了しました。ネットワークアクセス、ログファイルの生成・変更、follow polling はこの help 実行では行いません。通常経路の引数エラーやログ取得エラーは `--help` 自体の失敗経路ではなく、help 表示後には到達しません。

## 根拠

- 索引上のコマンド階層・option scope: 文書作成先リポジトリの `docs/cli/README.md:1019-1027`。
- `logs` parser とその option 宣言: `strata_cli/monitor_commands.py:63-72`。接続共通 option: `strata_cli/monitor_commands.py:20-25`。
- parser の生成と `logs` 登録: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:488-493`。
- parse の後に通常処理へ進む経路: `strata_cli/cli.py:2217-2238`。help action は parse 中に終了するため `_run()` に到達しない。
- 通常の `logs` validation、接続解決、ログ処理への dispatch: `strata_cli/monitor_commands.py:167-202`。ログ取得実装: `strata_cli/logs.py:101-151`。
- 起動前段: `strata.py:30-43`, `strata_cli/handover.py:126-134`, `strata_cli/private_files.py:349-389`。
- help 表示の補助確認: 同一 checkout で `python strata.py logs --help` を実行し、終了コード `0` と出力を確認。build、テスト、GPU 実行は行っていません。
