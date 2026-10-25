# `strata ops rollback --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。argparse のヘルプ表示アクション |

## 役割

`strata ops rollback` の使い方と、このコマンドで受け付ける引数・オプションを表示します。これは `strata ops --help` とは別の、`rollback` サブコマンドに対するヘルプです。

## 使い方

```sh
strata ops rollback --help
```

同一 revision のソース checkout で実行したヘルプ出力は次のとおりです。

```text
usage: strata ops rollback [-h] --profile PROFILE [--output {human,json}]
                           --to REVISION [--json] [--quiet]
                           name

positional arguments:
  name

options:
  -h, --help            show this help message and exit
  --profile PROFILE
  --output {human,json}
  --to REVISION
  --json                alias for --output json
  --quiet               suppress human informational output
```

## 値と既定値

値は取りません。`-h` は同じヘルプアクションの短縮別名です。出力形式を選ぶオプションではなく、`--output` の既定値 `human` や `--json` の指定にも左右されません。ヘルプアクションは共通 parser の `argparse.ArgumentParser` による標準のものです（`strata_cli/cli.py:40-41`）。

## 実行時の動作

このコマンド固有の parser には位置引数 `name`、必須の `--profile PROFILE`、`--output {human,json}`（既定値 `human`）、必須の `--to REVISION` が定義されています。`--json` と `--quiet` は one-shot parser 群に追加されるため、この rollback parser にも表示されます（`strata_cli/cli.py:255-277`, `strata_cli/cli.py:508-515`）。

`--help` を指定すると parser が引数説明を表示して終了します。そのため、ヘルプ表示だけなら必須の `name`、`--profile`、`--to` を与える必要はありません。例のように実行した場合、`_run` から `_ops` の rollback 分岐へ進まず、レシピを読み込んだり履歴を復元したりしません（`strata_cli/cli.py:1391-1394`, `strata_cli/cli.py:1436-1439`, `strata_cli/cli.py:2217-2237`）。

## 適用条件と副作用

このヘルプは `strata ops rollback` の parser に適用されます。ヘルプ表示自体は stdout への usage とオプション説明の出力で、終了コードは 0 です。rollback の保存先・履歴ファイルには触れず、レシピの rollback も実行しません。

通常の `strata ops rollback` では `--to` に対象 revision を渡します。rollback 実行時は `name` と profile の現在のレシピを読み、対象 revision の履歴ファイルを検証し、現在版を履歴に保存したうえで対象版を原子的に保存します（`strata_control/recipes.py:253-275`）。これは `--help` の効果ではありません。

## 出力とエラー

同一 revision の CLI で確認したヘルプ出力は標準出力に表示されました。ヘルプ表示は正常終了します。通常実行で必要な `name`、`--profile`、`--to` が欠けている場合などは parser の引数エラーとなり、ヘルプアクションを指定しないエラー経路では usage とエラーが表示されます（`strata_cli/cli.py:40-41`, `strata_cli/cli.py:255-277`, `strata_cli/cli.py:2223-2231`）。

## 根拠

- parser の生成とトップレベルコマンド登録: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:255-277`
- one-shot 共通オプション（`--json`、`--quiet`）の追加: `strata_cli/cli.py:508-515`
- CLI 引数解析と dispatch: `strata_cli/cli.py:2217-2237`, `strata_cli/cli.py:2160-2161`
- rollback 呼び出し: `strata_cli/cli.py:1436-1439`
- revision の形式検査、履歴読込、保存: `strata_control/recipes.py:253-275`
- 利用者向けの rollback 実行例: `docs/TERMINAL.md:116-120`

補助確認として、調査対象 checkout で `python strata.py ops rollback --help` を実行しました。Release 配布物の同一 revision 版は調査していません。
