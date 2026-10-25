# `strata profile use-config --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了するスイッチ |

## 役割

`use-config` サブコマンドの使い方と、その parser が受け付ける引数を表示します。`argparse` の標準ヘルプであり、Strata 独自の値変換や追加 validation はありません。コマンドに必須の `name` と `--from-config` を省略しても、ヘルプの要求が先に処理されます。

## 使い方

```sh
strata profile use-config --help
strata profile use-config -h
```

## 値と既定値

- `--help` と `-h` は同一の標準ヘルプ action です。値を指定しません。`use-config` parser の作成時に `add_help=False` は指定されていないため、`argparse` が両表記を登録します。
- `use-config` parser 自体には、位置引数 `name`、必須の `--from-config CONFIG.json`、`--plan`、`--if-revision REVISION`、`--output {human,json}` が定義されています。これらは表示対象であり、ヘルプ実行時に必須値の検証や profile の読み込みは進みません。

## 実行時の動作

標準ヘルプ action が選択されると、`argparse` はこのサブコマンドの usage と説明を標準出力へ表示して parsing を終了します。通常の `_run()` / `_profile_command()` へ進まないため、ヘルプだけでは profile の読み込み・変更、run-config の検証、保存は行いません。

ただし、トップレベルの `main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。Windows では、この関数がプロセス token の既定 owner と DACL を現在のユーザー向けに設定する場合があります（失敗時は `False` を返します）。Windows 以外では何もせず `False` を返します。この初期化は help action より前に行われます。

## 適用条件と副作用

- `strata profile use-config` の parser に限るヘルプです。トップレベルの `strata --help` や他のサブコマンドのヘルプとは別スコープです。
- 表示自体は設定ファイルやネットワークを操作しません。上記の Windows 初期化を除き、この経路に Strata 側のファイル変更はありません。
- Help action は parsing 中に終了するため、通常の後段処理にある unknown-argument 判定やコマンド実行には達しません。

## 出力とエラー

- 成功時は `use-config` の usage とオプション説明を標準出力に表示し、`argparse` の標準動作で終了コード `0` で終了します。
- `--help` を付けずに `name` や必須 `--from-config` が欠けた場合は、この help オプションの実行ではなく parser の引数エラーになります。トップレベルは `parse_known_args()` 後、余分な引数があれば `ap.error()` を呼びます（通常の `argparse` の usage/error は標準エラー、終了コード `2`）。
- この checkout の CLI を実行して出力を採取する調査は行っていません。表示文面は parser 宣言から確認し、終了動作は標準 `argparse` action に基づいて記述しています。

## 根拠

- 索引上のリンクとコマンド scope: `docs/cli/README.md` の `strata profile use-config` 節。`--help`（alias `-h`）を同コマンド配下に掲載。
- parser は `argparse.ArgumentParser(prog="strata", ...)` と標準 `add_subparsers()` を使い、`profile` も標準 `add_parser()` で作成: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:69-70`。
- `use-config` parser と表示される引数: `strata_cli/cli.py:89-95`。
- 通常の dispatch が `_run()` の `profile` 分岐から `_profile_command()` へ進むこと: `strata_cli/cli.py:2119-2129`。help action は parsing 中に終了するためこの分岐より前で終わる。
- 起動前の初期化と parse / unknown-argument 経路: `strata_cli/cli.py:2217-2231`。
- 初期化の Windows 限定動作、token owner / default DACL の設定、例外時の `False`: `strata_control/private_files.py:349-389`。
