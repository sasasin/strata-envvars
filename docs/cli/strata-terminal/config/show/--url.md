# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--url` |
| 別名 | なし |
| 値 | `URL`。HTTP または HTTPS のサーバールート |

## 役割

接続設定の実効値を解決するとき、環境変数や既定値の代わりにサーバールートを指定します。`config show` は接続先・認証情報の参照元を表示するローカル設定確認コマンドで、指定したサーバーへ接続しません（`strata_cli/monitor_commands.py:132-139`）。

## 使い方

```sh
strata config show --url http://127.0.0.1:8095
```

JSON で確認する場合:

```sh
strata config show --url https://strata.example --output json
```

`--url` は `strata config show` に属します。parser は `--url` を必須にしておらず、引数を省略できます（`strata_cli/monitor_commands.py:96-103,20-26`）。

## 値と既定値

- 値は HTTP(S) URL のサーバールートです。userinfo（`user:password@`）、パス、query、fragment は拒否されます。末尾の `/` は許容され、出力 URL は正規化されます（`strata_cli/client.py:45-63`）。
- HTTP は `localhost`、`127.0.0.1`、`::1` のみ許可されます。それ以外のホストは HTTPS が必要です（`strata_cli/client.py:58-63`）。ポートの構文が不正な場合は `invalid server port` になります（同:55-57）。
- `--url` 未指定時は `STRATA_URL`、続いて既定値 `http://127.0.0.1:8095` が使われます（`strata_cli/connections.py:44,273-291`）。
- 空文字列や `http://host/path` のような値も parser 自体は受け取りますが、URL 検証で失敗します（`strata_cli/monitor_commands.py:20-26`、`strata_cli/client.py:45-63`）。

## 実行時の動作

`strata config show` parser は `--url`、`--connection`、`--credential-env`、`--timeout` を共通接続引数として登録します（`strata_cli/monitor_commands.py:20-26,96-103`）。`strata` の parser はこの `config` サブコマンドを登録し、実行時は `monitor_commands.run()` に渡します（`strata_cli/cli.py:490-493,2165`）。

設定解決の優先関係は次の通りです。

1. `--url` と `--connection` を同時に指定するとエラーです（`strata_cli/connections.py:277-280`）。
2. `--connection NAME` があれば保存済み接続を使います。これがなければ、`--url` が `STRATA_CONNECTION` より優先されます（同:277-289）。
3. `--url` も `--connection` もなければ `STRATA_CONNECTION`、次に `STRATA_URL`、最後にローカル既定 URL を解決します（同:277-291）。
4. `--credential-env` を併用すると、選択された接続に記録された認証環境変数名または既定の `STRATA_API_KEY` を上書きします。値そのものは表示せず、環境変数に値があるかを `credential_present` として示します（同:282-302）。

このサブコマンドは解決済み URL、proxy prefix、認証環境変数名とその有無、timeout、接続名・revision、各値の由来を出力します。`--output json` または `--json` では `schema_version` と `ok` を含む JSON 形式になります。`--quiet` は human 表示を抑制しますが、JSON 出力は抑制しません（`strata_cli/monitor_commands.py:132-139,167-175`）。接続設定の解決に際してサーバー API を呼び出す処理はなく、`Endpoint` も生成されません（同:132-139）。

## 適用条件と副作用

`--url` は設定値を選択・検証するだけで、ネットワーク通信、設定ファイルへの書き込み、サーバー起動は行いません（`strata_cli/monitor_commands.py:132-139`）。保存済み接続の選択とは併用できません。保存済み接続を指定しない場合、`STRATA_CONNECTION` が設定されていても明示した `--url` が選択されます（`strata_cli/connections.py:277-291`）。

## 出力とエラー

- 成功時は human 形式の JSON オブジェクト、または `--output json` / `--json` による機械可読 JSON を stdout に出します（`strata_cli/monitor_commands.py:132-139,167-175`）。
- `--url` と `--connection` の同時指定、URL 検証失敗、timeout の範囲外は失敗します。human 形式では `strata: <message>` を stderr に出して終了コード 2 を返し、JSON モードではエラーオブジェクトを stdout に出します（`strata_cli/connections.py:277-280,292-298`、`strata_cli/monitor_commands.py:124-129,231-240`）。
- このコマンドは通信をしないため、URL 到達不能・認証拒否などサーバー応答に由来する失敗は `config show` では確認しません（`strata_cli/monitor_commands.py:132-139`）。

## 根拠

- parser と同じスコープの共通引数: `strata_cli/monitor_commands.py:20-26,96-103`
- `strata` への parser 登録と実行委譲: `strata_cli/cli.py:490-493,2165`
- `config show` の解決・表示処理: `strata_cli/monitor_commands.py:132-139,167-175`
- URL の形式、scheme、host、port の検証: `strata_cli/client.py:45-63`
- URL・環境変数・saved connection の選択、credential と timeout の解決: `strata_cli/connections.py:273-303`
- runtime error の出力形式と終了コード: `strata_cli/monitor_commands.py:124-129,231-240`
