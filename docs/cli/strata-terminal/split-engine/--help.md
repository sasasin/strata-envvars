# `strata split-engine --help`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。調査時の checkout は `main`、`origin/main` と同期し、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（フラグ） |

## 役割

`strata split-engine` の使用法とサブコマンド一覧を表示します。この階層では `apply` が必須の唯一のサブコマンドです。run config を処理する機能は `strata split-engine apply` にあり、親コマンドの help はその処理を実行しません（`strata_cli/split_cmd.py:16-22`、`strata_cli/cli.py:2156-2158`）。

## 使い方

```sh
strata split-engine --help
strata split-engine -h
```

同一 revision の CLI で確認した出力は次のとおりです。

```text
usage: strata split-engine [-h] {apply} ...

positional arguments:
  {apply}
    apply     write the split engine's run config for this one when the rule
              says yes; the config itself is not changed

options:
  -h, --help  show this help message and exit
```

## 値と既定値

オプションは値を取りません。`argparse.ArgumentParser` が自動で `-h` と `--help` を登録します。独自の既定値・validation は定義されていません（`strata_cli/cli.py:40-45`、`strata_cli/split_cmd.py:16-19`）。

## 実行時の動作

root parser が `split-engine` parser を登録し、その parser が `apply` を `required=True` のサブコマンドとして登録します（`strata_cli/cli.py:174-175`、`strata_cli/split_cmd.py:16-19`）。help を指定すると argparse がこの階層の usage と説明を表示して parse を終了します。表示内容は親 parser の `prog` 名が `strata` であること、および `split-engine` parser に登録された `apply` から構成されます（`strata_cli/cli.py:40-41`、`strata_cli/split_cmd.py:17-22`）。

`strata split-engine` のみを指定した場合は必須サブコマンドがないため parser error になります。help 表示時に `split_cmd.run()` は呼ばれず、run config の読み込みや split engine 判定・出力ファイル作成は行いません（サブコマンドの dispatch: `strata_cli/cli.py:2156-2158`、実処理: `strata_cli/split_cmd.py:25-58`）。

## 適用条件と副作用

help はサブコマンド処理を実行しません。ただし CLI の `main()` は parser の parse より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows ではプロセス token の既定 owner / DACL を現在の user に設定しようとし、設定失敗を例外にせず、Windows 以外では何もしません（`strata_cli/cli.py:2244-2252`、`strata_control/private_files.py:349-392`）。このため「help が常にプロセス状態にも一切作用しない」とは言えません。ファイルやモデル設定への変更、ネットワーク通信、GPU 起動は help 経路から確認されません。

## 出力とエラー

確認した help は usage とサブコマンド一覧を標準出力へ表示します。通常の argparse help action は help 表示後に正常終了します。`-h` と `--help` の具体的な出力差はありません。サブコマンドを省いた呼び出しは `required=True` により usage とエラーを伴う parser failure になります（`strata_cli/split_cmd.py:18`）。エラー時の実際の終了表示は本調査では個別に実行確認していません。

## 根拠

- parser とサブコマンド: `strata_cli/split_cmd.py:16-22`
- root parser の生成・登録: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:172-175`
- help 後の実処理 dispatch: `strata_cli/cli.py:2244-2259`, `strata_cli/cli.py:2156-2158`
- split-engine の実処理: `strata_cli/split_cmd.py:25-58`
- Windows 起動時処理: `strata_control/private_files.py:349-392`
- 補助確認: 同一 revision の `python3 strata.py split-engine --help`。出力は上記のとおり。
