# `STRATA_MCP_TIMEOUT_MS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストアプリがエージェント用プロファイルを作る際、適用対象となる外部 MCP サーバーのクライアント設定に、ツール呼び出し timeout をミリ秒で追加する fallback 値です。Strata 自身が MCP 呼び出しをタイマーで打ち切る実装ではなく、値を `@deepseek-ai/dsh-mcp-client` の設定 `toolCallTimeoutMs` としてプロファイルに渡します。対象は `mcpRows` が作るモデル設定または Settings の MCP サーバー行です（`app/host/server/agent/profile.mjs:82-116, 424-432`）。

## 値と判定

値は `process.env.STRATA_MCP_TIMEOUT_MS` を各 MCP サーバー行の生成時に読み、JavaScript の真偽値判定と `Number(...) > 0` で採否を決め、`Math.round` で整数ミリ秒にします。文字列全体の厳密な数値検証はしません（`app/host/server/agent/profile.mjs:98-107`）。

| 条件 | 判定・結果 |
|---|---|
| 未設定または空文字 | 値なしとして扱い、他の timeout も無ければ `toolCallTimeoutMs` をプロファイルに含めない。 |
| 正の数値文字列 | 採用し、ミリ秒単位に `Math.round` して設定する。例: `1500` → `1500`、`1.5` → `2`。 |
| 正の数値だが 0.5 未満 | 数値条件は通るが丸めて `0` となり、truthy 判定で設定項目が省かれる。 |
| `0`、負数、非数値、`NaN` 相当 | `Number(...) > 0` が偽になり、この環境変数は fallback として使われない。 |
| 空白、指数表記、16 進表記など | `Number` が正数へ変換できれば採用される（例: `" 2 "` → `2`、`"1e3"` → `1000`、`"0x10"` → `16`）。先頭・末尾の空白除去や形式制限は独自に行わない。 |
| `Infinity` 相当 | `Number(...) > 0` を通り `Math.round` 後も `Infinity`。プロファイル JSON のシリアライズでは JSON の数値 `null` になる。有限値上限のチェックはない。 |

この変数が選ばれるのは、サーバー固有の `timeoutSec` / `timeout_s` / `timeout` が正の値でなく、かつ `toolCallTimeoutMs` も正の値でない場合だけです。優先される秒指定は最初に null/undefined でないフィールド一つを選ぶため、その値が無効でも後続の秒フィールドは見ず、次に `toolCallTimeoutMs`、最後に本環境変数へ進みます（同 `profile.mjs:98-107`）。

## 有効になる条件

- `buildProfile` が呼ばれ、サーバーが `mcpRows` に渡されること。対象サーバーは無効化されておらず、有効な名前と `command` または `url` を持つ必要があります。満たさない行は除外されます（`app/host/server/agent/profile.mjs:82-92`）。
- 対象行に明示的な正の `timeoutSec` / `timeout_s` / `timeout` または `toolCallTimeoutMs` がないこと。これらがあれば環境変数より優先します（同 `profile.mjs:98-107`）。
- 既定ローカルモデルの MCP 設定にある `mcp_timeout_s` が正数の場合、モデル側サーバーに明示的 timeout がない限り先に秒指定 `timeout_s` として補われ、環境変数より優先します（同 `profile.mjs:420-431`）。モデル設定の `mcp_timeout_s` はホストの設定項目として 1〜3600 秒の範囲で定義されています（`app/host/server/native-settings.mjs:28`）。
- Settings → Tools で登録した MCP サーバーは `timeoutSec` を付けてプロファイルへ渡します（`app/host/server/agent/tools-settings.mjs:149-159`）。この項目の既定値は 120 秒で、1〜3600 秒に clamp されるため、通常その設定値が環境変数より優先します（`app/host/server/agent/tools-settings.mjs:60, 85-88`; `app/host/server/agent/custom-command-run.mjs:18-19, 65-68`）。
- `mcpRows` で作られない Strata 内蔵の instructions / command / browser / admin 行にはこの環境変数を適用しません（`app/host/server/agent/profile.mjs:431-440, 470`）。また、Strata の `/v1/chat/completions` API クライアントやエンジン CLI の timeout を設定するものではありません。

## 実行時の詳細

環境変数は `mcpRows` のループ内で各サーバー行をプロファイル化するたびに読みます。静的キャッシュはありません。プロファイルは状態照会時とエージェント実行前に構築されます（`app/host/server/agent/agent-bridge.mjs:250-263, 279, 333-340`）。生成した MCP 行はプロファイルの `insert` に入り、ホストは生成済みパッチをファイルに書いて Harness 子プロセスを起動し、プロファイルの環境も渡します（`app/host/server/agent/profile.mjs:470-493`; `app/host/server/agent/agent-bridge.mjs:294-305`）。

設定変更で `toolCallTimeoutMs` が変わると MCP 行を含む `toolsSignature` が変化し、次に実行環境を照合する際に既存 Harness の再起動経路へ入ります（`app/host/server/agent/profile.mjs:484-493`; `app/host/server/agent/agent-bridge.mjs:339-355`）。OS の親プロセス環境を実行中に外から変更しても、既に起動したホストの `process.env` は更新されません。ホスト内で値が変化した場合は次回のプロファイル生成で再読込されます。

## ログと測定値

この環境変数自体に関する Strata 側の専用ログ、警告、timeout 判定、終了処理は確認できませんでした。Strata のコードで確認できる結果は、条件を満たした MCP 行に `toolCallTimeoutMs` を設定してプロファイルへ渡すことまでです。timeout 時の MCP クライアント側の挙動は Strata 所有コードの調査範囲外です。

## 根拠

- `app/host/server/agent/profile.mjs:82-116` — サーバー行の除外条件、timeout の変換・優先順位、`toolCallTimeoutMs` の設定。
- `app/host/server/agent/profile.mjs:420-432` — 既定ローカルモデルのサーバー選択、`mcp_timeout_s` fallback と Settings サーバー行との合成。
- `app/host/server/agent/profile.mjs:470-493` — MCP 行のプロファイル挿入、署名生成。
- `app/host/server/agent/agent-bridge.mjs:250-263, 279, 294-305, 333-355` — プロファイルの生成時期、子プロセスへの適用、設定変更時の再起動。
- `app/host/server/native-settings.mjs:28`, `app/host/server/agent/tools-settings.mjs:60, 85-88, 149-159`, `app/host/server/agent/custom-command-run.mjs:18-19, 65-68` — モデル timeout 設定項目と Settings サーバー timeout の既定・範囲。
