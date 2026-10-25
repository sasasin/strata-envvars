# `strata connect --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査開始時の作業ツリーは `## main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

## 対象と別名

- コマンド: `strata connect`
- オプション: `--help`
- 別名: `-h`
- 値: なし。`argparse.ArgumentParser` の既定 help action が提供します。

## 役割

`strata connect` 専用の使用法、説明、位置引数とオプションの一覧、例を表示します。トップレベルや `strata launch` の help とは別の parser scope です。`connect` parser は専用の説明文と `EXAMPLES` epilog を持ち、`RawDescriptionHelpFormatter` を使うため、例の整形を保った help が構成されます。根拠: `strata_cli/launch/cmd.py:148-165`。

## 使い方

```sh
strata connect --help
strata connect -h
```

## 値と既定値

値を取りません。parser 作成時に `add_help=False` や独自の help action を指定しておらず、`connect` は通常の `ArgumentParser` として作られています。したがって `argparse` の標準 help 表記 `-h, --help` が適用されます。connect parser に登録される他の引数は、任意の harness 位置引数と `--url`、`--key`、`--key-env`、`--model`、`--context`、`--preset`、`--check`、`--write`、`--yes`、`--show-key`、`--output` です。根拠: `strata_cli/launch/cmd.py:148-165`。

## 実行時の動作

トップレベル parser の構築時に `launch_cmd.add_parsers(sp)` が `connect` parser を登録します。起動時は `main()` が parser を構築して `parse_known_args` を呼びます。標準 help action が選ばれると、argparse が `connect` parser の help を stdout に出して正常終了するため、`run_connect()` の一覧表示・接続先情報の処理へは進みません。実際の dispatch は parse 後に行われます。根拠: `strata_cli/cli.py:488-490,2217-2225,2153-2155`。

## 適用条件と副作用

このオプション自体はサーバーへの接続、設定ファイルの書き込み、接続確認を開始しません。なお `main()` は parser の解析より先に `private_files.adopt_user_defaults()` を呼びます。これは Windows で後続作成ファイルの所有者と既定 ACL をユーザー向けにする処理で、同関数は非 Windows では何もせず、失敗しても例外を送出しない設計です。根拠: `strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-390`。

## 出力とエラー

成功時は `connect` parser の usage、説明、引数一覧、例が標準出力に表示され、argparse の標準動作で終了コード 0 になります。専用の Strata エラー処理や `--help` 固有の validation は確認できません。標準ライブラリ argparse の help action の動作は、parser 定義を照合したうえで記述しています。checkout の CLI を実行して出力を採取することはしていません。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — connect parser と引数定義
- `strata_cli/cli.py:40-46,488-490` — トップレベル parser と subcommand 登録
- `strata_cli/cli.py:2217-2231` — 初期処理、引数解析、parse 後の未知引数処理
- `strata_cli/cli.py:2153-2155` — connect 実処理への dispatch
- `strata_control/private_files.py:349-390` — CLI の引数解析前に呼ばれる Windows の既定所有者・ACL 設定

調査は上記 revision の Terminal CLI ソースに限定しています。OS ごとの実行済み help 出力は採取していません。
