# `strata status --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（フラグ） |

## 役割

`strata status` の使い方と、そのコマンドで受け付けるオプションを表示します。これは `strata --help` のトップレベルヘルプとは別の、`status` parser のヘルプです。索引上のコマンド階層はトップレベルの `status` です（索引: `docs/cli/README.md:987-997`）。

## 使い方

```sh
strata status --help
strata status -h
```

## 値と既定値

値は取りません。`strata` のトップレベル parser は `argparse.ArgumentParser`、`status` はその subparser として作られ、いずれも独自の help action を無効化していません。そのため Python `argparse` の既定により `--help` と `-h` が有効です。明示的な既定値・型変換・値検証はありません（`strata_cli/cli.py:40-45,490`、`strata_cli/monitor_commands.py:28-33`）。

## 実行時の動作

help action は parser が引数を処理する段階で usage と `status` の説明・オプション一覧を標準出力へ出し、正常終了します。`strata` は `parse_known_args` の後でコマンド処理へ進みますが、help action はそこで終了するため `monitor_commands.run` や snapshot 取得には到達しません（`strata_cli/cli.py:2217-2237,2165`）。したがって、このオプションによる HTTP 接続、ファイル変更、server/GPU 操作はありません。

ヘルプに掲載される `status` 固有の parser 定義は、接続指定 `--url`、`--connection`、`--credential-env`、`--timeout` と、出力指定 `--output`、`--json`、`--quiet` です（`strata_cli/monitor_commands.py:20-33`）。各オプションの詳細は [索引](../../README.md) の `strata status` 節を参照してください。

## 出力とエラー

正常なヘルプ表示では usage と説明を stdout に表示して終了コード 0 で終了します。`-h` は同じ help action の短縮表記です。argparse が認識できない引数を含む場合の usage/error 表示と終了コード 2 は標準 parser のエラー処理によります。Strata 側で `--help` 専用のエラー処理や出力整形を追加するコードは確認できません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `ArgumentParser` と subparser の構成。
- `strata_cli/cli.py:488-493` — 共通 `status` parser をトップレベル CLI に登録。
- `strata_cli/cli.py:2217-2237` — 引数解析と、解析後に通常処理へ渡す順序。
- `strata_cli/cli.py:2153-2165` — `status` を含む未処理コマンドの `monitor_commands.run` への委譲。
- `strata_cli/monitor_commands.py:20-33` — `status` parser とその通常オプションの定義。独自 help action の無効化はない。
- `strata_cli/monitor_commands.py:167-213` — 通常の status 実行時に接続を解決して snapshot を取得・表示する経路。help action は解析段階で終了するため、この処理には進まない。

調査では parser と実行経路をソースで確認しました。既存 CLI の help 表示、ビルド、テストは実行していません。Release 配布物や OS ごとの配布版については照合していません。
