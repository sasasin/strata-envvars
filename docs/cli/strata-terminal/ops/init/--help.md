# `strata ops init --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`strata ops init` の利用方法と、そのサブコマンドで受理される引数を表示します。トップレベルの `strata --help` や `strata ops --help` とは別の parser に対するヘルプです。

## 使い方

```sh
strata ops init --help
```

同じ表示は `strata ops init -h` でも得られます。ヘルプには `--profile PROFILE`、`--output {human,json}`、`--json`、`--quiet` とヘルプ自身が表示されます。`--profile` は通常の init 実行では必須ですが、ヘルプ表示には不要です。

## 値と既定値

値は取りません。`argparse.ArgumentParser` の既定のヘルプ機能によって `-h` と `--help` が登録されます。init の parser は `--profile` を必須、`--output` を `human` または `json`（既定値 `human`）として定義し、後段で一回実行型 parser 共通の `--json` と `--quiet` も追加します。これらはヘルプに掲載されますが、`--help` 自体に値形式や既定値はありません。

## 実行時の動作

`strata ops init --help` は argparse が usage と説明を標準出力へ出して正常終了します。引数解析が終了するため、`_run()` や `_ops()`、`recipes.initialize()` は呼び出されず、プロファイルのレシピ作成・読込は行いません。`--output`、`--json`、`--quiet` は init の通常処理向けであり、ヘルプの表示形式を JSON に切り替えません。

## 適用条件と副作用

このオプションは `strata ops init` の parser で有効です。`strata ops` 直下や別のサブコマンドに指定する場合は、その別 parser のヘルプ規則に従います。

CLI の `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でのみ、プロセスの既定ファイル所有者と ACL を現在ユーザー向けに設定しようとします。関数の説明上、ファイル操作はせず失敗しても例外を送出しません。したがって、ヘルプはレシピファイルを作りませんが、Windows でのプロセス内 token 既定値設定の試行は先行します。非 Windows ではこの関数は `False` を返して何もしません。

## 出力とエラー

正常なヘルプ表示は usage を含むテキストを stdout に出し、終了コード 0 で終了します。通常実行に必要な `--profile` の欠落は `--help` 表示時にはエラーになりません。ヘルプなしで必須引数が欠ける場合や未知の引数がある場合、argparse の parser error として stderr に usage/error が出て終了コード 2 になります。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` を生成。既定の `add_help=True` により標準ヘルプを有効化。
- `strata_cli/cli.py:255-267` — `ops init` を含むサブコマンド parser を登録し、`--profile` を必須、`--output` を `human|json`（既定 `human`）として定義。
- `strata_cli/cli.py:508-515` — 各 one-shot parser（`ops init` を含む）に `--json` と `--quiet` を追加。
- `strata_cli/cli.py:1391-1398` — `init` の通常処理が `recipes.initialize(profile)` を呼び、結果を人向けまたは JSON 形式で返す。
- `strata_cli/cli.py:2119-2161,2217-2235` — `_run()` の `ops` dispatch と、CLI 起動時の既定値設定・引数解析・余分な引数のエラー処理。
- `strata_control/private_files.py:349-360` — `adopt_user_defaults()` の Windows 限定動作と非 Windows の早期 return。
- `docs/cli/README.md:476-484` — 索引上のコマンド階層、`--help` と `-h` の alias、および同スコープの他オプション。

`--help` の実表示は対象 revision の既存 CLI を実行して採取していません。表示内容は parser 定義と Python argparse の既定動作に基づいており、ソースの明示定義は確認しています。Release 配布物ごとの差異は調査していません。
