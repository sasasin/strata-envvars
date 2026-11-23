# `DSH_PERMISSION_MODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の agent host は、外部コンポーネントである DeepSeek Harness を起動するとき、その子プロセスの環境に `DSH_PERMISSION_MODE=read-only` を設定する。これはホスト環境の同名変数を読んで設定を選ぶ処理ではなく、Strata が固定値を子プロセスへ渡す処理である。ソースコメントは、チャットがモードを設定していない session（child agent や seeded session）の composition default と説明しているが、Harness は調査対象外の別コンポーネントなので、この値を同コンポーネントがどう解釈するかまではここでは断定しない（`app/host/server/agent/harness-runtime.mjs:25-36,80-83`）。

## 値と判定

Strata は環境値を parse せず、agent 環境オブジェクトに固定文字列を代入する。親プロセス側で未設定、空文字、`read-only`、`0`、`true`、その他の文字列のいずれでも、この代入自体の結果は `read-only`。親環境からは同名キーが通常コピーされない。`agentEnvironment` の `extra` に同名キーが明示的に渡されれば末尾の spread が固定値を上書きするが、実運用の `HarnessProcess` 呼び出し元が渡す `extra` は profile が作った環境と pause marker であり、profile の環境キーは `STRATA_...` 名として構成される（`harness-runtime.mjs:20-36,80-83`; `agent-bridge.mjs:303-305`; `profile.mjs:82-96,442-448`）。

| Strata が受け取る親環境 | Strata の子環境に設定する値 | 判定 |
|---|---|---|
| 未設定、空文字、または任意の設定値 | `read-only` | 親の値を判定せず固定値を設定 |
| `agentEnvironment` の `extra` に同名キーを指定 | その `extra` の値 | `...extra` が固定値より後に適用される。通常の agent bridge 起動経路ではこの上書き値を渡さない |

## 有効になる条件

- Harness 子プロセスの起動時に `agentEnvironment` が使われること。`HarnessProcess.start()` は `spawn()` の `env` に同関数の戻り値を渡す（`harness-runtime.mjs:75-83`）。
- この環境設定は agent bridge が Harness を起動する経路に適用される。Harness が見つからない場合は起動前に `AgentUnavailable` となり、子プロセスは起動しない（`agent-bridge.mjs:294-304`）。
- 親環境の同名値が何であっても選択条件にはならない。通常のチャットでは、Strata は各 turn のモードを別途決め、session の permission preset を RPC で確認・適用する（`agent-bridge.mjs:424-435,601-605`）。
- OS、GPU backend、build macro、モデル状態によるこの代入の分岐はない（`harness-runtime.mjs:25-36`）。

## 実行時の詳細

`agentEnvironment(base, extra)` は `externalEnvironment(base)` から通常ユーザー環境の許可リストにある値を選び、secret 名を除外した後、`DSH_PERMISSION_MODE: 'read-only'` を含む既定キーを追加し、最後に `extra` を展開する。許可リストは `DSH_PERMISSION_MODE` を含まないため、親環境に同名キーがあってもコピーされない。Strata はその親値を読み取ったり検証したりせず、起動ごとに子環境を組み立てて `spawn()` に渡す。関数内 cache はなく、起動後に親プロセスの環境を変更しても、すでに起動した子プロセスの環境は更新されない（`harness-runtime.mjs:20-36,75-83`）。

実運用では `agent-bridge.mjs` が `HarnessProcess` に `profile.env` と `STRATA_UPDATE_PAUSE_FILE` を渡し、`start()` がさらに `DSH_HOME` を追加する。同 bridge は通常の各 turn で保存モード（または plan task の `plan`）を選び、session の permissions projection を照会し、不一致なら `/permission <preset-key>` を実行して再照会する。したがって通常のチャットモードはこの環境変数の親側の値による選択ではなく、turn ごとの session RPC で扱われる。モード変更はその turn の適用時に読み込まれ、実行中 turn には反映せず次の turn に適用する（`agent-bridge.mjs:303-305,424-435,601-605`; `profile.mjs:39-54`）。

Strata のソースから確認できるのは子プロセス環境へのキーと値の設定までであり、Harness 自身が `DSH_PERMISSION_MODE` を読む位置や、Harness 内で session・child agent に及ぼす最終的な効果は確認対象外である。環境変数の設定自体に専用ログはない。通常の turn で permission の適用・確認に失敗すると、Strata は turn を開始せず、通信不能時は `agent · session …: the agent did not answer while the chat's mode was set (...); nothing ran` を host log に記録し、チャットには `The assistant could not start. Try again in a moment.` を返す。その他のモード設定失敗では `Strata could not set this chat to <mode> mode, so nothing ran. Try again.`、Manual の gate 確認失敗では `Strata could not make sure the coding assistant asks before changing anything, so nothing ran. Close and reopen Strata, then try again.` を返す（`agent-bridge.mjs:437-455`）。これらは session RPC の失敗経路であり、`DSH_PERMISSION_MODE` の値判定ログではない。

## 根拠

- `app/host/server/agent/harness-runtime.mjs:20-36` — 親環境の許可リストと secret 除外、固定値の設定、`extra` による上書き順。
- `app/host/server/agent/harness-runtime.mjs:75-83` — 起動時に組み立てた環境を Harness 子プロセスへ渡す。
- `app/host/server/agent/agent-bridge.mjs:294-305` — 実運用で渡す追加環境。
- `app/host/server/agent/agent-bridge.mjs:424-455,601-605` — turn ごとの permission preset 確認・設定と失敗経路。
- `app/host/server/agent/profile.mjs:39-54,82-96,442-448` — preset と profile が生成する環境キー。
