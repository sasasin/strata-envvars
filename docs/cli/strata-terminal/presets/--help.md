# `strata presets --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata presets` のサブコマンド一覧と使い方を表示します。この parser は `argparse.ArgumentParser` で作られており、`--help` / `-h` は argparse が各 parser に自動追加するヘルプオプションです。対象は親コマンドのヘルプであり、各サブコマンドの詳細は `strata presets list --help` などで個別に表示します。

## 使い方

```sh
strata presets --help
strata presets -h
```

## 値と既定値

値は不要です。既定値はありません。`--help` と `-h` は同じヘルプ action の別名です。

## 実行時の動作

ヘルプには `list`、`status`、`show`、`apply`、`rename`、`delete`、`undo`、`export`、`import`、`effective`、`off`、`recheck` が列挙されます。`presets` parser に必須サブコマンドが設定されていますが、ヘルプ action は引数解析中に表示して終了するため、サブコマンドを実行せずに親 parser の案内を確認できます。

このオプションは preset の読み書き、推論、ファイル出力を行いません。実装は `strata presets` の引数解析後、指定されたサブコマンドを `presets_command` に渡します。

## 出力とエラー

argparse が親 parser の usage、説明、サブコマンド一覧、`-h, --help` を標準出力に表示して終了コード 0 で終了します。値を付けた場合や未知の引数など、ヘルプ以外の不正な引数は通常の argparse エラー経路になり、usage とエラーメッセージを標準エラーへ出して終了コード 2 となります。サブコマンドを省略した通常呼び出しは `required=True` のためエラーになります。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser の生成とコマンド階層。
- `strata_cli/cli.py:486-488` — `strata presets` parser の登録。
- `strata_cli/cli.py:2217-2231` — parser を構築して `parse_known_args` を行う入口と未知引数の処理。
- `strata_cli/cli.py:2151-2153` — `presets` を `presets_command` に渡す dispatch。
- `strata_cli/tune_commands.py:49-90` — `presets` 親 parser、必須サブコマンド、および各サブコマンドの定義。`ArgumentParser` の `add_help=True` は既定で、ここでは明示的な `--help` 登録はありません。
- `strata_cli/tune_commands.py:289-348` — 引数解析後に実行される preset コマンド処理。
