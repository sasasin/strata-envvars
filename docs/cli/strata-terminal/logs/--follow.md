# `--follow`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--follow` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は一回だけ取得する |

## 役割

サーバーが保持する、秘匿情報を除いたリクエスト遷移を表示し、その後も新しい遷移をポーリングして追跡します。`logs` は読み取り専用コマンドとして登録されています（`strata_cli/monitor_commands.py:63-69`）。

## 使い方

```sh
strata logs --follow
strata logs --follow --output jsonl --interval 1
strata logs --url http://127.0.0.1:8095 --follow
```

リモートサーバーへ接続する場合は HTTPS、またはローカル SSH トンネルを使います。デフォルトの URL は `http://127.0.0.1:8095` です。接続先は `--url`、保存済み接続は `--connection NAME` で指定できます（`strata_cli/monitor_commands.py:20-25`、`strata_cli/connections.py:41-45,273-302`、`strata_cli/client.py:45-63`）。

## 値と既定値

`--follow` 自体に引数や設定可能な既定値はありません。ポーリング間隔は同じ `logs` コマンドの `--interval` で指定し、既定値は 2 秒、受理範囲は 0.5〜30 秒です。範囲外では終了コード 2 で失敗します（`strata_cli/monitor_commands.py:67-69,176-178`）。

接続タイムアウトは `--timeout` で指定でき、既定値は 3 秒、0 より大きく 30 秒以下です（`strata_cli/monitor_commands.py:20-25`、`strata_cli/connections.py:295-302`）。

## 実行時の動作

- 初回に telemetry snapshot を一度取得し、保持されているイベントを出力してから `--interval` 秒ごとに snapshot を取得します。後続の snapshot ではシーケンス番号をカーソルとして新着分を選び、欠けた番号があれば `gap`、サーバー instance が変われば `instance_change` のイベントも出します（`strata_cli/logs.py:25-57,101-138`）。
- 既定の `--output human` はイベントの人間向け表示です。`--output jsonl` はイベントごとに JSON オブジェクトを1行ずつ出力し、各行を flush します（`strata_cli/monitor_commands.py:70-72`、`strata_cli/logs.py:14-23,129-132`）。
- `--follow` と `--output json` の組み合わせは拒否されます。追跡中の JSON 出力には `--output jsonl` を使います。逆に `jsonl` は `--follow` なしでは拒否されます。`--json` は一回取得専用で、`--follow` との併用もできません（`strata_cli/monitor_commands.py:70-72,179-186`）。
- `--quiet` は人間向けの開始案内と再接続の進捗表示を抑えますが、イベント行の出力は続きます（`strata_cli/monitor_commands.py:168-169`、`strata_cli/logs.py:127-128,144-150`）。
- CLI は接続先を解決し、`Endpoint.snapshot()` を呼びます。snapshot は `/v1/telemetry` を優先し、404 の場合は `/metrics` と `/v1/status`、さらに `/v1/status` のみの経路へフォールバックします。読み取り先は許可された telemetry/status/metrics/health endpoint に制限され、応答はサニタイズされます（`strata_cli/monitor_commands.py:195-202`、`strata_cli/client.py:101-152,244-268,361-368`）。

## 適用条件と副作用

- `--source` の既定値 `runtime` が必要です。`--source harness` は共有 harness 活動を利用できず、終了コード 5 のエラーになります（`strata_cli/monitor_commands.py:66,187-188`）。
- 初回 snapshot で request activity が利用できない場合、または instance ID がない場合は追跡を開始できず、終了コード 5 になります。監視中に sequence が instance 変更なしで巻き戻った場合も同じく失敗します（`strata_cli/logs.py:25-40,105-126`）。
- 確認できる副作用は接続先への読み取りリクエストと端末への出力です。追跡カーソルはプロセス内だけで保持され、履歴をローカルに保存する処理はこの実装にありません（`strata_cli/logs.py:60-68,101-151`）。
- Ctrl+C は追跡を中断して正常終了コード 0 になります（`strata_cli/monitor_commands.py:241-244`）。

## 出力とエラー

- 人間向け出力は標準出力、接続切断・復旧の案内は標準エラーへ出ます。JSON Lines は標準出力へ逐次出力します（`strata_cli/logs.py:14-23,127-150`）。
- 接続エラーの終了コードが 3 のとき、追跡は最大3回まで試行し、最初の失敗時に再試行を標準エラーで案内します。3回失敗すると `request activity connection failed after 3 attempts` として終了コード 3 で失敗します。復旧時は案内を出して追跡を継続します（`strata_cli/logs.py:133-150`）。
- API エラーは、人間向けなら `strata: ...` を標準エラーへ、JSON/JSONL モードなら `{schema_version, ok: false, error}` を標準出力へ出します。CLI は例外に付属する終了コードを返します（`strata_cli/monitor_commands.py:124-129,231-240`）。

## 根拠

- parser 定義、間隔・出力の検証、コマンドから追跡実装への引き渡し: `strata_cli/monitor_commands.py:63-72,167-202`
- 初回イベント、差分・欠落の検出、poll loop、出力と再試行: `strata_cli/logs.py:14-57,101-151`
- endpoint の URL/timeout 検証、snapshot の取得と fallback、イベントのサニタイズ: `strata_cli/client.py:45-63,84-152,244-268,361-368`
- 接続先・credential 環境変数・既定値の解決: `strata_cli/connections.py:273-302`
