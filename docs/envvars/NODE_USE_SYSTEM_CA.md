# `NODE_USE_SYSTEM_CA`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata はホストプロセスの環境からこの変数を読みません。エージェント用 DeepSeek Harness を Node.js 子プロセスとして起動するとき、Strata が子プロセス環境へ `NODE_USE_SYSTEM_CA: '1'` を設定します。したがって、候補一覧には現れますが、Strata の通常の設定入力ではなく、Harness 起動時に固定値を渡すための名前です。

この変数が設定された子プロセス内で何を行うかは外部 Node.js ランタイム側の動作なので、ここでは Strata の挙動として説明しません。Strata ホスト自身の証明書処理は `apps/host/server/system-ca.mjs` にあり、そこで確認する別の環境変数は `STRATA_NO_SYSTEM_CA` です。

## 値と判定

Strata 側に `NODE_USE_SYSTEM_CA` の値を parse・比較・検証する処理はありません。ホストから継承した同名変数の未設定・空文字・任意値も読み取らず、Harness 起動用環境へ `'1'` を設定します。Harness 起動コードでは `agentEnvironment()` の既定値より `extra` を後から展開しますが、現行の呼び出し元が渡す `profile.env` はプロファイル内 MCP 設定や検索設定から作られる `STRATA_MCP_...`、`STRATA_SEARCH_KEY` 等の環境だけで、この名前を上書きしません。

| 状況 | Strata が子プロセスへ渡す値 |
|---|---|
| ホスト側で未設定、空文字、または任意の値 | `'1'` |
| 現行 Harness 起動元が渡す追加環境 | `'1'`（対象名との衝突なし） |
| `agentEnvironment(base, extra)` を直接呼び、`extra.NODE_USE_SYSTEM_CA` を指定 | `extra` の値（最後の展開が優先）。これは helper の一般仕様で、現行の Harness 起動経路ではその指定を行わない |

## 有効になる条件

この設定は `HarnessProcess.start()` が Harness を起動する経路に限られます。エージェントコンポーネントが見つからないなどの理由で Harness を起動しない場合、子プロセス環境も作られません。実際の起動では、Strata は Harness の `bin` を `nodePath`（既定は `process.execPath`）で実行し、`--profile web` 等を渡します。

OS/backend、モデルの種類、CLI 引数、Strata の `STRATA_NO_SYSTEM_CA` は、`NODE_USE_SYSTEM_CA` を読む Strata 側の分岐条件ではありません。ホストの証明書処理はサーバー起動時に別モジュールで初期化されます。そこでは `STRATA_NO_SYSTEM_CA === '1'` の場合にシステム証明書の追加を行わず、それ以外は TLS API の有無やシステム証明書一覧などを確認します。この処理を `NODE_USE_SYSTEM_CA` が制御するとはコードから確認できません。

## 実行時の詳細

`agentEnvironment()` はホスト環境から `externalEnvironment(base)` の値を受け取り、名前を `KEEP` 正規表現で許可したものだけ残し、秘密情報らしい名前を除外します。`NODE_USE_SYSTEM_CA` は `KEEP` に含まれないため、ホストに同名変数を設定してもその値はこの経路では引き継がれません。その後、Strata は Harness 起動用の環境に `'1'` を追加します。起動時に環境を一度組み立てて `spawn()` に渡し、リクエストごとに読み直す処理や Strata 内の cache はありません。

Strata による対象名固有のログ、警告、終了・失敗処理は見つかりません。Harness の起動が所定時間内に接続先 URL を出力しない場合は一般の起動 timeout、起動中に子プロセスが終了した場合は一般の起動エラーとなり、起動後の終了は Harness 終了コード付きで記録されます。これらの経路がこの変数の値を検査するわけではありません。

## 根拠

- `apps/host/server/agent/harness-runtime.mjs:20-36`: 子プロセス環境の許可リストと `NODE_USE_SYSTEM_CA: '1'` の設定。`extra` を最後に展開。
- `apps/host/server/agent/harness-runtime.mjs:67-83`: `HarnessProcess.start()` が `agentEnvironment()` の結果を `spawn()` の `env` として渡す。Node 実行ファイルの既定値は 67 行目。
- `apps/host/server/agent/agent-bridge.mjs:205-223`: Harness の解決、`profile.env` を追加環境に渡す処理、および起動。
- `apps/host/server/agent/profile.mjs:77-100,196-200,294-298,339-348`: プロファイル追加環境の生成元。MCP の環境変数名は `STRATA_MCP_...` 形式。
- `apps/host/server/system-ca.mjs:11-24` と `apps/host/server/index.mjs:3`: ホスト側の証明書初期化と別変数 `STRATA_NO_SYSTEM_CA`。
- `apps/host/server/agent/harness-runtime.mjs:94-104`、`apps/host/server/agent/agent-bridge.mjs:214-233`: Harness 起動 timeout・起動失敗・終了時の一般処理。
- `docs/envvars/000_envvers.md:464`: この名前が候補一覧にあること。候補一覧だけでは Strata による環境からの読み取りを示さない。
