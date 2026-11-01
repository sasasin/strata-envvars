# `STRATA_TASK_REMOTE_MODEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの調査開始時の状態は `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数は対象外です。

## 役割

Strata Host のスケジュールタスクを Harness エージェントとして実行するとき、ロード済みの既定ローカルモデルがない場合に、保存済み API 接続とモデルを選びます。選択値はタスクの agent turn に渡され、agent profile 内に同じ接続 ID とモデル ID の API route があればその route で実行されます。通常のチャットが選択するモデルを変える設定ではありません。

## 値と判定

Host は `process.env.STRATA_TASK_REMOTE_MODEL ?? ''` を文字列化して `:` で分割します。最初の要素を `connectionId`、残りの要素を再結合した文字列を `modelId` とし、両方が truthy のときだけ remote model の選択オブジェクトを返します。全体を trim したり、ID の書式を検査したりはしません。

| 値 | 選択結果 |
|---|---|
| 未設定または空文字 | `null`。remote model を選ばない |
| `connection:model` | `connectionId=connection`, `modelId=model` |
| `connection:model:variant` | `connectionId=connection`, `modelId=model:variant`。最初の `:` 以後をモデル ID に戻す |
| `:model`, `connection:`, `:` | `null`。少なくとも片方が空になる |
| ` connection : model ` | 空白を含む ID として渡す。trim や追加検証はない |

形式上の選択ができても、現在の agent profile にその ID の保存済み API route がなければ解決されません。無効な形式の値を数値化したり別値へ fallback したりする処理はありません。根拠: `apps/host/server/index.mjs:914-922`、`apps/host/server/agent/profile.mjs:351-356`。

## 有効になる条件

- `createAgentTaskRunner` は、タスク実行時に `choice()` を呼びます。既定ローカルモデルが `native.resolveInstance(native.state().defaultId)` で解決できれば、その instance を返して remote 環境変数は参照されません。ローカル既定モデルが解決できないときだけ環境変数が選択候補になります（`apps/host/server/index.mjs:914-922`）。
- タスクの run 関数は agent の状態が `unavailable` でない場合に agent runner を使います。状態が `unavailable` なら環境変数を使わず通常の `runTurn` へ進みます（`apps/host/server/index.mjs:923-939`）。Agent runner に選択された ID は、現在の profile の API route と connection/model ID の両方が一致する必要があります（`apps/host/server/agent/agent-bridge.mjs:244-253`; `apps/host/server/agent/profile.mjs:351-356`）。
- コード上に OS、GPU backend、build macro、CLI 引数による分岐はありません。機能は `apps/host/server/index.mjs` の Node.js Host に属します。スケジュール済みタスクは 15 秒間隔の timer から確認されます（`apps/host/server/index.mjs:941-942`）。

## 実行時の詳細

値は Host 初期化時に変数へ保存されず、`choice()` が呼ばれるタスク実行ごとに `process.env` から読み直されます。したがって Host プロセス内で環境値が変われば次のタスク実行に反映されます。実行中のタスクが使う選択は、その実行の最初に取得した値です（`apps/host/server/index.mjs:914-922`; `apps/host/server/agent/task-run.mjs:14-18`）。

`choice()` が `null` を返すと agent runner は `null` を返し、呼び出し側は `runTurn` に進みます（`apps/host/server/agent/task-run.mjs:14-18`; `apps/host/server/index.mjs:927-938`）。反対に、形式の整った値が profile の route と一致しない場合、bridge は `This API model is no longer available. Choose another model in the chat picker.` を `model-unavailable` として投げます（`apps/host/server/agent/agent-bridge.mjs:244-253`）。task runner は error frame を記録して例外にし（`apps/host/server/agent/task-run.mjs:24-40`）、タスクサービスが実行を `error` 状態にして例外メッセージを保存します（`apps/host/server/tasks.mjs:61-71`）。タスク状態通知には `status` と `error` が含まれます（`apps/host/server/index.mjs:923-927`）。この環境変数専用のログ出力や Host プロセス終了処理は見つかりませんでした。

実際に remote route が見つかれば `ensureRuntime` がその route を含む agent runtime を用意し、タスクの prompt を agent turn に渡します（`apps/host/server/agent/agent-bridge.mjs:244-268,382-384`; `apps/host/server/agent/task-run.mjs:24-27`）。

## 根拠

- 環境変数の唯一のコード参照とローカル優先、値の分解: `apps/host/server/index.mjs:914-922`。
- runner が各実行で choice を取得し、null の場合に fallback する契約: `apps/host/server/agent/task-run.mjs:11-18`; `apps/host/server/index.mjs:927-939`。
- route の一致条件と不一致時の失敗: `apps/host/server/agent/profile.mjs:351-356`; `apps/host/server/agent/agent-bridge.mjs:244-253`。
- タスク結果の error 保存と通知: `apps/host/server/tasks.mjs:61-71`; `apps/host/server/index.mjs:923-927`。
