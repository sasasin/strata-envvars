# `REASON_TOKENS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/chat-growth-proxy.mjs` 専用の値です。`POST /api/chat/stream` に対し、実際のモデル応答ではなく、合成した `reasoning` NDJSON フレームを何回出すかを決めるループの目標値に使われます。Strata エンジンや通常のサーバー応答の reasoning token 数を設定するものではありません。このスクリプトの先頭コメントは、demo host を変更せず当該ストリームだけを長い定型応答に置き換える使い捨てプロキシと説明しています（`apps/host/scripts/chat-growth-proxy.mjs:1,9-21`）。

## 値と判定

起動時に `Number(process.env.REASON_TOKENS ?? 3000)` で一度だけ数値へ変換します。環境変数が未設定（`undefined`）なら既定値は `3000` です。空文字は nullish ではないため既定値にならず、`Number('')` の結果である `0` になります。入力を整数として検証・丸めたり、範囲制限したりする処理はありません。

| 値 | ループへの効果 |
|---|---|
| 未設定 | 目標値 `3000`。カウンターが 9 ずつ増えるので `reasoning` フレームを 334 回出す |
| `0`、空文字、数値化後 0 以下 | `sent < REASON` が最初から偽となり、`reasoning` フレームを出さない |
| 正の有限数 | 目標値に達するまで 9 ずつ進む。フレーム数は `ceil(REASON / 9)` 回（正の小数でも最低 1 回） |
| 数値に変換できない文字列 | `Number(...)` は `NaN` を返し、比較 `0 < NaN` が偽となるためフレームを出さない |
| `Infinity` | 有限のカウンターが目標値未満のままなのでループが終了しない |

`Number()` が受け付ける数値表記は JavaScript の変換規則に従い、コード側に独自の形式検査はありません。たとえば空白だけの文字列も数値 0 になります。大きな正数では目標値分の反復が長く続き得ます。カウンターは tokenizer の token 数ではなく、各フレーム後に固定値 9 ずつ増える値です。そのため、変数名に `TOKENS` とありますが、実際の token 数を数えたり保証したりする実装ではありません（`apps/host/scripts/chat-growth-proxy.mjs:4,15-18`）。

## 有効になる条件

- 値を読むのはこの Node.js スクリプトだけです。ソース全体の完全一致検索でも他の読み取り箇所は見つかりませんでした。
- `http.createServer` が受け取ったリクエストが `POST` で、URL が `/api/chat/stream` で始まる場合に限り、設定値が reasoning フレーム数の目標に使われます。それ以外の要求は上流 `127.0.0.1:<UP>` に転送されます（`apps/host/scripts/chat-growth-proxy.mjs:9-10,23-25`）。
- スクリプトは listen 時に `127.0.0.1` に bind します。ポートは別変数 `PORT`（既定 `18790`）で決まります（`apps/host/scripts/chat-growth-proxy.mjs:3,26`）。
- 関連する `chat-growth.mjs` は、使い捨て host、当該 proxy、Chrome を必要とする測定スクリプトとして記述されています。`REASON_TOKENS` は CLI 引数、モデル設定、サーバーの一般設定から読み取られません（`apps/host/scripts/chat-growth.mjs:1`）。

## 実行時の詳細

環境変数の読み取りと変換はスクリプトのモジュール評価時に行い、`REASON` 定数に保持します。プロセス起動後に環境を書き換えても再評価されません。受信した該当 POST は本文を最後まで読み、HTTP 200 と `application/x-ndjson` を返して `start` フレームを出した後、目標値に達するまで `reasoning` フレームを順に書きます。その後 `delta` と `stats` フレームによる定型返信を出し、`done` で終了します（`apps/host/scripts/chat-growth-proxy.mjs:4,9-21`）。

このファイルでは `REASON_TOKENS` 固有の警告や値検証エラー、終了コード変更は実装されていません。通常の有限値では `proxy on <port>` が listen 完了時に標準出力へ出ます（`apps/host/scripts/chat-growth-proxy.mjs:26`）。数値化できない値や 0 以下は reasoning 部分を省いて後続の定型返信へ進み、`Infinity` は reasoning ループから抜けません。

## 根拠

- `apps/host/scripts/chat-growth-proxy.mjs:1-4`: スクリプトの用途、環境変数と既定値の変換。
- `apps/host/scripts/chat-growth-proxy.mjs:9-21`: 対象リクエストの判定、レスポンス形式、reasoning ループと後続フレーム。
- `apps/host/scripts/chat-growth-proxy.mjs:23-26`: その他の要求の転送と listen の bind / 起動ログ。
- `apps/host/scripts/chat-growth.mjs:1`: 測定用スクリプトの前提。
