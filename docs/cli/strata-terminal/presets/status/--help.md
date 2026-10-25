# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets status` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`strata presets status` の使い方と、その parser に属する位置引数・オプションを表示します。`-h` は同じヘルプ action の短縮別名です。`presets status` は `presets` のサブコマンドで、保存済み preset のうち対象設定に対応するものと、有効 preset の状態を調べるコマンドです（`strata_cli/tune_commands.py:49-60, 391-408`）。

## 使い方

```sh
strata presets status --help
strata presets status -h
```

ヘルプ表示だけなら対象設定名や JSON 設定ファイルの指定は不要です。通常の status 照会では位置引数 `target` が必要で、保存済み profile 名または run configuration（JSON）を渡します（`strata_cli/tune_commands.py:59-60`）。

## 値と既定値

- 値を取りません。専用の `--help` 宣言はなく、Strata は `argparse.ArgumentParser` と標準の `add_parser()` で parser を作成しています。`argparse` の既定 help action が `-h` と `--help` を登録します（`strata_cli/cli.py:40-45, 487`; `strata_cli/tune_commands.py:50-60`）。
- ヘルプを呼ばず通常実行する場合、status parser は `--output {human,json}` を受理し、既定値は `human` です（`strata_cli/tune_commands.py:53-55, 59`）。ヘルプ action は status の `target` を読み込まずに parser 処理を終了するため、`target` の指定や status 用の出力形式はヘルプ表示の条件ではありません。

## 実行時の動作

`main()` は parser を作って `parse_known_args()` を呼びます。`--help` が選ばれると argparse の help action が usage と引数説明を stdout に出し、終了コード `0` で parser を終了するため、後続の `_run()` と `tune_commands.presets_command()` には進みません（`strata_cli/cli.py:2217-2225, 2236-2237`; サブコマンド dispatch は `strata_cli/cli.py:2151-2153`）。表示内容には `target` と `--output {human,json}` が status parser の構文として含まれます（`strata_cli/tune_commands.py:53-60`）。

これは `strata presets --help` や `strata --help` とは異なり、`status` parser のスコープのヘルプです。`presets` parser は必須サブコマンドを要求し、status parser 自身は `target` を位置引数として定義しています（`strata_cli/tune_commands.py:50-60`）。

## 適用条件と副作用

- `--help` は `presets status` の parser が選ばれる位置に指定します。`strata presets status --help` と `strata presets status -h` が該当します。
- ヘルプ action の後は status 処理に入らないため、profile 解決、run configuration の読込、preset index の照会や preset 状態の計算は行いません。これらは通常の status 処理 `_status()` にあり、`target` の読込から始まります（`strata_cli/tune_commands.py:391-408`）。
- CLI の `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます（`strata_cli/cli.py:2217-2224`）。Windows では、この関数が現在のプロセス token の既定 owner と DACL を設定し、以後そのプロセスが作成するファイルに適用します。関数は失敗時に例外を外へ出さず、Windows 以外では何もしません（`strata_control/private_files.py:349-389`）。これは `--help` 固有の処理ではありません。確認したヘルプ経路には、status 用ファイルの書込み、ネットワーク接続、engine/GPU の起動はありません。

## 出力とエラー

argparse の標準ヘルプを stdout に表示して終了コード `0` で終了します。Strata 独自の status 成功・失敗 JSON は出力しません。ヘルプではなく通常の `status` 実行は `presets_command()` から `_status()` に進み、preset store などの読込エラー処理の対象になりますが、その経路は `--help` では通りません（`strata_cli/tune_commands.py:289-305, 391-408`）。

## 根拠

- parser 共通部と最上位コマンド登録: `strata_cli/cli.py:40-45, 486-489`
- `presets` と `status` parser、位置引数・共通 `--output`: `strata_cli/tune_commands.py:49-60`
- `main()` の起動前処理と引数解析: `strata_cli/cli.py:2217-2237`
- status の dispatch と通常処理の範囲: `strata_cli/cli.py:2151-2153`; `strata_cli/tune_commands.py:289-305, 391-408`
- Windows のプロセス既定 owner/DACL の設定: `strata_control/private_files.py:349-389`
- `argparse` が自動で提供する `-h/--help` の仕様は Python 標準ライブラリの挙動です。Strata の checkout では help action の独自定義・置換は確認できませんでした。

関連文書: [コマンド概要](README.md)、[`--output`](--output.md)。
