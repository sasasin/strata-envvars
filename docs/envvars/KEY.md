# `KEY`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`apps/host/scripts/agent-flow-s4b.mjs` のフロー実行スクリプトが、任意の `METRICS` URL へ定期アクセスするときに Authorization ヘッダーを付けるための値です。Strata のエンジンや通常のサーバー起動処理が読む設定ではありません。このスクリプトは Playwright でアプリの実フローを動かし、画面と同時実行リクエスト数を確認するための開発用ツールです。

## 値と判定

| `KEY` の状態 | スクリプトが送るヘッダー |
|---|---|
| 未設定または空文字 | Authorization ヘッダーなし |
| 空でない文字列 | `authorization: Bearer <値>` |

文字列の trim、形式検証、大小文字の変換はしません。値の存在判定は JavaScript の truthiness なので、空文字だけがヘッダーを省略し、空白だけの値もそのまま `Bearer ` の後ろに送ります。

## 有効になる条件

`METRICS` が空でない場合に限り、スクリプトはサンプリングを開始します。`METRICS` が未設定または空文字なら `KEY` は参照されず、metrics の同時実行数チェックも行われません。`KEY` に設定しても、スクリプト以外のプロセスへ値を渡したり、エンジンの認証設定を変更したりはしません。

## 実行時の詳細

`startSampling()` は `METRICS` が設定されていると1秒ごとのタイマーを開始します。各回の `fetch()` で `process.env.KEY` を評価し、値が truthy なら Authorization ヘッダーを追加して `METRICS` の URL へアクセスします。環境値は静的キャッシュされず、サンプルごとに読み直されます。応答 JSON の `live.running.length`、または `live.slots` のうち `state` が `idle` 以外の数を読み、最大値 `peak` を更新します。フロー終了後は `METRICS` が設定されている場合に `peak >= 2` をチェックします。

`fetch()` と JSON 読み取りで発生した例外は catch され、ログ出力なしでその回のサンプルを捨てます。`KEY` 自体の値をログへ出す処理はありません。サーバーがこのヘッダーをどう認証・解釈するかは、このスクリプトの範囲外です。

## 根拠

- `apps/host/scripts/agent-flow-s4b.mjs:1-14` — スクリプトの用途、起動例、環境変数の説明。
- `apps/host/scripts/agent-flow-s4b.mjs:46-60` — `METRICS` の有無による開始条件、1秒ごとの fetch、`KEY` の truthiness 判定とヘッダー、失敗時の処理。
- `apps/host/scripts/agent-flow-s4b.mjs:95-114,158` — フロー中のサンプリング開始・停止と `peak >= 2` のチェック。
