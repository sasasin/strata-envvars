# `strata ops run --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata ops run` が受け付ける引数と説明を表示して終了します。ヘルプは Python の `argparse.ArgumentParser` が自動生成する標準 action で、`run` 専用の処理や値の validation はありません。`strata ops run` の parser は `ops` の下に作られ、レシピ名や `--profile` などの引数を持ちます（`strata_cli/cli.py:255-280`）。

## 使い方

```sh
strata ops run --help
```

短縮別名も同じヘルプを表示します。

```sh
strata ops run -h
```

## 値と既定値

値は不要です。`argparse.ArgumentParser` は `add_help=True` を既定とするため、各 parser に `-h` / `--help` を追加します（`strata_cli/cli.py:40-41, 260`）。通常の `run` 引数には `name`、必須の `--profile`、既定値 `human` の `--output`、および `--exclusive`、各種 `--if-*` 条件があります（`strata_cli/cli.py:264-290`）。one-shot parser 共通の `--json` と `--quiet` も登録されます（`strata_cli/cli.py:508-515`）。

## 実行時の動作

CLI の `main()` は parser を作成し、`parse_known_args()` で引数を解析します（`strata_cli/cli.py:2217-2225`）。`argparse` の help action が呼ばれると、該当する `strata ops run` の usage と引数ヘルプを標準出力へ出し、parser の終了処理を通じて終了コード `0` で終了します。このため、通常の実行 dispatcher `_run()` やレシピ実行処理 `_ops()` には進みません（dispatcher: `strata_cli/cli.py:2119-2161`、レシピ実行: `strata_cli/cli.py:1391-1464`）。

## 適用条件と副作用

オプション自体は全プラットフォームで parser が利用可能なときに使えます。`main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows ではプロセスの既定 owner / DACL を設定する処理を試み、失敗時は `False` を返します。POSIX では何もせず `False` を返します（呼び出し順: `strata_cli/cli.py:2217-2224`、動作: `strata_control/private_files.py:349-390`）。したがってヘルプ表示時にも、この Windows のプロセス単位の設定試行は先に行われます。ヘルプによるレシピ実行、プロファイル読み込み、レシピファイル変更は確認できません。

## 出力とエラー

usage と引数説明が標準出力に表示され、終了コードは `0` です。ヘルプ action が先に終了するため、必須の `name` や `--profile` が省略されても、通常実行時の必須引数エラーにはなりません。ヘルプ以外の未知引数は通常 `ap.error()` に渡されますが、`--help` の実行では action がそこで終了するため、この後続処理には到達しません（`strata_cli/cli.py:2223-2231`）。端末幅などによる具体的な折り返しは実行環境に依存します。

## 根拠

- parser の生成と `ops run` の引数定義: Strata `strata_cli/cli.py:40-41, 255-290, 508-516`。
- 引数解析と未知引数処理: Strata `strata_cli/cli.py:2217-2231`。
- dispatcher と `ops` 処理: Strata `strata_cli/cli.py:1391-1464`, `2119-2164`。
- 解析前の Windows owner / DACL 設定試行: Strata `strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-390`。
- 確認したソースは調査対象 checkout の commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`。checkout は `main...origin/main` で変更なしでした。CLI の `--help` は実行していません。
