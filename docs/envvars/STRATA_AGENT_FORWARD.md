# `STRATA_AGENT_FORWARD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の agent bridge が、対象モデルへのリクエストをホスト内の LLM forwarding endpoint 経由にするかを選びます。既定（この変数が文字列 `0` でない場合）は、転送可能なモデルルートを常に転送します。endpoint はレスポンス中の、サーバーが実行できなかった tool call を示す marker を読み取れるため、bridge は同じ turn 内でモデルに修正を促せます。`STRATA_AGENT_FORWARD=0` は旧来の選択に戻し、Response 設定に差がある場合だけ転送します。変数自体はモデルや tool の選択・実行を行わず、agent の有効・無効も切り替えません。読み取りと route 選択は `app/host/server/agent/agent-bridge.mjs` の `createAgentBridge` と `agentProvider` が担います（`app/host/server/agent/agent-bridge.mjs:41-48,267-268,584-598`）。

## 値と判定

`createAgentBridge` の `env`（省略時は `process.env`）から値を読み、ブリッジ生成時に `env.STRATA_AGENT_FORWARD !== '0'` を一度評価します。文字列全体を `'0'` と比較し、数値変換、trim、大文字小文字変換はしません。未設定（`undefined`）、空文字、`'1'`、`'false'`、`'00'`、`'0anything'` などはすべて常時転送側です。文字列 `'0'` だけが旧来の条件付き転送側です。実行中に環境オブジェクトの値を変えても、この bridge instance の判定は変わりません（`app/host/server/agent/agent-bridge.mjs:160,267`）。

| 条件 | unset | 常時転送になる値 | 条件付き転送になる値 |
|---|---|---|---|
| agent bridge の全ルート | `'undefined'` 相当。`!== '0'` のため常時転送 | `'0'` 以外すべて（空文字を含む） | 文字列 `'0'` のみ |

## 有効になる条件

- agent bridge が生成されており、該当 turn が `session/selectModel` で provider を選ぶこと（`app/host/server/agent/agent-bridge.mjs:160,584-598`）。
- 対象 route に `shaped` provider があること。ローカルモデルは `proxyBase` があると shaped route が作られます。保存済み接続は OpenAI Completions 形式で、reasoning format が `openrouter` でなく、URL が localhost または private network address と判定された場合に限り shaped route になります。app の通常起動では `index.mjs` が `proxyBase` を渡します（`app/host/server/agent/profile.mjs:323-335,338-370,373-417`; `app/host/server/index.mjs:214-221`）。
- cloud route、shaped route のない API protocol / connection にはこの変数の転送効果はありません。`agentProvider` は `route.shaped` がないとき元の `route.route` を使います（`app/host/server/agent/agent-bridge.mjs:46-48`; shaped route の条件は `app/host/server/agent/profile.mjs:373-417`）。
- 値が `'0'` でも、thinking budget が 0 より大きいか、Expert sampling の差分がある turn は shaped provider を選びます。budget は thinking が Off なら 0、それ以外は `nearestBudget` により候補値へ丸められます。sampling は shaped route と `proxyBase` がある場合に取得されます（`app/host/server/agent/agent-bridge.mjs:580-588`; `app/host/server/agent/llm-shape.mjs:18-26,37-48`）。

## 実行時の詳細

ブリッジ生成時に環境値を読み、各 turn で `forwardAlways` とその turn の budget / sampling を `agentProvider` に渡します。常時転送側では shaped route があれば budget 対応 provider（なければ元 route）を選びます。`'0'` の場合は budget または sampling があるときだけ同じ shaped route を使い、いずれもなければ元 route に直接接続します。選んだ provider は `session/selectModel` に渡され、route が変われば再選択されます（`app/host/server/agent/agent-bridge.mjs:267,584-598`; route 作成は `app/host/server/agent/profile.mjs:325-335`）。

forwarding endpoint はローカル接続であることを検査し、route key から転送先を解決します。該当する JSON request では必要な Response 設定を加え、応答は marker 読み取り処理を通したうえで caller に流します。`STRATA_AGENT_FORWARD` が直接変更するのはこの endpoint を通る route の選択です（`app/host/server/agent/llm-shape.mjs:63-105,193-240`）。常時転送側では Response 設定が既定でも endpoint が marker を観測できます。marker が turn に一致すると、bridge は完了扱いを保留して修正 prompt を同じ session に送り、推測で tool を実行しません。修正回数上限では turn を終了します（`app/host/server/agent/agent-bridge.mjs:1200-1224`; `app/host/server/agent/tool-fix.mjs:1-53,65-99`）。

## ログと測定値

この環境変数の読み取り自体はログを出しません。条件付き転送側で marker を観測できないため、既定設定で転送される route と比べて tool-call correction は働きません。marker が見つかった場合は `agent · <chatId>: tool call could not run (...)`、修正開始時は `agent · <chatId>: tool call could not run (...); correction <n> of <limit>`、上限到達時は `agent · <chatId>: tool call could not run (...); recovery limit reached, ending the turn` を記録します。複数 turn に marker が曖昧に一致した場合のログもあります（`app/host/server/agent/agent-bridge.mjs:1205-1219`）。

転送 endpoint の観測可能な失敗は、非 loopback 接続の `403`（`This endpoint is for the assistant on this computer only.`）、未知 route の `404`（`Unknown model route.`）、上流接続失敗の `502`（`The model server could not be reached: ...`）です。provider 選択が `session/selectModel` で失敗すると bridge は `AgentUnavailable`（`The coding assistant could not use <route>. Pick the model again and retry.`）を返します（`app/host/server/agent/llm-shape.mjs:196-201,237-240`; `app/host/server/agent/agent-bridge.mjs:590-597`）。この変数に関する Strata の測定値は確認できません。

## 根拠

- `app/host/server/agent/agent-bridge.mjs:41-48,160,267-268,580-598,1200-1224`
- `app/host/server/agent/profile.mjs:323-335,338-370,373-417`
- `app/host/server/agent/llm-shape.mjs:18-26,37-48,63-105,122-135,193-240`
- `app/host/server/agent/tool-fix.mjs:1-53,65-99`
- `app/host/server/index.mjs:214-221`
