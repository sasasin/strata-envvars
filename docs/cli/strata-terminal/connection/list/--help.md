# `strata connection list --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプ表示用のフラグ。 |

## 役割

`strata connection list` の構文を標準出力に表示して終了します。`connection list` 専用 parser に自動追加される argparse の help action です。`connection` や他のサブコマンドのヘルプとは別スコープです。

## 使い方

```sh
strata connection list --help
strata connection list -h
```

この revision の checkout で `python strata.py connection list --help` を実行すると、usage は `strata connection list [-h] [--output {human,json}] [--json] [--quiet]` と表示されます。`--output`、`--json`、`--quiet` は `list` parser に登録されています。

## 値と既定値

値は不要です。`-h` は `--help` の短縮別名です。argparse の標準 help action は parser ごとに既定で有効で、`connection list` の parser 作成時に無効化されていません。

## 実行時の動作

argparse がこのフラグを処理すると、その parser のヘルプを表示して終了します。コマンドの実行分岐には進まないため、一覧を作る `connections.list_connections()` は呼ばれません。従って、このオプション自体は接続記録の読込、ファイル作成・変更、ネットワーク通信を行いません。

ヘルプに表示される `--output {human,json}`、`--json`、`--quiet` は `connection list` の通常実行時のオプションです。help action 自体にはこれらの値との相互作用や永続的な設定変更はありません。

## 適用条件と副作用

ソース checkout の Terminal CLI に適用されます。ヘルプ表示は出力のみで、接続一覧の存在や設定内容に依存しません。`strata connection list` の parser は `required=True` の `connection` サブパーサー以下に登録されていますが、このヘルプの表示に接続先や保存済み接続は必要ありません。

## 出力とエラー

確認した checkout では、ヘルプを標準出力に表示して終了コード 0 で終了しました。表示内容には usage と `-h, --help`、`--output {human,json}`、`--json`、`--quiet` が含まれます。

オプション名の誤りなど parser が引数を受理できない場合は、argparse が usage とエラーを標準エラーに出し、通常の parse error として終了コード 2 で終了します。これは `--help` 自体の値検証ではなく、引数解析の失敗経路です。

## 根拠

- Strata `strata_cli/cli.py:40-46` — `prog="strata"` のトップレベル `ArgumentParser` と、`connection` コマンドを含むサブパーサーの起点。
- Strata `strata_cli/cli.py:490-493` — Terminal CLI parser へ connection サブコマンド群を登録。
- Strata `strata_cli/monitor_commands.py:75-95` — `connection` と `list` の parser 定義、および `--output`、`--json`、`--quiet` の登録。`actions.add_parser("list", ...)` に help の無効化指定はありません。
- Strata `strata_cli/monitor_commands.py:140-164` — 通常実行時の `list` 分岐が `connections.list_connections()` を呼び、結果を出力する経路。
- Strata `strata_cli/cli.py:2217-2231` — parser を作成して引数を解析し、解析不能な余剰引数を `ap.error()` に渡す経路。
- Strata `strata_cli/cli.py:2165` — 通常の connection コマンドを `monitor_commands.run(a)` へ渡す dispatch。help action は引数解析時に終了するため、この経路へ到達しません。
- 同一 revision の `python strata.py connection list --help` — 表示された usage と options を parser 定義と照合。Release 配布物や別 OS の wrapper は今回確認していません。

関連文書: [CLI 索引](../../../README.md#strata-terminal)。
