# `--timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--timeout` |
| 別名 | なし |
| 値 | 秒数（`float`） |

## 役割

監視対象サーバーへ送る各 HTTP 要求の timeout を指定します。対話モニターの更新間隔を指定する `--interval` とは別の値です。

## 使い方

```sh
strata monitor --url https://HOST --timeout 8 --once --json
```

`--url` を省略して保存済み接続または環境設定を使う場合も、`--timeout` は同じように適用されます。

## 値と既定値

parser は値を `float` として読み取り、既定値は `None`（未指定）です。接続設定の解決時に未指定を3.0秒へ変換します。明示値は0より大きく30以下でなければなりません。0、負数、30を超える値、`nan`、`inf` は受理されず、接続設定の検証でエラーになります。数値として解釈できない文字列は argparse の引数エラーになります。`--timeout` を複数回指定した場合は argparse の通常の挙動により最後の値が残ります。

## 実行時の動作

`strata monitor` は `monitor_commands.run()` で接続設定を解決し、得られた timeout を `Endpoint` に渡します。接続 URL の選択（`--url`、`--connection`、`STRATA_URL` 等）や資格情報の参照先とは独立して指定できます。実際の HTTP 要求では `urllib` の `open(..., timeout=...)` にこの値を渡します。

この値は要求ごとの待ち時間上限であり、コマンド全体の期限やポーリング周期ではありません。通常のスナップショットは `/v1/telemetry` を優先し、404 の場合に限って `/metrics`、さらに必要なら `/v1/status` へ順に問い合わせます。従って fallback 経路では複数要求がそれぞれこの timeout を使います。`--interval` は対話モニターの更新周期を指定し、parser 上の既定値は1秒です。

対話モニターの overview はスナップショット取得後に `/metrics` も問い合わせます。この追加要求にも同じ timeout が適用されますが、その失敗は overview の詳細モデルを利用不可にし、スナップショット自体のエラーにはしません。

## 適用条件と副作用

`strata monitor --once` と対話モニターの両方で、`Endpoint` のネットワーク要求に適用されます。`--json` は `--once` と併用する one-shot 出力であり、timeout 自体の値は変えません。接続先の保存やサーバー設定変更は行いません。

対話モニターでは要求失敗時にエラーを画面へ出し、最後のスナップショットがあれば失敗が続く間 stale として保持し、3回目以降は disconnected 状態になります。通信エラーは再試行され、間隔は指数的に増加し最大30秒（ジッターあり）です。timeout を短くしても、要求が完了する前に更新周期を短くするものではありません。

## 出力とエラー

one-shot の取得で timeout 等の通信エラーが起きると `ClientError` となり、通常出力では標準エラーに `strata: cannot reach Strata server: <例外型>` を出して既定終了コード3を返します。JSON モードでは同じエラーを `ok: false` の JSON として出します。無効な timeout は `strata: timeout must be greater than zero and at most 30 seconds` の設定エラー（`ConnectionError` の既定終了コード2）になります。対話モードでは `ClientError` が画面上のエラー・接続状態・再試行に反映され、コマンドを直ちに終了しません。

## 根拠

- `strata_cli/monitor_commands.py:20-25` — `--timeout` の parser 定義と `float` 型。`monitor` は同じ `_connection()` を呼び出す（`strata_cli/monitor_commands.py:49-52`）。
- `strata_cli/monitor_commands.py:189-199` — monitor の適用条件、接続設定への受け渡し、`Endpoint` の生成。
- `strata_cli/connections.py:273-302` — 正の値かつ30秒以下という検証、既定3秒、接続設定内での優先順位。
- `strata_cli/client.py:84-110` — Endpoint の範囲検査と HTTP 要求への timeout の受け渡し。
- `strata_cli/client.py:117-152` — HTTP/通信エラー処理とスナップショットの fallback 経路。
- `strata_cli/monitor_commands.py:203-236` — one-shot の出力とエラー処理。
- `strata_cli/monitor.py:267-305` — 対話モードの poll、stale/disconnected 状態および再試行。
- `strata_cli/monitor.py:310-320` — overview 用 `/metrics` 要求の失敗をスナップショット失敗と分ける処理。
- `strata_cli/monitor_commands.py:56-60` — `--interval` の独立した既定値（1秒）。
