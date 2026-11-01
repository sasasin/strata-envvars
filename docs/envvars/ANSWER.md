# `ANSWER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数の挙動は対象外です。

## 役割

`ANSWER` は、同梱の HTTP 操作スクリプト `apps/host/scripts/agent-http.mjs` が、エージェントから届いた承認待ちツールカードに自動回答するための値です。Strata の推論エンジンやホストの一般設定としては読み取られず、このスクリプトを実行した場合だけ使われます。候補一覧には載っていますが、通常のアプリ実行時の環境変数ではなく、この同梱スクリプト上の読み取りです。

## 値と判定

Node.js の `process.env.ANSWER` を文字列として参照し、真偽値判定と `decision` の値に使います。数値変換や文字列の正規化はしません。

| 状態・値 | 動作 |
|---|---|
| 未設定 | 偽値となり、自動回答しない。 |
| 空文字 | 偽値となり、自動回答しない。 |
| 空でない値（例: `approve`, `deny`, `0`, `false`） | 真値となり、自動回答を試みる。`APPROVE_MATCH` が該当しない場合、その文字列をそのまま `decision` に送る。 |

承認 API が受け付ける `decision` は文字列 `approve` または `deny` のみです。それ以外の空でない値もスクリプト側では有効化条件を満たしますが、API は HTTP 400 とエラー本文 `sessionId, toolId and decision (approve or deny) are required` を返します。スクリプトはこの失敗を捕捉してログに出します。値に対する trim、大小文字変換、fallback はありません。

## 有効になる条件

- スクリプトが `stream()` で受信した `agent-tool` フレームの `f.tool.state` が `proposed` であること。
- `ANSWER` が空でないこと。
- `APPROVE_MATCH` も空でなく、正規表現が `f.tool.target` と `f.tool.effect` を連結した文字列に大文字小文字を無視して一致した場合は、`ANSWER` の値にかかわらず `approve` を送ります。一致しない場合、または `APPROVE_MATCH` が未設定・空の場合は `ANSWER` を送ります。正規表現のコンパイルには `new RegExp(value, 'i')` を使います。
- 実際に `proposed` カードが出るかはリクエストのモードやツールの状態に依存します。たとえば `stream` コマンドはモードの既定値が `bypass` ですが、`plan` コマンドの共通リクエストは `MODE` がなければ `manual` です。値を設定しただけで、あらゆる実行経路のツールが回答対象になるわけではありません。

コマンドライン引数による `ANSWER` の上書きはありません。値は各 `proposed` フレームの処理時に `process.env` から参照され、スクリプト内に `ANSWER` のキャッシュや既定値はありません。

## 実行時の詳細

条件を満たすとスクリプトは `/api/chat/approval` に `sessionId`、`toolId`、選択した `decision` を POST します。ホストは `sessionId` / `toolId` が文字列で、decision が `approve` または `deny` であることを検査します。該当する待機中の承認がなければ 409（期限切れ）または 400 を返します。ホストは有効な承認を対応する待機イベントへ送り、`approve` を `allowed-once`、`deny` を `rejected` に対応させます。

POST 成功時はスクリプトが `-> ${process.env.ANSWER} ${f.tool.id}` を出力します。この表示は実際に送った decision ではなく `ANSWER` の値なので、`APPROVE_MATCH` の一致で `approve` を送った場合も `ANSWER` の文字列が表示されます。失敗時は `answer failed: ${e.message}` を出力します。`ANSWER` に有効な値を置いたことだけでプロセスが終了する処理はありません。

## 根拠

- `apps/host/scripts/agent-http.mjs:34-60` — フレーム処理、`proposed` と `process.env.ANSWER` の条件、`APPROVE_MATCH` による decision 選択、POST と成功・失敗ログ。
- `apps/host/scripts/agent-http.mjs:83-86,144-150` — `stream` コマンドの既定モードが `bypass`、`plan` コマンドの既定モードが `manual`。
- `apps/host/server/index.mjs:1942-1949` — 承認 API の入力検証、成功・失敗時の HTTP 応答。
- `apps/host/server/agent/agent-bridge.mjs:1165-1188` — 待機中承認の照合と、承認／拒否の結果の配送。
- `docs/envvars/000_envvers.md:36` — 候補一覧に `ANSWER` が掲載されていること。
