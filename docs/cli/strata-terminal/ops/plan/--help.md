# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops plan` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示する `argparse` 標準 action。 |

## 役割

`strata ops plan` の使い方と引数・オプションを表示します。この parser のヘルプであり、親の `strata ops --help` や他の `ops` サブコマンドのヘルプとは表示対象が異なります。

## 使い方

```sh
strata ops plan --help
strata ops plan -h
```

## 値と既定値

値は不要です。`ops plan` は `ops` のサブパーサーとして `add_parser("plan")` で作成され、`add_help=False` は指定されていません。そのため標準の `-h` / `--help` が有効です。ヘルプには、必須の位置引数 `name`、必須の `--profile PROFILE`、`--output {human,json}`（既定値 `human`）、one-shot コマンド共通の `--json` と `--quiet` も表示されます。これらは `--help` 自体の値ではありません。

## 実行時の動作

`argparse` がヘルプを表示して引数解析を終了するため、`name` や `--profile` を指定しなくてもヘルプを表示できます。通常実行時の `_ops()` にある `recipes.plan()` 呼び出しには進まず、recipe の読み取りや plan の生成は行いません。

## 適用条件と副作用

対象は `strata ops plan` の parser です。ヘルプ表示は recipe、profile、operation run の記録を変更せず、plan の実行やネットワーク・子プロセス起動にも進みません。

CLI の `main()` は引数解析の前に `private_files.adopt_user_defaults()` を呼びます。この処理は Windows では実行プロセスの既定 owner と DACL の設定を試み、POSIX では何もしません。ファイルを直接変更する処理ではなく、失敗時も例外を送出しません。ソース checkout からの起動では updater handover を行わない分岐があります。

## 出力とエラー

ヘルプは標準出力へ出力され、終了コード `0` で終了します。`--help` を付けずに必須の `name` または `--profile` を省略した場合、parser は usage とエラーを標準エラーへ出し、終了コード `2` で終了します。認識できない引数も `main()` から parser のエラー処理に渡されます。

## 根拠

- `strata_cli/cli.py:40-45` — `prog="strata"` のトップレベル `ArgumentParser` とサブコマンド parser の構成。
- `strata_cli/cli.py:255-267` — `ops` の必須サブコマンド parser、`plan` を含む登録、`name` と `--profile`、`--output` の定義。
- `strata_cli/cli.py:508-515` — `ops_items` に `--json` と `--quiet` を追加。
- `strata_cli/cli.py:1391-1447` — 通常実行時の `ops plan` は `recipes.plan()` を呼び、JSON または整形 JSON を表示する経路。
- `strata_cli/cli.py:2217-2237` — `main()` の前処理、引数解析、parse 後の実行経路。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の Windows 限定のプロセストークン設定と失敗時の扱い。
- `strata_cli/handover.py:126-134` — `.git` があるソース checkout では handover しない条件。
- `strata.py:30-43` — 起動時の handover 判定、preflight、`main()` の呼び出し。今回の調査では CLI を実行せず、ソースの parser と呼び出し経路を確認。
- 索引 `docs/cli/README.md:559-567` — `strata ops plan` のコマンド階層と `--help` の予定リンク。
