# `UP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/chat-growth-proxy.mjs` の転送先ポートを指定します。このスクリプトは冒頭で使い捨ての計測用プロキシと説明され、`chat-growth.mjs` からチャット画面のメモリ・DOM・メインスレッド時間を測る際に必要なものとして記載されています。通常の Strata engine や一般向け CLI の設定ではありません（`apps/host/scripts/chat-growth-proxy.mjs:1-3`, `apps/host/scripts/chat-growth.mjs:1`).

## 値と判定

| 入力 | `UP` 定数の値 |
|---|---|
| 未設定 | `18791` |
| 設定あり | `Number(process.env.UP)` の結果 |

`??` を使うため、未設定の場合だけ既定値になります。空文字は既定値に置き換わらず、`Number("")` の結果である `0` になります。値を整数として検証したり、範囲に clamp したり、CLI 引数と比較したりするコードはありません。数値に変換できない文字列は `NaN` になりますが、その値に対する明示的な検証や fallback もありません。ソースは変換結果を Node の `http.request` の `port` に渡すため、無効値が与えられた場合の最終的な扱いは同ランタイム側に依存し、このスクリプトからは確定できません（`apps/host/scripts/chat-growth-proxy.mjs:3,23`).

## 有効になる条件

`apps/host/scripts/chat-growth-proxy.mjs` を起動した場合にだけ使われます。OS、GPU backend、build macro、モデル状態による分岐はありません。このスクリプトは別の `PORT` 環境変数で自身の待受ポートを決めますが、`UP` は転送先ポート用です。CLI 引数による上書きはありません（`apps/host/scripts/chat-growth-proxy.mjs:1-4,23,26`).

## 実行時の詳細

モジュール読み込み時に `UP` を一度数値化して定数に保持します。プロセス起動後に環境値を変更してもこの定数は再評価されません。`POST` で URL が `/api/chat/stream` から始まるリクエストには、モックの NDJSON 応答を返すため `UP` は使いません。それ以外のリクエストでは、元の URL・method・headers を保って `127.0.0.1:UP` に HTTP リクエストを送り、受け取った status と headers を返して response body を pipe します。転送リクエストの `error` イベントでは HTTP 502 を返し、本文を空で終えます。待受開始時には `proxy on` と待受ポートをログに出します（`apps/host/scripts/chat-growth-proxy.mjs:9-26`).

この環境変数の読み取り先は候補索引に載った名前と一致します。確認した参照は上記の計測用スクリプトのみで、Strata の通常の実行エンジンや製品サーバーが `UP` を読む箇所はありません。

## 根拠

- `apps/host/scripts/chat-growth-proxy.mjs:1-4` — スクリプトの用途、既定値、および環境値の数値変換。
- `apps/host/scripts/chat-growth-proxy.mjs:9-26` — モック応答と転送経路、502 応答、待受ログ。
- `apps/host/scripts/chat-growth.mjs:1` — 計測スクリプトが使い捨て host とこの proxy を必要とする旨。
