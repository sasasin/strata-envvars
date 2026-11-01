# `PLAIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `## main...origin/main` で、変更はありません。外部ライブラリの環境変数は対象外。

## 役割

`PLAIN` はエンジンや通常のアプリ設定ではなく、`apps/host/scripts/agent-http.mjs` と `apps/host/scripts/agent3-http.mjs` の HTTP 診断スクリプトが使うスイッチです。これらのスクリプトの `stream` コマンドと、`agent-http.mjs` の `effort` コマンドで、空でない値があるとチャット要求に `agent: false` を付けます。サーバーはその要求で agent 経路を飛ばし、通常のチャット処理へ進みます。

## 値と判定

値を parse せず、JavaScript の truthiness で判定します。`process.env` の値は文字列なので、空文字以外の値はすべて真です。

| `PLAIN` の状態 | スクリプトが送る値 |
|---|---|
| 未設定 | `stream`: `agent` プロパティを省略。`effort`: `agent: undefined` となり、JSON 化で省略 |
| 空文字 | 未設定と同じく `agent` を省略 |
| 空でない値 | `agent: false`。`1`、`0`、`true`、`false` などの文字列はいずれも同じ扱い |

CLI 引数による `agent` 指定はありません。`stream` コマンドではスクリプトが要求オブジェクトを組み立て、`effort` でも同じ環境変数判定を各要求に適用します。別の環境変数による `PLAIN` の既定値や変換はありません。

根拠: `apps/host/scripts/agent-http.mjs:83-86,195-205`, `apps/host/scripts/agent3-http.mjs:72-75`。

## 有効になる条件

`agent-http.mjs` では `stream` と `effort`、`agent3-http.mjs` では `stream` の各コマンドでだけ参照されます。他のコマンドでは `PLAIN` を読みません。両スクリプトとも HTTP で Strata host の `/api/chat/stream` に要求を送る診断用スクリプトです。エンジンの C++/CUDA/HIP/SYCL コードが読む変数ではなく、`STRATA_DOORBELL_PLAIN` とは別の名前です。

サーバーでは `STRATA_AGENT=off` も agent を使わない条件です。要求に `agent: false` がある場合も agent を起動せず、agent を使わないという notice は出さずに通常の `runTurn` へ進みます。`runTurn` に渡す `useTools` は `body.useTools === true` の場合だけ真になるため、この診断スクリプトが送る要求（`useTools` を指定しない）では通常チャット側のツールも有効になりません。`PLAIN` が未設定または空文字でも、サーバーの agent 状態、モデルの有無など他条件で agent が実行されない場合があります。

根拠: `apps/host/server/index.mjs:2001-2021,2023-2038`。

## 実行時の詳細

環境変数は各コマンドの要求を作る時に読む通常の `process.env` 参照で、スクリプト側に値の cache はありません。`stream` 要求は `JSON.stringify(body)` で host に送られます。host は `/api/chat/stream` で `body.agent === false` を判定すると agent 経路をスキップし、`runTurn` に進みます。サーバーの `STRATA_AGENT=off` が設定されている場合も agent 経路は使いません。

`PLAIN` 自体について、スクリプトに警告・ログ・終了処理はありません。要求の後は通常のストリーム応答をスクリプトが受け取ります。HTTP 要求が失敗したときは `stream()` が `stream -> <status> <body>` のエラーを throw しますが、これは HTTP エラー処理であり、`PLAIN` の値に対する専用エラーではありません。リポジトリの設計資料・ユーザー向け文書にはこのスイッチの説明は見つからず、コード上の用途は診断スクリプト内に限られます。

根拠: `apps/host/scripts/agent-http.mjs:35-37,83-86,195-205`, `apps/host/scripts/agent3-http.mjs:35-37,72-75`, `apps/host/server/index.mjs:1980-1999,2001-2038`。

## 根拠

- `apps/host/scripts/agent-http.mjs:83-86` — `stream` コマンドでの `PLAIN` 判定と要求 JSON。
- `apps/host/scripts/agent-http.mjs:195-205` — `effort` コマンドでの `PLAIN` 判定。
- `apps/host/scripts/agent3-http.mjs:72-75` — 別の HTTP 診断スクリプトにある `stream` 判定。
- `apps/host/server/index.mjs:2001-2021` — `agent: false` および `STRATA_AGENT=off` の agent スキップ経路。
- `apps/host/server/index.mjs:2023-2038` — agent をスキップした後に通常の `runTurn` を呼び、`useTools` を渡す処理。
