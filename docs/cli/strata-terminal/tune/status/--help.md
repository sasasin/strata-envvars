# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune status` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。`argparse` が parser ごとに自動追加するヘルプ action。 |

## 役割

`strata tune status` の使い方と、このサブコマンドで受理する引数を表示して終了します。トップレベルの `strata --help`、親コマンドの `strata tune --help`、ほかの `tune` サブコマンドの help とは parser scope が異なります（`strata_cli/cli.py:40-45,395-397,477-480`）。

## 使い方

```sh
strata tune status --help
```

`job_id` を指定せずに実行できます。status parser には位置引数 `job_id` が定義されていますが、help action は状態ファイルの検索に進まず終了します（`strata_cli/cli.py:477-480,1678-1685`）。

## 値と既定値

値を取りません。トップレベル parser は標準設定の `argparse.ArgumentParser` で作られ、`tune` と `status` も標準設定の `add_parser()` で追加されています。いずれにも `add_help=False` の指定はありません。そのため `-h` と `--help` は同じ help action です（`strata_cli/cli.py:40-41,395-398,477-480`）。

## 実行時の動作

help には status parser の usage と `job_id`、`--state-dir`、`--output {human,json}` が示されます。`--state-dir` の既定値は `None`、`--output` の既定値は `human` です（`strata_cli/cli.py:477-480`）。help action により引数解析中に表示して終了するため、通常の status 処理は実行されません。通常処理では、`--state-dir`、環境変数 `STRATA_TUNE_DIR`、Strata の state base 内 `tuning` の順に状態ディレクトリを決め、`<job_id>/job.json` を読みます（`strata_cli/cli.py:1643-1650,1678-1706`）。

## 適用条件と副作用

この help は `strata tune status` 専用です。実行結果や保存済み job の内容は表示せず、状態ファイルも読み書きしません。なお CLI の `main()` は parser の構築・引数解析より先に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows 以外では何もせず、Windows ではプロセス token の既定 owner / DACL をユーザー向けに設定しようとします（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-364`）。

## 出力とエラー

標準の `argparse` help action が usage とオプション一覧を標準出力に表示し、終了コード 0 で終了します。したがって `job_id` など必須値を省略しても help 表示が優先されます。通常の引数解析で未知の引数が残ると `main()` は `ArgumentParser.error()` に渡し、usage とエラーを出して終了コード 2 となります（`strata_cli/cli.py:2223-2231`）。同一 revision の CLI の help は実行せず、出力内容の実測確認はしていません。parser 定義からの調査です。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `ArgumentParser` とサブコマンド parser の設定。
- `strata_cli/cli.py:395-397,477-480` — `tune` / `status` の parser 階層、位置引数、status の option 定義。
- `strata_cli/cli.py:1643-1650,1678-1706` — status が通常実行時に参照する state root、job 読み込み、出力と job 不在時のエラー。
- `strata_cli/cli.py:2217-2231` — help 解析前の処理、引数解析、未知引数のエラー経路。
- `strata_control/private_files.py:349-364` — Windows での `adopt_user_defaults()` の条件と処理。
