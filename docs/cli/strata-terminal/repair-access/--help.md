# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata repair-access` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata repair-access` の利用方法を表示して終了します。このオプションは Strata 独自の action としては定義されていません。`strata_cli/cli.py` で `argparse.ArgumentParser` とサブコマンド parser を作り、`repair-access` に `--output` だけを追加しています（`strata_cli/cli.py:40-45,107-108`）。Python `argparse` の既定設定で各 parser に `-h` と `--help` が登録されるため、このサブコマンドにも適用されます。

## 使い方

```sh
strata repair-access --help
```

同じ表示を短縮形で要求できます。

```sh
strata repair-access -h
```

## 値と既定値

値は不要です。`-h` は `--help` の短縮別名です。表示される構文には、同じ parser に登録された `--output {human,json}` も含まれます（`strata_cli/cli.py:107-108`）。`--help` 自体に既定値はありません。

## 実行時の動作

CLI の `main()` は parser を作成し、引数を解析します（`strata_cli/cli.py:2217-2225`）。`argparse` の help action が表示して終了するため、通常は `_run()` の `repair-access` 分岐および `_repair_access()` には到達しません（`strata_cli/cli.py:2107-2116,2121-2126`）。従って、このオプションによって既知のユーザーデータ領域の走査やアクセス権修復は実行されません。

ただし `main()` は parser の作成・引数解析より前に `private_files.adopt_user_defaults()` を呼びます（`strata_cli/cli.py:2217-2224`）。Windows では、プロセストークンの既定 owner と DACL を現在のユーザー向けに設定しようとします。権限設定に失敗した場合は `False` を返し、例外は内部で捕捉されます（`strata_control/private_files.py:349-389`）。Windows 以外では何もしません。これは `--help` 固有の処理ではなく CLI 起動時の初期化です。

## 適用条件と副作用

- `--help` は `repair-access` サブコマンドの parser に適用されます。トップレベルの `strata --help` は別の parser scope です（`strata_cli/cli.py:40-45,107`）。
- help action による表示後は終了するため、修復処理の出力・ファイル走査・修復失敗コードは発生しません。
- Windows では上記の CLI 起動初期化がプロセスの既定 token owner/DACL に作用し得ます。`--help` はこの初期化を抑止しません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-385`）。

## 出力とエラー

通常の `argparse` help action は usage と parser の説明・オプション一覧を標準出力へ表示して、終了コード 0 で終了します。Strata の parser 宣言から確認できる当該コマンド固有の説明は「管理者として実行した際にロックされた Strata ファイルへのアクセスを戻す（Windows）」で、オプションとして `--output {human,json}` が列挙されます（`strata_cli/cli.py:107-108`）。この文書では実行による出力を採取していません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser とサブコマンド parser の構成。
- `strata_cli/cli.py:107-108` — `repair-access` parser と明示的なオプション定義。`--help` は明示定義されていません。
- `strata_cli/cli.py:2107-2116,2121-2126` — 修復コマンド処理と dispatcher。
- `strata_cli/cli.py:2217-2225` — `main()` の起動初期化と引数解析順序。
- `strata_control/private_files.py:349-389` — Windows の `adopt_user_defaults()` の作用と失敗時の扱い。

同一 revision の CLI help は実行していません。`main()` が引数解析前に Windows の token defaults を変更し得るためです。help action の自動登録・表示・終了動作については Python `argparse` の標準動作に基づき、Strata 固有の parser/dispatch は上記ソースで照合しました。Release 配布物や別のインストール済み CLI の挙動は調査していません。
