# `strata ops show --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops show` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。Python `argparse` が各 parser に自動追加する help action。 |

## 役割

`strata ops show` の使い方と、その parser が受け付ける引数・オプションを表示して終了します。ここで対象となるのは `ops` の `show` サブコマンドの help であり、`strata --help` や `strata ops --help` とは別の parser スコープです。

## 使い方

```sh
python strata.py ops show --help
```

インストール済み Terminal CLI では同じ階層で `strata ops show --help` を実行します。`-h` は同じ help action の短縮別名です。

## 値と既定値

このオプションは値を取りません。`--help` を明示すると help を表示して終了します。既定値としての出力モードや通常の `show` 処理への切替はありません。

`show` parser 自体は位置引数 `name` と必須の `--profile`、`--output {human,json}`（既定値 `human`）を定義します。また one-shot parser 群への共通追加により `--json` と `--quiet` も定義されます。これらは help の対象となる構文情報ですが、help 表示時に値を指定する必要はありません。

## 実行時の動作

`ops` の各 action 用 parser は `argparse` の `add_parser()` で作られ、`show` もその一つです。`ArgumentParser` の既定動作により `-h` / `--help` が自動で追加されます。`main()` は parser で引数を解析した後に通常の `_run()` へ進みますが、標準の help action は解析中に usage/help を標準出力へ書き、status `0` で終了するため、`_run()` および `recipes.load()` による recipe 読み込みは行われません。

## 適用条件と副作用

通常の `show` 処理（recipe の読み込み・表示）は実行されません。`main()` は parser 作成・引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この処理は Windows では現在のプロセスの既定 owner と DACL の設定を試み、成功すればプロセスが後で作成するファイルの所有者・アクセス規則に影響します。失敗時は `False` を返し、例外を伝播しません。Windows 以外では `False` を返して何もしません。help 表示自体が recipe ファイルを作成・更新する処理は確認できません。

## 出力とエラー

`argparse` の help action により usage と `show` parser の説明・引数一覧を標準出力に表示し、終了コード `0` で終了します。help を指定せず `name` や必須の `--profile` を欠かした場合は parser の引数エラーとなり、usage とエラーを標準エラーへ出して終了コード `2` になります。

## 根拠

- コマンド階層と `ops` / `show` parser の生成、位置引数 `name`、必須 `--profile`、`--output` の定義: `strata_cli/cli.py:255-267`。
- one-shot parser 群（`ops_items` を含む）への `--json`・`--quiet` 追加: `strata_cli/cli.py:508-515`。
- 引数解析および `_run()` への通常経路: `strata_cli/cli.py:2217-2237`。
- `show` が通常実行された場合の recipe 読み込みと結果返却: `strata_cli/cli.py:1416-1418`。
- CLI エラー時の標準エラー出力: `strata_cli/cli.py:527-532`。
- Windows での既定 owner / DACL 設定と Windows 以外での no-op: `strata_control/private_files.py:349-389`。
- ソース checkout からの CLI 起動入口と `main()` 呼び出し: `strata.py:30-43`。

`--help` は Strata 側で明示的な `add_argument()` をしておらず、`argparse` の標準機能を利用しています。上記の出力・status `0` および parser エラー時の status `2` は、その標準 help / error 処理によるものです。調査対象は指定 checkout のソースコードで、同 revision の実行 help および Release 配布物との照合は行っていません。
