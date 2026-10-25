# `--help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets import` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。ヘルプ表示用のフラグ |

## 役割

`strata presets import` の使い方を表示します。import サブコマンドの位置引数と、その parser に共通して登録される出力形式オプションを確認できます。

## 使い方

```sh
strata presets import --help
strata presets import -h
```

## 値と既定値

値は取りません。`strata_cli/cli.py` は標準の `argparse.ArgumentParser` を使い、`add_help` を無効にしていません。Python `argparse` の既定により各 parser に `-h/--help` が追加されます。import parser の必須位置引数は `file`、任意の `--output` は `human` または `json`（既定値 `human`）です（`strata_cli/cli.py:40-45`、`strata_cli/tune_commands.py:53-55,76-77`）。

## 実行時の動作

`strata presets` はトップレベル parser に登録され、その下に `import` parser が作られます（`strata_cli/cli.py:486-489`、`strata_cli/tune_commands.py:49-51,76-77`）。`--help` / `-h` は引数解析時にヘルプを表示して終了するため、通常の import handler には進まず、`file` の読み込みや preset の保存は行われません。通常処理では handler が `file` を UTF-8-SIG として読み、JSON を解析して `presets.import_preset` を呼びますが、これは help 表示時には実行されません（`strata_cli/cli.py:2223-2231`、`strata_cli/tune_commands.py:338-341`）。

## 適用条件と副作用

ファイル引数は不要で、ヘルプ本文は標準出力に表示されます。help action は parser の引数解析段階で終了し、import によるファイル読み書きや preset store の変更は発生しません。

ただしエントリポイントの `main` は parser の解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows で、昇格実行時にこのプロセスが後から作るファイルの既定所有者・ACLをユーザー向けに設定する処理です。Windows 以外では何もしません。また同関数は失敗時に `False` を返し、例外を外へ出さない設計です（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-358,372-389`）。

## 出力とエラー

標準の `argparse` help action による usage と各引数の説明が標準出力に出て、終了ステータスは 0 です。help に `file` は必須引数として表示されますが、help action 自体はその値を要求せずに終了します。ヘルプ時には preset 読み込みや保存に関する通常処理のエラー経路へ入りません（parser の `file` 定義: `strata_cli/tune_commands.py:76-77`、引数解析: `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `argparse` parser とサブコマンド parser の構成。
- `strata_cli/cli.py:486-489` — `presets` をトップレベルに登録。
- `strata_cli/cli.py:2217-2224` — parser 構築前の起動処理と引数解析。
- `strata_cli/tune_commands.py:49-55,73-77` — `presets import` parser、共通 `--output`、必須 `file`。
- `strata_cli/tune_commands.py:338-347` — 通常の import 処理および失敗時の扱い。
- `strata_control/private_files.py:349-389` — Windows におけるユーザー既定所有者・ACL設定。

同一 revision の CLI help は実行していません。ヘルプの内容と終了動作は parser 定義および Python 標準 `argparse` の既定動作から確認しました。配布済み Release 実体との照合はこの調査に含めていません。
