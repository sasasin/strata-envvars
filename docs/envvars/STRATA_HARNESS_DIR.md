# `STRATA_HARNESS_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部 Harness の内部動作は対象外。

## 役割

Strata の desktop host が agent 用の外部 DeepSeek Harness の場所を指定するための環境変数です。設定されている場合はインストール同梱先やユーザー component フォルダーより先に候補として調べます。Harness をダウンロード・インストールする変数ではありません。主な利用経路は agent bridge で、Harness が見つからないと agent capability が unavailable になり、起動要求も `component-missing` で失敗します。通常の engine 起動やモデル設定を直接変更するものではありません。

## 値と判定

`resolveHarness()` は `env.STRATA_HARNESS_DIR` を文字列として受け取り、他の候補とともに `filter(Boolean)` で絞り込みます。数値や真偽値への変換はありません。

| 値 | Strata の扱い |
|---|---|
| 未設定または空文字 | 明示候補にせず、同梱 Harness、次いで `<componentsDir>/harness` を探す |
| 空でないパス | 最優先候補。`resolve()` で絶対パス化して検査する。相対パスは Node プロセスの現在の作業ディレクトリー基準 |
| 存在しない場所、または想定 CLI ファイルがない | 次の候補へ進む |
| CLI ファイルはあるが `node_modules` がない | そこで `{ok:false}` を返す。後続候補へは進まない |
| 使用可能な候補 | `{ok:true, dir, bin, version}` を返す。version ファイルの読み取り・JSON parse に失敗した場合も利用可で、version は `null` |

source checkout 形式では `<dir>/apps/cli/lib/bin.js` を先に探し、なければインストール形式の `<dir>/lib/bin.js` を探します。値の大文字小文字や数値範囲の判定はありません。空白だけの値も空文字ではないためパス候補になります。

## 有効になる条件

- Strata host の agent bridge が Harness を探すときに参照します。desktop host は `componentsDir` と、host の隣に同梱された `bundledDir` も候補として渡します（`apps/host/server/index.mjs:193-207`）。
- 有効候補になるには、CLI ファイルと `node_modules` が必要です。OS 専用の分岐や build macro による値の解釈差は、この読み取り箇所にはありません。
- agent の実行にはモデル route も必要です。route がない場合は Harness の解決後に `model-unavailable` となり、変数だけでは agent を起動しません（`apps/host/server/agent/agent-bridge.mjs:243-253`）。
- Harness が見つからない場合、status は unavailable と理由を返し、起動時は同じ missing-component 条件で拒否します（`apps/host/server/agent/agent-bridge.mjs:187-190,205-207`）。

## 実行時の詳細

本番 host では `createAgentBridge()` の `env` 引数は省略され、既定の `process.env` が使われます（`apps/host/server/agent/agent-bridge.mjs:120`、`apps/host/server/index.mjs:193-219`）。`harnessInfo()` は `resolveHarness()` を呼ぶ関数で、結果を cache しません。status 要求（`GET /api/agent/status`）時と Harness 起動時に解決を行います（`apps/host/server/agent/agent-bridge.mjs:182,187-189,205-207`、`apps/host/server/index.mjs:1888-1889`）。

起動時には選ばれた `dir/bin` を `HarnessProcess` に渡し、Node で `bin --profile web --patch … --port 0 --no-open` を起動します（`apps/host/server/agent/agent-bridge.mjs:211-223`、`apps/host/server/agent/harness-runtime.mjs:75-83`）。環境変数の値そのものを CLI 引数に追加する処理はありません。子プロセス向け環境は `agentEnvironment()` が親環境から作る許可リスト方式で、`STRATA_HARNESS_DIR` は `KEEP` に含まれないため、親環境からは引き継がれません（`apps/host/server/agent/harness-runtime.mjs:20-36,80-83`）。

プロセス内 cache はありませんが、既に動いている Harness の実行ファイルは環境値を変えただけでは自動で再起動しません。bridge の runtime 再利用判定は tools signature と選択 route に基づき、Harness の directory を比較しません（`apps/host/server/agent/agent-bridge.mjs:243-267`）。新規起動時に候補が使えない場合は `component-missing`、子プロセス起動後に失敗した場合は agent-start-failed 系のエラーになります。Harness 起動時に stdout に loopback address が出なければ既定 120 秒後に timeout、または起動中の終了としてエラーになります（`apps/host/server/agent/harness-runtime.mjs:75-107`）。起動失敗の詳細は agent status の `detail` に保持されます（`apps/host/server/agent/agent-bridge.mjs:191-195,262-265`）。

Strata 同梱の `apps/host/scripts/context-e2e.mjs` も `process.env.STRATA_HARNESS_DIR` を直接 truthy 判定し、未設定または空文字なら `STRATA_HARNESS_DIR is not set` を stderr に出して exit code 2 で終了します（`apps/host/scripts/context-e2e.mjs:47`）。設定値自体をこのチェックでパス検査するわけではありません。その後の agent bridge で Harness を解決します。これは E2E 診断スクリプトの条件であり、本番 host の既定値・優先順位とは別です。

## 根拠

- `apps/host/server/agent/harness-runtime.mjs:39-57` — 候補の順序、空値の除外、パス解決、実行ファイル・依存関係の確認、返却理由。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — 子プロセス環境の絞り込みと Harness 起動引数。
- `apps/host/server/agent/agent-bridge.mjs:120,182-207,211-232,243-267` — env の既定値、解決タイミング、status、起動、runtime 再利用と失敗処理。
- `apps/host/server/index.mjs:193-219,1888-1889` — desktop host が渡す候補ディレクトリーと status endpoint。
- `apps/host/scripts/context-e2e.mjs:47` — 同梱診断スクリプトの未設定チェックと終了経路。

`000_envvers.md` の候補名は本番 host の実読み取りと E2E スクリプトの直接参照で裏付けられます。`apps/host/tests/**` にもテスト用読み取りがありますが、上記の本番挙動の根拠にはしていません。
