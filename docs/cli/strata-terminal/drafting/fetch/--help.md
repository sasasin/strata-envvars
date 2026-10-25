# `strata drafting fetch --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`fetch` サブコマンドの usage と、その parser が受け付けるオプションの説明を標準出力に表示します。`--help` は `strata drafting fetch` に属し、トップレベルや `strata drafting plan` の help とは別のスコープです。

## 使い方

```sh
strata drafting fetch --help
```

## 値と既定値

値を取りません。`strata_cli/drafting_cmd.py` は `fetch` 用 parser を `add_parser("fetch", ...)` で作り、help を無効にする指定をしていません。Python `argparse` の標準により `-h` と `--help` が同じ help action として利用できます。表示内容には、同じ parser に定義された `--data-dir`、`--config`、`--family`、`--mode`、`--if-needed`、`--output` も含まれます。

## 実行時の動作

`strata_cli.cli.main()` は parser を作って引数を解析します。`argparse` の help action がヘルプを表示して正常終了するため、`_run()` や `drafting_cmd.run()` は呼ばれず、fetch・ネットワーク取得・パック作成は実行されません。実行時の help 表示は Strata の CLI 処理における読み取り専用の案内です。

ただし、CLI 共通入口は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。これは POSIX では何もせず、Windows では可能な場合にプロセス token の既定 owner と DACL を現在のユーザー向けに設定します。これはファイル取得ではありませんが、`--help` 固有のものでもない起動前処理です。

## 適用条件と副作用

- `--help` を指定すると、`fetch` の実処理には入りません。`fetch` が通常行う `drafting_fetch.ensure()` は `drafting_cmd.run()` 内で呼ばれます。
- help の表示形式や折り返しは `argparse` と実行環境の Python によります。調査では実行時 help を取得していないため、特定 Python 版の実出力そのものは記録していません。
- Windows では前述の process token の既定値設定が試みられます。この関数は失敗時に `False` を返し、CLI は戻り値を参照しません。

## 出力とエラー

help action は usage と parser に定義された説明を標準出力へ出して終了コード `0` で終了します。Strata の fetch 実装が出す進捗・成功・失敗メッセージはこの経路では出ません。help を指定せず parser が不正な引数を検出した場合は、`main()` が `ArgumentParser.error()` を使う経路となり、これは help 表示とは別です。

## 根拠

- Strata `strata_cli/cli.py:40-45,172-173` — トップレベル parser と `drafting` parser の登録。
- Strata `strata_cli/cli.py:2217-2231,2236-2237` — 引数解析前の共通処理、`parse_known_args()`、余分な引数のエラー処理と通常実行への分岐。
- Strata `strata_cli/drafting_cmd.py:17-29` — `fetch` parser とその help、同じスコープのオプション定義。`add_help=False` の指定はありません。
- Strata `strata_cli/cli.py:2144-2146`、`strata_cli/drafting_cmd.py:57-59,87-99` — fetch 実装への分岐と取得・出力処理。help action が終了する通常経路はこれらの処理へ進みません。
- Strata `strata_control/private_files.py:349-389` — Windows での既定 owner / DACL 設定と POSIX の no-op、失敗時に例外を伝えない処理。
- `docs/cli/README.md:339-349` — 索引上の `strata drafting fetch` と `--help` 文書パス。
