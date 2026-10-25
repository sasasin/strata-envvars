# `--timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--timeout` |
| 別名 | なし |
| 値 | 秒数（`float`） |

## 役割

`strata status` がサーバーから読み取り専用 telemetry snapshot を取得するとき、各 HTTP 要求に設定する timeout を指定します。コマンド全体の実行期限ではありません。

## 使い方

```sh
strata status --url https://HOST --timeout 8 --json
```

`--url` を省略して保存済み接続、環境設定、または `strata launch` が起動中の接続先を使う場合にも指定できます。

## 値と既定値

parser は値を `float` として読み取り、既定値は `None`（未指定）です。接続設定の解決時に未指定は3.0秒になります。明示値は0より大きく30以下でなければなりません。0、負数、30を超える値、`nan`、`inf` は接続設定の検証で拒否され、数値として解釈できない値は argparse の引数エラーになります。複数回指定した場合は argparse の通常動作により最後の値が使われます。

## 実行時の動作

`status` parser は共通接続オプションとして `--timeout` を登録します。実行時には接続設定解決関数へ値を渡し、その結果を `Endpoint` に設定します。接続先や資格情報の選択（`--url`、`--connection`、`STRATA_URL` など）とは独立して上書きできます。環境変数から timeout を指定する経路は、この接続解決処理にはありません。

`Endpoint` は各 HTTP 呼び出しの `urllib` timeout にこの秒数を渡します。snapshot はまず `/v1/telemetry` を要求し、404 の場合に `/metrics`、さらに `/metrics` も404なら `/v1/status` へ順に問い合わせます。fallback では複数の HTTP 要求があり、それぞれに同じ timeout が適用されます。各要求の待ち時間を制限するもので、snapshot 全体を一つの期限で打ち切る値ではありません。

## 適用条件と副作用

`strata status` の snapshot 取得で発生するネットワーク要求に適用されます。`--json` と `--output` は結果の形式、`--quiet` は人向け情報出力を制御し、timeout の範囲や要求先は変えません。コマンド自体は読み取り専用 snapshot を取得し、timeout によるサーバー設定変更やローカル設定保存はありません。

## 出力とエラー

timeout 等の通信失敗は `ClientError` となり、既定の終了コード3で処理されます。通常出力では `strata: cannot reach Strata server: <例外型>` を標準エラーに出し、JSON 出力では `ok: false` のエラー JSON を標準出力に出します。無効な値は `ConnectionError` として終了コード2になり、通常出力では `strata: timeout must be greater than zero and at most 30 seconds` を標準エラーに出します。引数の数値変換に失敗した場合は argparse の使用法エラーです。

## 根拠

- `strata_cli/monitor_commands.py:20-33` — `--timeout` の `float` parser 宣言、`status` への登録、および status 固有の出力オプション。
- `strata_cli/monitor_commands.py:195-213` — status の接続解決、Endpoint 生成、snapshot 取得、human/JSON 出力。
- `strata_cli/connections.py:273-302` — timeout の検証、未指定時3.0秒、接続設定に対する独立性。
- `strata_cli/client.py:84-110` — Endpoint の範囲検査と各 HTTP 要求への timeout の受け渡し。
- `strata_cli/client.py:117-152` — HTTP/通信エラーと snapshot fallback の経路。
- `strata_cli/client.py:38-42` — `ClientError` の既定終了コード。
- `strata_cli/monitor_commands.py:124-129,231-240` — 標準エラーまたは JSON エラー出力と例外コード処理。
- `strata_cli/cli.py:490-493` — Terminal CLI parser への status コマンド登録。
- `strata_cli/cli.py:2223-2231` — 共通 parser による引数エラー処理。
