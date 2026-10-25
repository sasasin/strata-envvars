# `--connection`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--connection` |
| 別名 | なし |
| 値 | 保存済み接続の名前（`NAME`） |

## 役割

保存済みの read-only 接続設定を選び、`strata status` が問い合わせる Strata server と reverse-proxy path prefix を指定します。parser は `strata status` にこのオプションを登録しており、同じ名前のオプションがある `models list`、`monitor`、`logs`、`config show` とは別スコープです（`strata_cli/monitor_commands.py:20-33`、`strata_cli/cli.py:490-493`）。

## 使い方

```sh
strata status --connection staging
```

`staging` は事前に `strata connection create staging --url https://example.invalid` などで作成した接続名です。ここでは status の read-only リクエストは実行しますが、接続設定を作成・変更する操作は行いません（`strata_cli/connections.py:128-145, 221-242`、`strata_cli/monitor_commands.py:195-213`）。

## 値と既定値

- 値を1つ取ります。parser 自体には `choices` や独自の `type`、既定値はなく、未指定なら `None` です（`strata_cli/monitor_commands.py:20-25`）。
- 接続名は、実際に保存接続を選ぶときに小文字 `a-z` で始まり、その後は小文字英字・数字・`_`・`-`、全体で最大64文字という形式で検証されます（`strata_cli/connections.py:41-56, 93-95`）。
- 指定名の接続ファイルがない、読めない、通常ファイルでない、4 KiB を超える、または設定内容が不正な場合は失敗します。保存ファイルは private な通常ファイルとして読み込まれ、schema、ID、server root、prefix、credential 環境変数名も検証されます（`strata_cli/connections.py:97-114, 128-145`）。
- `--connection ''` のように空文字を渡すと、resolver の選択式では偽値となり、`STRATA_CONNECTION` または通常の URL 解決へ進みます。空文字でも `--url` を同時に指定した場合は、値が `None` でないため併用エラーになります（`strata_cli/connections.py:273-287`）。

## 実行時の動作

- `--url` と `--connection` は同時に指定できず、両方が渡されると `choose --url or --connection, not both` で失敗します（`strata_cli/connections.py:273-280`）。
- 非空の `--connection NAME` は環境変数 `STRATA_CONNECTION` より優先され、保存ファイルから URL、prefix、credential 環境変数名を読みます。`--credential-env` が併記されれば、保存された credential 参照だけを上書きします（`strata_cli/connections.py:276-294`）。
- `--connection` も `--url` もない場合、`STRATA_CONNECTION` が保存接続を選びます。それもなければ `STRATA_URL`、さらにそれもなければ `http://127.0.0.1:8095` が URL になります。接続を使わない場合の credential 参照は `STRATA_API_KEY` です（`strata_cli/connections.py:276-291`）。
- status の実行経路は、環境変数が示す credential 値（未設定なら空）を Bearer credential として読み、resolved endpoint に問い合わせます。`--connection` を指定すると、起動中の `strata launch` の接続先を自動取得する経路は使いません（`strata_cli/monitor_commands.py:195-204`、`strata_cli/client.py:101-110`）。
- telemetry は `/v1/telemetry` を先に要求し、404 の場合に限り `/metrics` と `/v1/status` の互換経路へ進みます（`strata_cli/client.py:134-152`）。

## 適用条件と副作用

- 接続設定の保存先は、`STRATA_CONNECTION_DIR` があれば絶対パスで指定された場所、Windows では `%APPDATA%/Strata/connections`（未設定時はホーム配下）、その他の POSIX 系では `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）です。接続ディレクトリは所有者専用であることが検査されます（`strata_cli/connections.py:71-90`）。このオプションはそこから設定を読み取ります。
- 保存 URL は HTTP(S) の server root でなければならず、認証情報・path・query・fragment は含められません。HTTPS 以外は localhost、loopback IP に限られます。保存 prefix は単純な path segment に限られ、`..` などの traversal は拒否されます（`strata_cli/client.py:45-76`、`strata_cli/connections.py:97-114`）。
- 接続 credential の値そのものは設定ファイルに保存せず、記録された環境変数名からプロセス環境を参照します。値が空または未設定なら Authorization header は付けません（`strata_cli/connections.py:283-301`、`strata_cli/monitor_commands.py:198-199`、`strata_cli/client.py:104-107`）。
- status は telemetry の取得のためネットワーク要求を行います。確認した status 経路では接続ファイルの書き込み・削除は行いません（`strata_cli/monitor_commands.py:195-213`、`strata_cli/client.py:101-152`）。要求 timeout は省略時3秒、指定時は `0 < timeout <= 30` 秒です（`strata_cli/monitor_commands.py:25`、`strata_cli/connections.py:295-302`）。

## 出力とエラー

- 成功時は既定で人間向け overview を標準出力に表示します。`--json` または `--output json` では `{ "schema_version": 1, "ok": true, "snapshot": ... }` の JSON を出力します（`strata_cli/monitor_commands.py:31-33, 203-213`）。
- 接続名・設定の不正や競合は `ValueError` 経路で扱われ、既定では `strata: ...` を標準エラーへ出し、通常は終了コード2（接続ファイルの安全性・欠落等はコード5）になります。JSON 出力時は `ok: false` と `error.code` / `error.message` を含む JSON になります（`strata_cli/cli.py:2165-2173`、`strata_cli/monitor_commands.py:124-129`、`strata_cli/connections.py:47-50, 128-145`）。
- HTTP 401/403 は認証・権限エラー（コード4）、通信失敗は到達不能として失敗します。redirect、JSON 以外の応答、2 MiB 超、壊れた JSON、互換性のない telemetry schema も失敗経路です（`strata_cli/client.py:101-129, 134-152`、`strata_cli/cli.py:2184-2188`）。

## 根拠

- parser と status 固有オプション: `strata_cli/monitor_commands.py:20-33`
- CLI への登録と dispatcher: `strata_cli/cli.py:488-493, 2165-2166`
- 保存接続名・ファイルの検証と解決規則: `strata_cli/connections.py:41-56, 97-145, 273-303`
- status の endpoint 選択と出力: `strata_cli/monitor_commands.py:195-213`
- URL 制約・HTTP 要求・telemetry fallback: `strata_cli/client.py:45-76, 101-152`

調査は上記 revision の Python CLI と接続・client 実装に限定しました。別 platform 上の実通信や Release 配布物は確認していません。
