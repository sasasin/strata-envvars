# `strata status --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--output` |
| 別名 | なし（`--json` は独立した真偽値オプションで、JSON を選ぶ alias） |
| 値 | `human` または `json` |

## 役割

status が取得する読み取り専用テレメトリ・スナップショットの表示形式を選びます。人向けの概要表示と、機械処理向けの JSON を切り替えます。出力先は stdout です。

## 使い方

```sh
strata status --output json
```

人向け表示は既定値なので `strata status` と同じです。短い指定として `strata status --json` も使えます。

## 値と既定値

parser は `human` と `json` だけを受理し、省略時は `human` です。ほかの値を渡すと `argparse` が usage とエラーを stderr に出し、通常の引数エラーとして終了します。`--output` 自体に短縮 alias はありません。別の `--json` フラグが設定された場合も実行時の machine 判定で JSON になります（`strata_cli/monitor_commands.py:28-33,167-169`）。

## 実行時の動作

`human` の場合は接続先からスナップショットを取得し、`render_view(..., "overview", width=80, height=24)` の結果を stdout に表示します。`--quiet` も指定した場合はこの表示を抑止しますが、スナップショットの取得は行われます（`strata_cli/monitor_commands.py:203-213`）。

`json` の場合はスナップショット全体を次の envelope に入れ、1行の JSON として stdout に出力します。`ensure_ascii=False` で非 ASCII 文字を保持し、`allow_nan=False` で非有限数を JSON に出しません。`--quiet` は machine 出力を抑止しません（`strata_cli/monitor_commands.py:167-169,203-208`）。

```json
{"schema_version":1,"ok":true,"snapshot":{}}
```

`--json` は parser 上 `store_true` の独立フラグですが、`run` 内で `a.output == "json" or a.json` と判定されるため、status では `--output json` と同じ machine 出力経路を選びます（`strata_cli/monitor_commands.py:31-33,167-169,203-208`）。

status のスナップショットは `Endpoint.snapshot()` を通じて取得されます。優先して `/v1/telemetry` を要求し、404 の場合だけ既存 server 用に `/metrics` と `/v1/status`、または `/v1/status` 単独へ fallback します。status は書き込み処理を行いませんが、指定または解決された Strata server へ HTTP(S) リクエストを送ります（`strata_cli/monitor_commands.py:195-204`; `strata_cli/client.py:101-152`）。

## 適用条件と副作用

- 接続先は `--url`、保存済み `--connection`、または既定のローカル server 解決から決まります。`--url` / `--connection` を明示しない場合、Terminal CLI に launch 機能があれば稼働中の `strata launch` 情報を参照し、見つからなければ接続設定解決へ進みます（`strata_cli/monitor_commands.py:36-44,195-199`）。
- リモート接続では HTTPS が必要です。HTTP は localhost、127.0.0.1、::1 に限定され、URL は server root 形式でなければなりません（`strata_cli/client.py:45-63`）。
- `--timeout` は接続 request の timeout に影響します。未指定時の既定値は 3 秒、Endpoint が受け付ける範囲は 0 より大きく 30 秒以下です。`--output` はこの設定を変更しません（`strata_cli/monitor_commands.py:20-25`; `strata_cli/client.py:84-95`）。
- 認証情報があれば Bearer Authorization header に設定されます。応答本文は最大 2 MiB まで読み、telemetry を正規化・sanitize してから表示します（`strata_cli/client.py:17,101-116,134-152`）。
- `--output` はファイルを作成せず、サーバー状態も変更しません。出力を pipe した先が閉じて発生する `BrokenPipeError` は成功扱い（終了コード 0）です（`strata_cli/monitor_commands.py:203-213,237-238`）。

## 出力とエラー

JSON モードでは失敗も JSON envelope `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を stdout に出します。human モードの失敗メッセージは `strata: ...` として stderr に出ます（`strata_cli/monitor_commands.py:118-123,231-236`）。主な失敗経路は次のとおりです。

- 接続 URL、timeout などの値が不正: 終了コード 2（`strata_cli/client.py:45-63,91-95`; `strata_cli/monitor_commands.py:235-236`）。
- 認証・権限失敗: HTTP 401/403 を終了コード 4 にする（`strata_cli/client.py:117-123`）。
- server 到達不能、その他 HTTP エラー、redirect、非 JSON / 不正 JSON 応答: `ClientError`。401/403 以外の既定終了コードは 3（schema 不整合など一部は 5）で、status の handler がこれを返します（`strata_cli/client.py:38-43,112-132,137-152`; `strata_cli/monitor_commands.py:231-234`）。
- 接続情報の解決エラー: `ConnectionError` に設定されたコードで終了します。ディレクトリや保存済み接続の問題などではコード 5 が使われます（`strata_cli/connections.py:47-50,72-90,128-146`; `strata_cli/monitor_commands.py:233-234`）。

CLI 引数の構文エラーは `strata_cli/cli.py` から共有 parser を使う通常の `argparse` 経路です。調査時点では安全な同一 revision の CLI `--help` 実行は行っていません。

## 根拠

- `strata_cli/cli.py:488-490` — トップレベル parser への status parser 登録。
- `strata_cli/monitor_commands.py:20-33` — status の接続設定、`--output` の値・既定値と `--json` / `--quiet`。
- `strata_cli/monitor_commands.py:167-169,195-213,231-238` — machine 判定、snapshot 表示、出力・例外経路。
- `strata_cli/client.py:17,38-63,84-152` — HTTP endpoint、URL・timeout 検証、snapshot fallback と失敗処理。
- `strata_cli/connections.py:47-50,72-90,128-146` — 接続設定の解決に関係するエラーと検証。
