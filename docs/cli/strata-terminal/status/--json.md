# `strata status --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--json` |
| 別名 | なし（`--output json` が同じ出力形式を選ぶ） |
| 値 | 値を取らない真偽フラグ。省略時 `false` |

## 役割

読み取り専用の telemetry snapshot を、人向け表示ではなく機械処理向け JSON で標準出力へ出します。status parser の説明も「one read-only telemetry snapshot」で、`--json` は `--output json` の alias と定義されています（`strata_cli/monitor_commands.py:28-33`）。

## 使い方

```sh
strata status --json
```

接続先や認証情報は、必要に応じて同じコマンドの `--url`、`--connection`、`--credential-env` で指定できます。これらは `status` parser に共通接続引数として追加されます（`strata_cli/monitor_commands.py:20-33`）。

## 値と既定値

- `argparse` の `store_true` なので値は不要です。指定すると `a.json` が真になり、省略時は偽です（`strata_cli/monitor_commands.py:32`）。
- `--output` は `human` または `json` を受け取り、既定値は `human` です（`strata_cli/monitor_commands.py:31`）。`--json` と `--output json` を両方指定しても、どちらも同じ JSON 出力経路を選びます。`--json --output human` の場合も `--json` が機械出力を選びます（`strata_cli/monitor_commands.py:168, 203-207`）。
- `--json` 自体に追加の値検証はありません。重ねて指定しても真偽フラグのままです。

## 実行時の動作

`run()` は `--output json` または `--json` を機械出力として判定します。status は `Endpoint.snapshot()` を取得し、成功時は標準出力に次の包みを1行の JSON として出します。シリアライズは UTF-8 文字をそのまま保ち、非有限数値があれば許容しません（`strata_cli/monitor_commands.py:167-169, 203-208`）。

```json
{"schema_version":1,"ok":true,"snapshot":{}}
```

上の空 `snapshot` は形式を示すための省略例であり、実際の snapshot のフィールドはサーバー応答と正規化結果によります。クライアントはまず `/v1/telemetry` を要求し、404 のときに `/metrics` と `/v1/status`、または `/v1/status` のみへフォールバックします。telemetry schema version が `1` 以外なら失敗します（`strata_cli/client.py:134-152`）。

status の接続先は `--url` / `--connection` など既存の接続解決に従い、JSON 指定は接続先や認証の選び方を変えません。明示 URL と接続名の同時指定は拒否されます（`strata_cli/connections.py:273-302`）。どちらもなければ、`STRATA_CONNECTION` / `STRATA_URL`、既定の `http://127.0.0.1:8095` の順で解決されます。status は明示 URL・接続名がないときに限り、起動中の `strata launch` の接続先情報を先に探します（`strata_cli/monitor_commands.py:36-46, 195-199`; `strata_cli/connections.py:277-302`）。

## 適用条件と副作用

`--json` は出力形式だけを切り替えます。status は snapshot を取得するためサーバーへの HTTP GET を行います。認証値がある場合は Bearer token として送り、要求先は telemetry、metrics、status の読み取り用 endpoint に限定されています（`strata_cli/client.py:101-110, 134-152`）。ローカル/リモート URL の形式と HTTPS 制約は `Endpoint` の URL 検証に従い、リモート監視には HTTPS（またはローカル SSH tunnel）が必要です（`strata_cli/client.py:45-63`）。

`--quiet` を併用しても JSON 出力は抑止されません。`quiet` は機械出力時に無効化されます（`strata_cli/monitor_commands.py:168-169, 205-212`）。このコマンド経路で status snapshot の保存・設定変更は行われません。

## 出力とエラー

- 成功時は `schema_version: 1`、`ok: true`、`snapshot` を持つ JSON を標準出力へ出し、終了コード `0` を返します（`strata_cli/monitor_commands.py:203-208`）。
- `ClientError` は `ok: false` と `error.code`（整数終了コード）・`error.message` を含む JSON を出力します（`strata_cli/monitor_commands.py:124-129, 231-232`）。接続失敗や不正応答は通常コード `3`、HTTP 401/403 は `4`、互換性のない telemetry schema は `5` です（`strata_cli/client.py:38-42, 117-131, 142-144`）。
- URL・接続設定や timeout の検証エラーも JSON 形式で報告されます。timeout は既定3秒、0より大きく30秒以下で、範囲外は拒否されます（`strata_cli/connections.py:295-302`; `strata_cli/monitor_commands.py:124-129, 235-236`）。
- HTTP redirect は追跡せず失敗として報告されます。応答は `application/json` でなければならず、本文上限は2 MiBです（`strata_cli/client.py:79-80, 101-125`）。

## 根拠

- parser 定義とオプション scope: `strata_cli/monitor_commands.py:20-33`。トップレベル CLI への登録と handler 委譲: `strata_cli/cli.py:488-493, 2153-2165`。
- JSON 出力判定、snapshot 呼び出し、成功/失敗 envelope: `strata_cli/monitor_commands.py:124-129, 167-169, 195-208, 231-244`。
- 接続情報の優先順位・既定 timeout: `strata_cli/connections.py:273-302`。
- HTTP 要求、応答検証、snapshot endpoint のフォールバック: `strata_cli/client.py:45-63, 79-152`。
- 索引上のコマンド階層と文書リンク: `docs/cli/README.md:987-997`（調査対象リポジトリ側）。

