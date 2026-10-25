# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。指定するとヘルプを表示する |

## 役割

`strata drafting` の使い方と、その配下にある `plan` / `fetch` サブコマンドの概要を表示します。この文書の対象は親コマンドのヘルプです。`strata drafting plan --help` と `strata drafting fetch --help` は別 parser のヘルプで、別スコープです。

## 使い方

```sh
strata drafting --help
```

## 値と既定値

値は不要です。`strata_cli.cli.parser()` が既定の `argparse.ArgumentParser` を作り、`drafting_cmd.add_parser()` がその配下に `drafting` parser を追加します。どちらも `add_help=False` を指定していないため、標準の `-h` / `--help` action が各 parser に設定されます。親 parser では `plan` と `fetch` の2つが表示対象です。既定値や値の validation はありません。

## 実行時の動作

標準の help action は使い方を標準出力へ出して解析を終了します。そのため `main()` の通常のコマンド dispatch に進まず、`drafting_cmd.run()` による計画処理や drafter の取得は行いません。`drafting` parser には `plan` または `fetch` の指定が必須ですが、help action は引数解析を終了するため、ヘルプ表示だけならサブコマンドを省略できます。

ただし `strata_cli.cli.main()` は parser を作成して解析する前に `private_files.adopt_user_defaults()` を呼びます。この処理は Windows ではプロセスの既定 owner / DACL を現在のユーザー向けに設定しようとし、POSIX では何もしません。ファイル取得はありません。`strata.py` 経由の起動では、その前に handover と preflight も評価されます。

## 適用条件と副作用

このオプションは `strata drafting` parser に対して有効です。配下の `plan` / `fetch` にもそれぞれ独立した標準 help option があります。通常のヘルプ経路は終了コード `0` で終了します。Windows では前述のプロセス既定 ACL 設定が試行されますが、この helper は失敗時に `False` を返し、例外を呼び出し元へ送出しない実装です。

## 根拠

- `strata_cli/cli.py:40-45` — 既定の `argparse.ArgumentParser` とトップレベル parser の作成。
- `strata_cli/cli.py:172-173` — `drafting` parser の登録。
- `strata_cli/cli.py:2217-2224` — help 解析前の `adopt_user_defaults()` 呼び出しと `parse_known_args()`。
- `strata_cli/cli.py:2144-2146` — 通常時に `drafting_cmd.run()` へ dispatch する箇所。
- `strata_cli/drafting_cmd.py:17-29` — `drafting` と必須 `plan` / `fetch` subparser、および各 subparser の option 定義。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の Windows 限定動作、失敗時の戻り値。
- `strata.py:30-43` — CLI 起動時の handover、preflight、`main()` 呼び出し順。
