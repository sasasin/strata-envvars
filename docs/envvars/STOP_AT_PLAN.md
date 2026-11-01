# `STOP_AT_PLAN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/agent-http.mjs` の `plan` コマンドで、生成した計画を goal として開始する前に実行する API action を指定します。Strata のサーバー設定や C++ engine の環境変数ではなく、HTTP 操作用の同梱スクリプトだけが読みます。計画が生成されない場合は、この変数を評価する前にスクリプトが終了します（`apps/host/scripts/agent-http.mjs:144-153`）。

## 値と判定

文字列の parse や値域検証はせず、JavaScript の truthiness で分岐します。未設定と空文字は false、それ以外の文字列は true です。たとえば `0`、`false`、`true` はすべて空でない文字列なので true になります。

| 値 | 動作 |
|---|---|
| 未設定、空文字 | 分岐を通らず、計画を `/api/plan/start-goal` に送って goal として開始する |
| `approve` | `/api/plan/approve` を呼び、計画を承認してスクリプトを正常終了する。goal は開始しない |
| `reject` | `/api/plan/reject` を呼び、計画を却下してスクリプトを正常終了する。goal は開始しない |
| `edit` | `/api/plan/edit` を呼ぶが、この呼び出しには `steps` が含まれないため、サーバーは `A plan needs a list of steps.` で失敗する |
| その他の非空文字列 | その文字列を URL path に使う。サーバーが認識する action は `approve`、`edit`、`reject` だけなので、それ以外は該当 route に一致しない |

HTTP エラーは helper `j()` が status と応答内容を含む `Error` にして throw します。たとえば未知 action はサーバーの route に一致せず、`edit` は入力検証エラーになります。これらは `process.exit(0)` の正常終了経路には到達しません（`apps/host/scripts/agent-http.mjs:18-23,156`; `apps/host/server/index.mjs:1902-1909`; `apps/host/server/agent/plan.mjs:164-172`）。

## 有効になる条件

- `agent-http.mjs` を `plan` コマンドで起動し、`/plan <task>` に対する応答から `plan` frame が得られる必要があります。frame がない場合は `NO PLAN FRAME (the reply stays plain text)` を出して終了コード 1 となり、`STOP_AT_PLAN` は参照されません（`apps/host/scripts/agent-http.mjs:144-153`）。
- `STOP_AT_PLAN` 分岐より前に、`EDIT_LAST` が truthy なら `/api/plan/edit` で計画を編集します。したがって両方を設定した場合、まず `EDIT_LAST` の編集が行われ、その後 `STOP_AT_PLAN` が action を選びます（`apps/host/scripts/agent-http.mjs:154-156`）。
- action API は `approve`、`edit`、`reject` のみを受け付けます。`approve` と `reject` は open な計画に適用され、計画がすでに open でない場合はエラーになります（`apps/host/server/index.mjs:1902-1909`; `apps/host/server/agent/agent-bridge.mjs:1046-1070`）。
- OS、GPU backend、build macro による条件分岐はありません。この値を読むのは Node.js スクリプトです。

## 実行時の詳細

値はスクリプト内の `plan` コマンド分岐に入った後、計画 frame を受け取り、状態照会と任意の `EDIT_LAST` 編集を終えた時点で `process.env.STOP_AT_PLAN` から直接読み取られます。static cache や共通 env helper はありません。値が truthy ならその値を `/api/plan/` の後ろに連結し、`sessionId` と `planId` を body に含めて POST します。API 応答の `plan.state` をログに出し、`process.exit(0)` します。truthy 分岐を通らない場合だけ `start-goal` の stream に進みます（`apps/host/scripts/agent-http.mjs:144-160`）。

`approve` は計画を `approved` にし、`reject` は `rejected` にします。どちらもこのスクリプトでは状態表示の後に終了するため、その後の goal 実行は行いません。action route はサーバー側で完全一致の正規表現により制限されています（`apps/host/server/index.mjs:1902-1909`; `apps/host/server/agent/agent-bridge.mjs:1046-1068`）。

## 根拠

- `apps/host/scripts/agent-http.mjs:18-23` — HTTP helper のエラー処理。
- `apps/host/scripts/agent-http.mjs:144-160` — plan command、計画 frame の確認、環境変数の読み取り、action の POST、正常終了と goal 開始経路。
- `apps/host/server/index.mjs:1902-1909` — 計画 action API が認識する path とエラー応答。
- `apps/host/server/agent/agent-bridge.mjs:1046-1070` — approve/edit/reject の状態変更。
- `apps/host/server/agent/plan.mjs:164-172` — edit に steps がない場合の入力エラー。

`000_envvers.md` には候補名として掲載されていますが、参照はこの HTTP 操作用スクリプトに限られます。Strata の他のコードがこの変数を読む・転送する箇所は確認できませんでした。
