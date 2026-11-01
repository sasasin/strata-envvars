# `APPROVE_MATCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`APPROVE_MATCH` は、同梱の開発・操作用 HTTP スクリプト `apps/host/scripts/agent-http.mjs` で、承認待ちツールカードへの自動回答を選ぶ正規表現です。Strata のエンジンや通常のホスト設定では読まれず、このスクリプトのチャット stream 処理だけで参照されます。自動回答には別変数 `ANSWER` も必要です。

## 値と判定

| `APPROVE_MATCH` の状態 | `ANSWER` が空でない場合に送る decision |
|---|---|
| 未設定または空文字 | `ANSWER` の値 |
| 空でない文字列がカード情報に一致 | `approve` |
| 空でない文字列が一致しない | `ANSWER` の値 |

比較は `new RegExp(value, 'i').test(...)` です。値は JavaScript の正規表現パターンとして使われ、大文字小文字を区別せず、対象文字列の部分一致を調べます（アンカーがなければ部分一致）。正規表現の区切り `/.../` は不要です。空白や `0`、`false` も空でない文字列としてパターンになります。未設定・空文字では match 分岐を使いません。

照合対象は `` `${f.tool.target} ${f.tool.effect}` `` です。両フィールドを空白一つで連結した文字列に対して検査します。正規表現に一致すると `ANSWER` が `deny` でも `approve` を送ります。不一致時は `ANSWER` の内容をそのまま送ります。`ANSWER` 自体が未設定または空文字なら自動回答処理に入らず、`APPROVE_MATCH` 単独では何もしません。

正規表現として不正な値は `new RegExp` の生成時に例外になります。スクリプトにはこの生成を捕捉する処理がないため、当該フレームの処理から `stream()` が失敗します。

## 有効になる条件

- `apps/host/scripts/agent-http.mjs` を実行していること。このファイルはホストの `package.json` に専用 npm script として登録されていません（`apps/host/package.json:5-28`）。通常のアプリ起動や Strata 推論エンジンの設定には影響しません。
- `stream()` が `agent-tool` フレームを受け取り、ツール状態が `proposed` であること。`ANSWER` が空でない場合に限り `/api/chat/approval` への POST を行います。
- OS/backend/build macro/model による分岐はこの読み取り箇所にはありません。`stream` コマンドは既定で `bypass` モードですが、引数でモードを指定できます。`plan` コマンドは `manual` モードを指定します（`apps/host/scripts/agent-http.mjs:83-86,144-150`）。実際に承認待ちカードが発生するかはホストから受け取るフレーム次第です。

## 実行時の詳細

環境値は `stream()` が各フレームを処理する時点で `process.env` から参照されます。`APPROVE_MATCH` の値をモジュール起動時に固定する変数や cache はありません。各 `proposed` カードごとに `ANSWER` の有無と正規表現判定を行います。

自動回答では `sessionId: body.sessionId`、`toolId: f.tool.id` と選んだ `decision` を `/api/chat/approval` に送ります。スクリプト側の API helper は HTTP 非成功応答を例外化し、承認送信の Promise rejection handler が `answer failed: ...` を標準出力に記録します。成功時は `-> ${process.env.ANSWER} ${f.tool.id}` を出します。この成功ログは実際に送った decision ではなく `ANSWER` の値を表示するため、正規表現一致で `approve` を送った場合も表示は `ANSWER` の値です。サーバー側は `decision` が `approve` / `deny` 以外なら HTTP 400 を返します。したがって、任意の空でない `ANSWER` は送信を試みますが、API が受け付けるとは限りません。

## 根拠

- `apps/host/scripts/agent-http.mjs:34-60` — stream のフレーム処理、`proposed` 状態と `ANSWER` の gate、正規表現による decision 選択、POST および成功・失敗ログ。
- `apps/host/scripts/agent-http.mjs:18-23` — HTTP 非成功応答を例外にする API helper。
- `apps/host/scripts/agent-http.mjs:83-86,144-150` — stream コマンドと plan コマンドのモード指定。
- `apps/host/package.json:5-28` — 登録された npm script。`agent-http.mjs` の実行登録はない。
- `apps/host/server/index.mjs:1942-1948` — 承認 API が受け付ける decision と不正値・承認失効時の応答。
