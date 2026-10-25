# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection list` |
| オプション | `--json` |
| 別名 | なし（`--output json` も指定可能） |
| 値 | 値なしの真偽フラグ。省略時は `false` |

## 役割

保存済み接続の一覧を、人向け表示ではなく1つの JSON オブジェクトとして stdout に出力します。読み取り専用の一覧コマンドで、接続先サーバーへの通信は行いません。

## 使い方

```sh
strata connection list --json
```

同じ出力形式は `strata connection list --output json` でも選べます。

## 値と既定値

`--json` は値を取りません。未指定時は人向け出力です。`--output` の受理値は `human` と `json`、既定値は `human` です。実装上は `--json` が真、または `--output json` のとき JSON 出力になります。フラグを繰り返しても真偽値の指定として扱われます。`--output jsonl` はこのコマンドでは受理されません。

## 実行時の動作

成功時は次の形の JSON を1行で stdout に出します。`connections` は接続 ID 順に並びます。

```json
{"schema_version":1,"ok":true,"connections":[{"id":"work","url":"https://example.invalid","prefix":"","credential_env":"STRATA_TELEMETRY_KEY","revision":"0123456789abcdef"}]}
```

接続記録には資格情報そのものではなく、資格情報を参照する環境変数名が含まれます。`--json` は結果の形式を切り替えるだけで、保存先や一覧内容は変更しません。保存先は `STRATA_CONNECTION_DIR`（指定時は絶対パスが必要）、Windows では `%APPDATA%/Strata/connections`、その他の環境では `$XDG_CONFIG_HOME/strata/connections` または `~/.config/strata/connections` です。

一覧処理は保存先の `*.json` ファイルを列挙し、名前規則に合うファイルを読み込みます。保存先が存在しなければ空配列を返します。名前が規則に合わないファイルは一覧対象から除外されます。有効な記録は `id`、`url`、`prefix`、`credential_env`、内容から計算した `revision` を含みます。読み込めない、または値が不正な記録は一覧全体を失敗させず、その項目を `{"id":"…","error":"…"}` として返します。

## 適用条件と副作用

保存先ディレクトリが存在する場合、ディレクトリであることと POSIX 環境で所有者専用であることを確認します。各記録も通常ファイルか、4 KiB 以下か、POSIX 環境で所有者専用かを確認し、スキーマと値を検証します。100件を超える対象ファイルがある場合は一覧処理をエラーにします。

このコマンドは接続記録を読み取るだけで、ディレクトリやファイルの作成・更新、環境変数からの資格情報読み出し、ネットワーク通信を行いません。`--quiet` と併用しても JSON は抑止されません。

## 出力とエラー

成功時は stdout に JSON オブジェクトを出し、終了コード `0` を返します。実行時エラーも JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":N,"message":"…"}}` の形式で出力されます。たとえば `STRATA_CONNECTION_DIR` が相対パスならコード `2`、保存先の権限・形式が不正、または一覧上限を超えた場合はコード `5` です。無効な個別記録は前述のとおり一覧内の `error` 項目で示され、一覧コマンド自体は成功扱いです。未知の引数や不正な `--output` 値は argparse の引数エラーとなります。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection list` parser と `--output` / `--json` / `--quiet` の定義。
- `strata_cli/monitor_commands.py:124-129` — JSON モードのエラー形式と通常エラーの stderr 出力。
- `strata_cli/monitor_commands.py:140-143,162-164` — 一覧データの取得、成功ペイロード、JSON 出力と終了コード。
- `strata_cli/monitor_commands.py:167-175,231-240` — JSON モードの判定、ローカル処理への分岐、接続・値・ファイルエラーの処理。
- `strata_cli/connections.py:72-90` — 保存先決定とディレクトリ検査。
- `strata_cli/connections.py:128-164` — 個別記録の検査、一覧順序、空一覧、100件上限、不正記録の扱い。
