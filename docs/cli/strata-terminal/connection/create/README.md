# `strata connection create`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| parser | `strata_cli/monitor_commands.py` の `connection create` |

## 役割

サーバー URL、必要ならリバースプロキシのパス prefix、および資格情報を読む環境変数名を、名前付きの monitor connection としてローカルに保存します。資格情報の値は保存しません。この接続情報は `strata monitor` などの read-only telemetry client が後から参照できます（`strata_cli/monitor_commands.py:75-94,147-150`、`strata_cli/connections.py:221-242`）。

このコマンドは接続先へのリクエストやサーバー起動を行いません。URL 等を検証して connection record を作成し、保存結果を表示して終了します（`strata_cli/monitor_commands.py:147-164`）。

## 使い方

```sh
strata connection create work \
  --url https://inference.example \
  --prefix /strata \
  --credential-env STRATA_TELEMETRY_KEY
```

`--prefix` が不要な場合は省略できます。最小例は `strata connection create work --url https://inference.example` です。名前 `work` の connection がすでにある場合は作成に失敗します。既存 record の編集には `strata connection set` を使います（`strata_cli/monitor_commands.py:78-94,147-150`、`strata_cli/connections.py:231-234`）。

## 実行モードと主な動作

コマンドには対話式や dry-run のモードはありません。作成時に名前、URL、prefix、資格情報の環境変数名を検証し、schema version 1 の JSON record を新規作成します。保存先は既定で POSIX では `${XDG_CONFIG_HOME:-~/.config}/strata/connections`、Windows では `%APPDATA%/Strata/connections` です。`STRATA_CONNECTION_DIR` が設定されていればその絶対パスを使います（`strata_cli/connections.py:72-90,97-114,221-242`）。

POSIX では connection directory と既存 record が owner-only であることを確認します。record は mode `0600` で作成し、同名ファイルを上書きしない排他的作成を行います。ファイルへの書き込み中に失敗した場合は作成した record を削除します（`strata_cli/connections.py:83-90,229-241`）。

成功時は human 出力が既定で、作成された connection と revision を JSON 形式の整形テキストで表示します。`--output json` または `--json` は schema version 1 の機械可読 JSON を出力します。`--quiet` は human 出力を抑制します（`strata_cli/monitor_commands.py:91-94,124-129,147-175`）。

## 注意点

- `NAME` は小文字 `a-z` で始まり、小文字英字・数字・`_`・`-` を使う最大64文字です（`strata_cli/connections.py:41-56`）。
- `--url` は必須です。値は `http` または `https` の server root に限り、ユーザー情報、path（空または `/` 以外）、query、fragment は拒否されます。remote host は HTTPS が必要で、HTTP は `localhost`、`127.0.0.1`、`::1` に限られます（`strata_cli/monitor_commands.py:78-82`、`strata_cli/client.py:45-64`）。
- `--prefix` の既定値は空文字列です。`/` も空 prefix として扱われます。指定する場合は最大256文字の単純な path segment の列で、`.` / `..`、query や別 origin にあたる形式は許可されません（`strata_cli/monitor_commands.py:81`、`strata_cli/client.py:66-76`）。
- `--credential-env` の既定値は `STRATA_TELEMETRY_KEY` です。保存するのは環境変数名だけで、環境変数の値や接続先での資格情報の有効性はこのコマンドでは確認しません。名前は ASCII の環境変数識別子形式で、最大128文字です（`strata_cli/monitor_commands.py:82`、`strata_cli/connections.py:41-42,66-69,221-226`）。
- `STRATA_CONNECTION_DIR` を指定する場合は絶対パスが必要です。保存先の directory が不適切な種類または POSIX で owner-only でない場合、保存は拒否されます（`strata_cli/connections.py:72-90`）。

## 出力とエラー

成功時の終了コードは `0` です。無効な名前・URL・prefix・環境変数名などはエラーとして報告されます。同名の connection が存在する場合は既存ファイルを上書きせず、エラーになります。connection directory や record の安全性に関する拒否、ファイル操作の失敗もエラー経路です（`strata_cli/connections.py:47-69,83-90,221-242`）。エラーは通常 `strata: <message>` として stderr に出力され、JSON モードでは `ok: false` とエラー情報を含む JSON を stdout に出します。validation の既定終了コードは `2`、保存データや directory の問題は `5`、OS ファイル操作の失敗は `6` です（`strata_cli/monitor_commands.py:124-129,231-240`、`strata_cli/cli.py:2165-2183`）。

## 関連文書

- [CLI 索引](../../../../README.md) — `strata connection create` の option 文書一覧。
- [`strata connection` 概要](../README.md) — connection 管理コマンドの親階層。
- [Terminal CLI の利用者向け説明](../../../../../TERMINAL.md) — connection の利用例と monitor 接続設定。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection create` parser、必須・既定値、出力 option。
- `strata_cli/monitor_commands.py:124-129,147-175,231-240` — 作成呼び出し、出力形式、quiet とエラー処理。
- `strata_cli/connections.py:41-69,72-90,97-121` — 名前・値の検証、保存先、record schema とサイズ制限。
- `strata_cli/connections.py:221-242` — 新規保存、同名時の拒否、書き込みと revision。
- `strata_cli/client.py:45-76` — server root URL と path prefix の規則。
- `strata_cli/cli.py:488-493,2165-2183` — `strata` への parser 登録と共通エラー処理。
