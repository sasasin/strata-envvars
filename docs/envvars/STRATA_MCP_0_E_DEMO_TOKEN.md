# `STRATA_MCP_0_E_DEMO_TOKEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前は、Strata の起動元プロセスから読み取る設定ではありません。Strata の host が MCP サーバー設定の `env` 値を agent 用プロファイルに埋め込まずに渡すため、動的に生成する agent 子プロセス用の環境変数名です。`STRATA_MCP_0_E_DEMO_TOKEN` は、MCP サーバーの並びで最初に採用されたサーバーの `DEMO_TOKEN` 環境値に対応する形です。

Strata は環境変数名を参照する `!!js process.env.STRATA_MCP_0_E_DEMO_TOKEN` を生成プロファイルへ書き、値そのものは別の `env` オブジェクトに入れて Harness 子プロセスへ渡します。したがって、同名の値を Strata host の親環境に設定しても、この経路の値にはなりません。値の参照を解決して MCP 起動設定へ適用する Harness 側の内部動作は本調査の対象外です。

## 値と判定

Strata はこの名前の値を `getenv` や `process.env[...]` で読みません。MCP 設定中の文字列値を `String(value)` で変数名に対応づけ、プロファイルと子プロセス環境に分けて設定します。MCP 設定の `env` 値は文字列である必要があり、最大 16,000 文字、NUL 文字不可です。空文字は許可され、空文字のまま環境値に格納されます。

| 状況 | Strata の処理 |
|---|---|
| 親プロセスでこの名前が未設定または設定済み | 参照されず、MCP 設定側の値を使う |
| 最初に採用された MCP サーバーの `env.DEMO_TOKEN` が空文字 | 空文字を `env.STRATA_MCP_0_E_DEMO_TOKEN` に格納し、プロファイルには名前だけを書く |
| MCP サーバーの `env.DEMO_TOKEN` が通常の文字列 | その文字列を子プロセス環境用オブジェクトに格納し、プロファイルには名前だけを書く |
| `env.DEMO_TOKEN` がない | 対応する変数もプロファイル参照も作らない |
| サーバーが無効、または不正名・アドレスなし・重複で採用されない | 行が生成されず、後続サーバーの index は採用順に詰められる |

`0`/`1`、数値、真偽値としての判定や範囲 clamp はありません。設定保存時に型・長さ・NUL を検証し、マスク文字列は既存値がある場合に限ってその値へ戻します。無効な MCP 設定は保存処理でエラーになります。

## 有効になる条件

- Agent 用 Harness の実行プロファイルを構築すること。通常の Strata 推論エンジンや MCP 以外の処理がこの名前を読むわけではありません。
- 有効な MCP サーバー設定に `env` があり、その中に `DEMO_TOKEN` のようなキーがあること。ローカルコマンド型では `E`（environment）の名前を生成します。HTTP 型のヘッダーは `H` になり、この対象名にはなりません。
- `0` は、無効サーバーを除き、名前・接続先などの検査を通過して採用されたサーバーの順番です。設定の順序、無効化、他サーバーの追加・削除で index は変わり得ます。
- default local model の `mcpServers` と Tools 設定の `servers` をマージした設定から行を作ります。Tools 側に同名がある場合はそちらが優先されます。Agent を使うモデル経路と Harness が利用可能であることも必要です。

不足している名前や接続先、不正名、重複名の MCP サーバーは省略され、profile の `mcpSkipped` として状態に載ります。Agent コンポーネントが見つからない場合は agent が unavailable となり、runtime 起動へ進みません。

## 実行時の詳細

`buildProfile()` は MCP 設定を `mcpRows()` に渡し、生成された MCP 環境値を profile の `env` に合流します。各値はプロファイル YAML ではなく、`HarnessProcess` 起動時の `extraEnv` として `agentEnvironment()` に渡され、起動する Harness の `spawn()` 環境へ含められます。Strata は生成プロファイルを `profile-<signature>.patch.yml` に書きますが、そこには資格情報の値でなく環境変数名が入ります。

この名前の値は環境から読み戻さず、別個の static cache もありません。設定から profile を作るたび値を構成します。稼働中 Harness の tool/profile signature が変われば、Strata は既存 agent が idle になるのを待って停止し、新しい profile で起動します。同じ signature と route の agent が動いていれば既存 runtime を再利用します。

対象名固有のログや終了コードはありません。MCP 設定検証エラー、agent コンポーネント不在、Harness の起動失敗はそれぞれ上位のエラー経路に現れます。プロファイル生成処理のコメントとテストは、secret 値を profile ファイルに含めない設計を示しています。

## 根拠

- `apps/host/server/agent/profile.mjs:72-100`: MCP サーバーを順に処理し、`STRATA_MCP_<index>_<E|H>_<KEY>` 形式の名前を作成。値を `env` に置き、プロファイル側は `process.env.<name>` 参照にする。無効・不正名・接続先なし・重複の扱い。
- `apps/host/server/agent/profile.mjs:121,290-297`: key の slug 化、default local model と Tools 設定のマージ、および MCP 値を profile 環境へ合流する処理。
- `apps/host/server/native-settings.mjs:118-133`: MCP 設定の保存検証。サーバー数、env object、文字列値、16,000 文字上限、NUL 拒否、空文字の許容と secret mask の復元。
- `apps/host/server/agent/profile.mjs:338-348`: 値を含まない profile patch の生成、値も含めた signature、戻り値の `env`。
- `apps/host/server/agent/agent-bridge.mjs:175-178,205-215,243-267`: profile の再生成、patch ファイル書き込み、Harness への profile/env 引き渡し、signature 不一致時の停止・再起動。
- `apps/host/server/agent/harness-runtime.mjs:20-36,67-83`: 親環境のフィルタと `extra` の合成、および Harness 子プロセス起動時の `env` 設定。
- `apps/host/tests/agent-tools.test.mjs:226-252`: MCP 環境 secret を設定したケースで、生成された agent profile ファイルに環境変数名があり、secret 値が含まれないことを確認するテスト。テストは実装の補助根拠として参照。
- 候補一覧 `docs/envvars/000_envvers.md:1021` はこの名前を掲載しています。Strata 内の完全一致参照はこのテストの assertion のみで、製品コードは名前を動的生成します。
