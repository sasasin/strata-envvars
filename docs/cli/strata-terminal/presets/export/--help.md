# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets export` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`strata presets export` の利用法と、その parser が受け付ける位置引数・オプションを表示します。Strata の parser では `--help` を個別に追加していませんが、`argparse.ArgumentParser` と `add_parser()` の既定動作により `-h` と `--help` が各 parser に用意されます（`strata_cli/cli.py:40-45`, `strata_cli/tune_commands.py:49-55,73-76`）。

このコマンドの通常実行には preset の識別子または名前が必要です。help 表示時はその引数を省略できます。

## 使い方

```sh
strata presets export --help
strata presets export -h
```

## 値と既定値

値は不要です。`--help` と `-h` は同じ parser action です。省略時にはヘルプを表示せず通常の引数解析・コマンド処理へ進みます。help action が呼ばれた場合はヘルプを stdout に表示して終了するため、通常処理用の引数値や `--output` の値は help 出力形式を JSON に切り替えません。

## 実行時の動作

`presets export` parser は必須の位置引数 `preset`、`--file`（既定値 `None`）、および共通の `--output {human,json}`（既定値 `human`）を持ちます。これらは help に記載されます（`strata_cli/tune_commands.py:53-55,73-76`）。

`strata_cli.cli.main()` は parser の `parse_known_args()` を呼び、その後に各 command を dispatch します（`strata_cli/cli.py:2223-2231,2151-2152`）。`--help` は解析中に argparse の help action がヘルプを表示して終了するため、`presets_command()` や `presets.export_preset()` には到達しません。したがって、help 表示だけでは preset を読み出したり、`--file` の出力先へ書いたりしません（通常の export 処理は `strata_cli/tune_commands.py:331-337`）。

## 適用条件と副作用

`-h` / `--help` は export parser の引数解析に到達したときに有効です。起動経路全体では parser の生成より前に共通処理があります。ソース checkout では handover 判定は checkout を検出して現在のコードを続行しますが、配布環境ではより新しい Control へ処理を引き継ぐ場合があります（`strata.py:32-42`, `strata_cli/handover.py:126-149`）。また `main()` は parser 解析の前に `private_files.adopt_user_defaults()` を呼びます。これは POSIX では何もせず、Windows では実行プロセスの既定 owner/DACL を設定しようとしますが、失敗しても例外を送出しません（`strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389`）。

## 出力とエラー

help action は usage と parser の説明を stdout に表示し、終了コード 0 で終了します。必須の `preset` を省略しても、`--help` が parser の required 引数検査より先に終了するためエラーになりません。help を指定しない通常解析で必須引数が欠ける、または `--output` に `human` / `json` 以外を指定するなどの parser エラーは、`parse_known_args()` 内で argparse の usage/error 出力となり終了コード 2 になります（parser 定義: `strata_cli/tune_commands.py:53-55,73-76`; 呼び出し: `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-45` — 最上位 `argparse.ArgumentParser` の生成。
- `strata_cli/tune_commands.py:49-55,73-76` — `presets export` の階層、共通 `--output`、必須位置引数 `preset`、`--file`。
- `strata_cli/cli.py:2223-2231,2151-2152` — 引数解析と `presets_command()` への dispatch。
- `strata_cli/tune_commands.py:331-337` — help 以外の export が preset を取得し、`--file` 指定時に JSON を書く処理。
- `strata.py:32-42`, `strata_cli/handover.py:126-149` — CLI 起動時の handover 判定。
- `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389` — parser 解析前の user-default 処理と OS 条件。

同一 revision の CLI help は副作用を避けるため実行していません。上記の option 構成と作用は parser・dispatch のソースを根拠に確認しました。配布済み Release artifact ごとの handover の有無や、Windows 実行時の token API の成否は、このソース確認だけでは判定していません。
