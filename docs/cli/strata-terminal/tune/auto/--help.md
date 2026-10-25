# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`strata tune auto` の位置引数とオプション、コマンドの説明を表示します。調査対象 revision の実行結果では、利用方法、`target`、`--mode`、`--goal` などの引数が表示され、終了コードは `0` でした。`--help` 自体は tuning を開始しません。

## 使い方

```sh
strata tune auto --help
```

短縮形も同じ parser のヘルプ表示を行います。

```sh
strata tune auto -h
```

`target` を省略してもヘルプ表示が優先され、引数不足のエラーにはなりません。

## 値と既定値

値は不要です。`argparse` の各 parser は既定で help action を持ち、`-h` と `--help` がその action の表記です。別の値を指定する形式や既定値はありません。

## 実行時の動作

`strata_cli/cli.py` は `tune` 用の必須サブコマンド parser を作り、`add_tune_auto` が登録した `auto` parser を追加します。`auto` parser には `argparse` 標準の help を無効にする指定がなく、同 parser のヘルプは自動で有効です。ヘルプ action は parser の引数解析中に表示・終了するため、通常の `tune auto` 実行 handler へ進みません。

実際の `python strata.py tune auto --help` は usage と引数説明を標準出力に表示し、終了コード `0` で終了しました。出力には `target` が位置引数として含まれ、`--mode {quick,thorough}`、`--goal GOAL`、`--leave-ram PERCENT`、`--use {chat,coding}`、その他 auto parser に宣言された引数が列挙されます。

## 適用条件と副作用

このオプションによる tuning、プリセット保存、status/work ファイルの書き込み、engine 起動はありません。なお CLI の `main` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。これは Windows では現在のプロセス token の既定 owner と既定 DACL の設定を試み、POSIX では何もしません。help 表示時にもこの呼び出し自体は通りますが、そこでファイルを作る処理はありません。

## 出力とエラー

ヘルプ本文は標準出力へ出て、終了コード `0` で終了します。ヘルプ出力を無効にする指定はこの parser にはありません。`--help` を使わず必須の `target` を省略した場合などは通常の `argparse` 引数エラー経路となりますが、help action を指定した呼び出しでは引数解析がその前に終了します。

## 根拠

- `strata_cli/cli.py:396` は `tune` サブコマンド parser を作成し、`strata_cli/cli.py:486` は `add_tune_auto` を登録します。
- `strata_cli/tune_commands.py:20-25` は auto parser と説明を定義し、`strata_cli/tune_commands.py:26-46` は位置引数および各オプションを宣言します。`add_help=False` は指定されていません。
- `strata_cli/cli.py:2217-2224` は `main` 内で `adopt_user_defaults()` の後に parser を作り、引数解析します。`strata_cli/cli.py:1652-1653` と `strata_cli/tune_commands.py:174-183` は通常実行時の handler および初期処理を示します。
- `strata_control/private_files.py:349-390` は `adopt_user_defaults()` の作用範囲、Windows 条件、失敗時に例外を送出しないことを示します。
- 同一 revision の補助確認として `python strata.py tune auto --help` を実行し、ヘルプ出力と終了コード `0` を確認しました。
