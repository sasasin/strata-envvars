# `strata profile rollback --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile rollback` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

rollback サブコマンドの使い方と、この parser が受け付ける引数・オプションを表示します。`argparse` がサブコマンド parser に自動追加する標準ヘルプアクションで、Strata 独自の値検証や rollback 設定はありません。

## 使い方

```sh
strata profile rollback --help
# または
strata profile rollback -h
```

対象 revision などを指定せずに実行できます。確認した出力は `usage: strata profile rollback [-h] --to REVISION [--output {human,json}] [--json] [--quiet] name` で、位置引数 `name`、必須の `--to REVISION`、出力関連オプションを表示します。

## 値と既定値

値は不要です。短縮形 `-h` は `--help` と同じヘルプアクションです。標準 `argparse` のヘルプアクションは parser の usage と説明を stdout に表示して、終了コード 0 で parser を終了します。ヘルプ表示だけを目的とする場合、`name` や必須の `--to` を指定する必要はありません。

## 実行時の動作

トップレベル parser は `argparse.ArgumentParser` で作られ、`profile` と `rollback` は `add_subparsers(...).add_parser(...)` で登録されています。rollback parser に `add_help=False` の指定はなく、標準の `-h`/`--help` が有効です。さらに one-shot parser 共通の `--json` と `--quiet` が rollback parser に追加されるため、ヘルプの選択肢にも現れます。

`--help` は引数 parse 中に parser を終了させるため、通常処理の `_run()`、`_profile_command()`、`profiles.rollback()` には進みません。したがって、プロファイルや履歴ファイルの読み書き、実行中インスタンスへの作用はありません。

通常実行の構文は `strata profile rollback NAME --to REVISION` です。`--to` は必須、`--output` は `human` または `json` を受け、既定値は `human` です。`--json` は `--output json` の別表記です。これらはヘルプ本文に列挙される対象 parser のオプションであり、この文書の主題である `--help` の動作とは別です。

## 適用条件と副作用

Terminal CLI の `strata profile rollback` に適用されます。ヘルプ表示は読み取り専用で、プロファイルの rollback は実行しません。`--help` そのものに backend、OS、モデル状態による条件はありません。

## 出力とエラー

ヘルプは stdout に usage と positional arguments/options の一覧を出力し、正常終了します。同一 revision のソース checkout で実行した出力では、`-h, --help` に `show this help message and exit` と表示されました。出力文言や折り返しは Python の argparse 実装に依存します。

通常の rollback 実行時は別経路です。指定 revision は小文字16進数16桁である必要があり、履歴に存在しない revision や壊れた履歴は `ProfileError` になります。CLI は `ValueError` 系エラーを人間向けなら stderr に `strata: ...` と出し、エラーコードを終了コードとして返します。これらは `--help` の失敗条件ではありません。

## 根拠

- `strata_cli/cli.py:40-46,69-70,102-105` — 標準 `argparse` parser と profile rollback parser の定義。位置引数 `name`、必須 `--to`、`--output` の既定値。
- `strata_cli/cli.py:508-515` — rollback parser に `--json` と `--quiet` を追加。
- `strata_cli/cli.py:2217-2235` — parser 作成・引数 parse の流れ。
- `strata_cli/cli.py:958-1014` — profile rollback の通常実行経路と成功出力。
- `strata_cli/cli.py:527-542,2166-2173` — 成功・エラー出力と終了コードの扱い。
- `strata_control/profiles.py:326-346` — rollback 対象 revision の形式・履歴検査と保存呼び出し。
- 補助確認: 同一 checkout で `python strata.py profile rollback --help` を実行し、parser の出力を確認。CLI help は parser 定義と照合しており、実行対象のソース変更・build・テストは行っていません。
