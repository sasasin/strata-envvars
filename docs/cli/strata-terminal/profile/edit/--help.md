# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile edit` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata profile edit` の引数とオプションを表示して終了します。Python `argparse` の既定のヘルプ action が有効な parser で、`profile edit` parser 自体には `add_help=False` の指定がありません（`strata_cli/cli.py:40-41,96-98`）。

## 使い方

```sh
strata profile edit --help
```

同じ parser には位置引数 `name` と `--output {human,json}` があり、共通 one-shot オプションとして `--json` と `--quiet` も登録されます。実際の同一 revision の表示例は次の通りです（`strata_cli/cli.py:96-98,508-515`）。

```text
usage: strata profile edit [-h] [--output {human,json}] [--json] [--quiet]
                           name

positional arguments:
  name

options:
  -h, --help            show this help message and exit
  --output {human,json}
  --json                alias for --output json
  --quiet               suppress human informational output
```

## 値と既定値

値を取りません。`argparse` の既定 help action が `-h` と `--help` を同一 parser に登録します。説明文に `show this help message and exit` と表示されます。明示的な既定値や値検証はありません（`strata_cli/cli.py:40-41,96-98`）。

## 実行時の動作

`main()` は parser を作り、`parse_known_args()` で引数を解析します。`--help` が指定されると parser がヘルプを標準出力へ表示して終了するため、通常の dispatch や `profiles.edit()` には進みません（`strata_cli/cli.py:2217-2231,958-1005`）。このためプロファイル名、`VISUAL` / `EDITOR`、編集用一時 JSON の生成、保存処理はヘルプ表示では要求・実行されません。編集処理の実装は `strata_control/profiles.py:349-379` にあります。

## 適用条件と副作用

トップレベル CLI の parser が使われる環境で有効です。オプション自体はプロファイルを読んだり編集したりせず、ヘルプを表示して解析を終了します。

ただし parser 解析より前に `private_files.adopt_user_defaults()` が呼ばれます。Windows では昇格プロセスが以後作成するファイルの owner と既定 DACL をユーザー向けにするため、プロセストークンの既定値を変更する場合があります。この関数は Windows 以外では何もせず、Windows でも失敗時に例外を送出しません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-389`）。

## 出力とエラー

ヘルプ本文を標準出力に表示します。同一 revision の CLI で確認した表示には使用法、位置引数 `name`、`-h, --help`、`--output`、`--json`、`--quiet` が含まれます（`strata_cli/cli.py:96-98,508-515`）。ヘルプ action は表示後に parser を終了するため、通常処理のエラー経路へは進みません。ヘルプ指定そのものに引数値の validation はありません。

## 根拠

- `strata_cli/cli.py:40-41` — 最上位 `argparse.ArgumentParser` の生成（既定の help を使用）。
- `strata_cli/cli.py:69-70,96-98` — `profile edit` parser と `name`、`--output` の登録。
- `strata_cli/cli.py:508-515` — `profile edit` を含む one-shot parser への `--json` と `--quiet` の登録。
- `strata_cli/cli.py:2217-2231` — Windows 向け user defaults 処理、引数解析。
- `strata_cli/cli.py:958-1005` — profile dispatch と edit 分岐。
- `strata_control/profiles.py:349-379` — 通常の profile edit における editor 起動、一時ファイル、保存・失敗処理。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の OS 条件と Windows でのプロセストークン設定。

