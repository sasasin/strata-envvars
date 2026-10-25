# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--url` |
| 別名 | なし |
| 値 | 必須。HTTP(S) の Strata server root URL |

## 役割

名前付き接続に保存するサーバーの URL を指定します。`strata connection create` は接続情報をローカルに保存するコマンドであり、この値を使ったサーバーへの接続確認は行いません。作成した接続は `strata connection list` / `show` で確認し、`--connection` または `STRATA_CONNECTION` で選択するコマンドから利用できます（`strata_cli/monitor_commands.py:75-85,140-150`、[`STRATA_CONNECTION`](../../../../STRATA_CONNECTION.md)）。

## 使い方

```sh
strata connection create staging --url https://strata.example
```

`--url` は省略できません。URL のほか、任意で reverse proxy 用 `--prefix` と認証値を格納する環境変数名 `--credential-env` を指定できます（`strata_cli/monitor_commands.py:78-82`）。

## 値と既定値

- `--url` は `required=True` の値引数で、既定値はありません。値を省くと `argparse` が引数エラーにします（`strata_cli/monitor_commands.py:78-81`）。
- URL は `http` または `https` scheme と hostname を持ち、userinfo（URL 内の埋め込み認証情報）を含まない必要があります。path は空か `/` のみで、query と fragment は指定できません。port が不正な場合も拒否されます（`strata_cli/client.py:45-57`）。
- 平文 HTTP は `localhost`、`127.0.0.1`、`::1` の hostname に限って許可されます。それ以外の hostname は HTTPS が必要です。エラーは `remote monitoring requires HTTPS or a local SSH tunnel` です（`strata_cli/client.py:58-63`）。
- 受理した URL は hostname を小文字化し、path のない server root に正規化されます。明示した port は保持されます。前後空白を取り除く処理はありません（`strata_cli/client.py:49-63`）。
- 同じコマンドで `--url` を複数回指定した場合の独自検証はありません。標準の `argparse` 値保存 action のため、複数指定では最後の値が使われます（`strata_cli/monitor_commands.py:78-81`）。

## 実行時の動作

parser が値を受け取ると、コマンド処理は `connections.create(name, url, ...)` を呼びます。ここで URL 検証・正規化が行われ、名前、prefix、認証環境変数名を含む JSON レコードが作成されます。URL は環境変数からの URL や既定 URL で補われず、保存後に接続先として自動選択もされません（`strata_cli/monitor_commands.py:147-150`、`strata_cli/connections.py:221-227`、`strata_cli/connections.py:273-303`）。

保存先は既定で POSIX では `${XDG_CONFIG_HOME:-~/.config}/strata/connections`、Windows では `%APPDATA%/Strata/connections`（`APPDATA` がなければホーム下）です。`STRATA_CONNECTION_DIR` が空でない絶対パスなら、そのディレクトリを使います。相対パスはエラーです。保存先がディレクトリであることを確認し、POSIX では所有者と owner-only 権限も検査します（`strata_cli/connections.py:72-90`）。

## 適用条件と副作用

- 作成されるファイルは `<接続名>.json` です。JSON には URL、prefix、credential-env 名が入り、秘密の認証値そのものは保存しません（`strata_cli/connections.py:1-5,117-121,221-242`）。
- ファイルは排他的作成（既存ファイルを上書きしない）で mode `0600` を指定して作られ、書き込み後に flush と `fsync` が行われます。書き込み中に例外が出た場合は作成ファイルを削除します（`strata_cli/connections.py:227-242`）。
- 同名接続が既にあれば `connection '<name>' already exists` で失敗します。接続名は小文字英字で始まり、小文字英数字・`_`・`-` のみ、長さ 1〜64 文字です（`strata_cli/connections.py:41,53-56,231-234`）。
- `--url` の検証は URL の形式と安全な接続 scheme の確認までです。到達性、TLS 証明書、Strata server としての応答はこの作成処理では確認されません（`strata_cli/connections.py:221-227`。この経路から `Endpoint` や HTTP 要求を呼ぶ処理はありません）。

## 出力とエラー

- 成功時は作成した接続レコードと revision を出力します。既定の human 出力は整形 JSON、`--output json` または `--json` は `{ "schema_version": 1, "ok": true, ... }` 形式です。`--quiet` は human informational output を抑制し、machine output には影響しません（`strata_cli/monitor_commands.py:91-94,147-164,167-175`）。
- URL 形式エラーや必須引数不足は終了コード `2` です。接続名・prefix・credential-env の不正も `ConnectionError` 経由で既定コード `2` になります。同名レコードは同じくコード `2` です（`strata_cli/client.py:45-63`、`strata_cli/connections.py:47-69,221-234`、`strata_cli/monitor_commands.py:231-240`）。
- 不正な保存先ディレクトリなどの接続ストレージ検査エラーはコード `5`、ファイル操作の `OSError` はコード `6` として返されます。human error は stderr に `strata: ...`、machine error は JSON error envelope に出ます（`strata_cli/connections.py:72-90,97-121`、`strata_cli/monitor_commands.py:124-129,231-240`）。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection create` の階層、`--url` の必須指定、同コマンドの出力オプション。
- `strata_cli/monitor_commands.py:140-164` — `--url` を保存処理へ渡す経路と成功出力。
- `strata_cli/connections.py:41-69,72-90,97-121,221-242` — 名前・値の検証、保存場所、保存形式、ファイル作成と失敗時の後始末。
- `strata_cli/client.py:45-63` — URL の受理条件と正規化。
- `strata_cli/monitor_commands.py:124-129,231-240` — エラー出力と終了コード変換。
