# `strata connection set`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/connections.py` |

## 役割

保存済みの monitor 接続定義から、URL、reverse-proxy prefix、または資格情報を読む環境変数名のいずれか1項目を変更します。接続情報はユーザーのローカル設定ファイルに保存され、資格情報の値そのものは保存しません。このコマンドは Strata server への要求を行いません。

接続定義を新規作成・表示・一覧する場合は、それぞれ `strata connection create`、`show`、`list` を使います。各オプションの詳細は [`--plan`](--plan.md)、[`--if-revision`](--if-revision.md)、[CLI 索引](../../../README.md)を参照してください。

## 基本的な使い方

```sh
# 変更内容を表示するだけで保存しない
strata connection set work prefix=/new-strata --plan --output json

# URL の変更を保存する
strata connection set work url=https://inference.example

# 資格情報の参照先を変更し、確認した revision の場合だけ保存する
strata connection set work credential_env=STRATA_TELEMETRY_KEY --if-revision 0123456789abcdef
```

構文は `strata connection set NAME KEY=VALUE` です。`KEY` は `url`、`prefix`、`credential_env` のいずれかで、1回の実行で変更できるのは1項目です。

## 実行モード

| モード | 動作 |
| --- | --- |
| 通常実行 | 保存済み定義を読み、指定値を検証してから、revision を再確認したうえで更新します。値に変更がなければファイル内容は置換しません。 |
| `--plan` | 更新候補、現在の revision、`would_save` を表示して終了します。ファイルは保存しません。 |
| JSON 出力 | `--output json` または alias の `--json` で機械可読の成功・エラー JSON を出力します。 |

`--if-revision REVISION` を指定すると、読み込んだ現在の revision と一致する場合だけ処理を続けます。通常保存では、オプションの有無にかかわらずロック内でも revision を比較するため、preview 後に別プロセスが変更した場合は上書きせず失敗します。

## 主な動作と副作用

- 接続名は小文字英字で始まり、小文字英数字、`_`、`-` からなる最大64文字です。対象名が未保存ならエラーになります。
- `url=...` は server root のみを受け付け、埋め込み資格情報、path、query、fragment を拒否します。remote URL は HTTPS が必要です。HTTP は localhost、`127.0.0.1`、`::1` に限られます。
- `prefix=...` は最大256文字の単純な URL path prefix です。空文字列または `/` は prefix なしとして正規化され、空セグメント、`.`、`..`、query などを含むパスは受け付けません。
- `credential_env=...` は ASCII の環境変数名（先頭は英字または `_`、以降は英数字または `_`、最大128文字）を保存します。環境変数の値は読み出し・保存しません。
- 保存先は通常 POSIX で `${XDG_CONFIG_HOME:-~/.config}/strata/connections/NAME.json`、Windows で `%APPDATA%/Strata/connections/NAME.json` です。`STRATA_CONNECTION_DIR` があれば展開後の絶対パスを使います。既存ディレクトリはディレクトリである必要があり、POSIX では所有者専用でなければ拒否されます。
- 通常保存では同名 lock file を使って排他し、revision を再読込して比較します。変更があれば一時ファイルへの書き込み後に置換します。record は 4 KiB 以下です。

## 出力と失敗

成功時は人間向け JSON 形式、または `--json` / `--output json` の場合は `schema_version` と `ok` を含む JSON を stdout に出します。`--plan` の JSON には `would_save`、通常保存では `previous_revision` と新しい `revision` が含まれます。`--quiet` は人間向け出力を抑制しますが、JSON 出力は抑制しません。

値や引数の不正、対象未保存、revision 不一致、保存先の権限・形式不正などはエラーになります。通常の接続定義エラーはコード2、ファイル・record 検査エラーは5、preview 後の revision 不一致は6として返されます。人間向けエラーは stderr の `strata: ...`、JSON モードでは stdout のエラーオブジェクトです。argparse が検出する構文エラーは parser が usage とエラーを表示します。

## 根拠

- Strata `strata_cli/cli.py:40-45,486-494` — `strata` parser と `connection` parser 群の登録。
- Strata `strata_cli/monitor_commands.py:75-94` — `connection set` の引数、`--plan`、`--if-revision`、出力オプション。
- Strata `strata_cli/monitor_commands.py:132-164,167-175,231-240` — set の実行、plan/save 分岐、出力形式、エラー処理。
- Strata `strata_cli/connections.py:41-69,72-90` — 名前・環境変数名と保存先・directory validation。
- Strata `strata_cli/connections.py:245-270` — 変更可能な key、revision 比較、ロックと保存。
- Strata `strata_cli/client.py:45-76` — server root と prefix の検証。
- Strata `docs/TERMINAL.md:30-44` — 利用例、設定保存先、環境変数・権限に関する利用者向け説明。
