# `ANSWER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`ANSWER` は Strata の通常のアプリ設定ではなく、HTTP で host を操作する Node.js スクリプト `apps/host/scripts/agent-http.mjs` の承認カード自動応答用です。ストリームから `agent-tool` の `state === 'proposed'` を受け取ったとき、`ANSWER` が空でなければ `/api/chat/approval` に decision を送ります。これは host サーバー自身が環境変数を読む機能ではありません（`apps/host/scripts/agent-http.mjs:34-59`）。

## 値と判定

| `ANSWER` の状態 | スクリプトの動作 |
|---|---|
| 未設定 | 自動応答しない |
| 空文字 | JavaScript の falsy 値なので自動応答しない |
| 空でない文字列 | `state === 'proposed'` のカードごとに承認 API を呼ぶ。値の文字列自体は正規化せず、基本的に `decision` として送る |

サーバーは `decision` が小文字の `approve` または `deny` のどちらかでなければ HTTP 400 を返します。したがって `ANSWER=approve` は承認、`ANSWER=deny` は拒否になりますが、`ANSWER=1`、大文字表記、前後に空白のある値などは有効な decision ではありません。スクリプト側には値の検査や fallback はありません（`apps/host/scripts/agent-http.mjs:58-59`; `apps/host/server/index.mjs:1965-1971`）。

ただし `APPROVE_MATCH` が空でなく、正規表現が `${f.tool.target} ${f.tool.effect}` に大文字小文字を無視して一致した場合は、`ANSWER` の値にかかわらず `approve` を送ります。一致しなければ `ANSWER` を送ります。正規表現は JavaScript `RegExp` にそのまま渡されます。無効な正規表現は `stream` の frame 処理中に例外となり、その frame の承認リクエストは送られません。これは `onFrame` callback の例外処理とは別の位置で評価されるため、`onFrame error ...` ではなく `stream` の失敗として上位へ伝わります（`apps/host/scripts/agent-http.mjs:48,56-59`）。

## 有効になる条件

- `agent-http.mjs` を実行し、その実行プロセスに `ANSWER` を設定していること。
- ストリームが `agent-tool` の `proposed` frame を返すこと。承認対象でない tool frame や、承認を必要としない処理には作用しません（`apps/host/scripts/agent-http.mjs:49-59`）。
- 実際に承認カードを出すには Manual の `ask` policy が必要です。Strata の mode 定義では Manual が `approval: 'ask'`、Plan と Bypass は `approval: 'never'` です（`apps/host/server/agent/profile.mjs:34-44`）。このスクリプトの `plan` コマンドは `MODE` 未設定時に `manual` を使いますが、`stream` コマンドの既定 mode は `bypass` です（`apps/host/scripts/agent-http.mjs:83-86,144-150`）。そのため `ANSWER` を設定しても、既定の `stream` 実行では通常この承認カード経路に入りません。`plan` コマンドの `MODE` を `plan` / `bypass` にした場合も同様です。
- `/api/chat/approval` が対象 chat と tool ID に対応する pending approval を解決できること。異なる chat の ID や、期限切れ・再起動後など既に待機していない承認は受け付けられません（`apps/host/server/index.mjs:1965-1971`; `apps/host/server/agent/agent-bridge.mjs:1255-1278`）。

## 実行時の詳細

スクリプトは `process.env.ANSWER` を `proposed` frame ごとに参照し、値を初期化時にキャッシュしません。外部から起動後のプロセス環境を書き換えても Node.js プロセスの値は変わりませんが、同じプロセス内で `process.env.ANSWER` が変更される実装があれば後続 frame で再評価されます。子プロセスへの転送処理はこのスクリプトにありません。

API 呼び出しは待たずに開始されます。成功時は `-> ${process.env.ANSWER} ${f.tool.id}` を出力します。このログは実際に送った decision と一致しない場合があります。たとえば `APPROVE_MATCH` が一致して `approve` を送っても、ログには `ANSWER` の値が表示されます。API 呼び出し失敗時は `answer failed: ${e.message}` を出力します。API は不正な decision や不正な request に 400、待機中でない承認などに 409 を返し、スクリプトの HTTP helper は status と応答エラーを例外メッセージに含めます（`apps/host/scripts/agent-http.mjs:18-23,58-59`; `apps/host/server/index.mjs:1967-1971`; `apps/host/server/agent/agent-bridge.mjs:1263-1277`）。

## 根拠

- `apps/host/scripts/agent-http.mjs:34-59` — stream frame の受信、`proposed` 判定、`ANSWER` / `APPROVE_MATCH` の読み取りと API 呼び出し。
- `apps/host/scripts/agent-http.mjs:83-86,144-150` — `stream` と `plan` コマンドの mode 指定。
- `apps/host/server/agent/profile.mjs:34-44` — Manual / Plan / Bypass の approval policy。
- `apps/host/server/index.mjs:1965-1971` — approval API の body 検査と status code。
- `apps/host/server/agent/agent-bridge.mjs:1255-1278` — pending approval の特定、期限切れ時の失敗、承認 / 拒否の転送。
