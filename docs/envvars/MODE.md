# `MODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの状態は `## main...origin/main`。

## 役割

`MODE` は Strata の C++/CUDA エンジン設定ではなく、`apps/host/scripts/agent-http.mjs` の `plan` コマンドと `apps/host/scripts/task-flow-s4b.mjs` が読むスクリプト用環境変数です。前者はチャットの実行モード、後者は作成する定期タスクの実行モードとしてホスト API に渡します。どちらも手動実行する確認スクリプトで、通常のホスト起動時に自動で読まれる設定ではありません。

## 値と判定

値を文字列としてそのまま使い、trim・大文字小文字変換・数値変換はしません。JavaScript の `??` を使うため、未設定 (`undefined`) のみ既定値になります。空文字列は設定値として渡されます。

| 読み取り箇所 | 未設定時 | 空文字・その他の値 |
|---|---|---|
| `agent-http.mjs` の `plan` コマンド | `manual` | 値を `/api/chat/stream` と `/api/plan/start-goal` の本文に渡す。ホストの agent bridge は `manual` / `plan` / `bypass` 以外を `manual` に正規化する。 |
| `task-flow-s4b.mjs` | `bypass` | 値を `POST /api/tasks` の `mode` に渡す。ホストは `plan` / `manual` / `bypass` 以外を拒否し、HTTP 400 と `Choose what this task may do.` を返す。 |

有効なモード文字列は `plan`、`manual`、`bypass` の完全一致です。たとえば `MODE=Plan` は一致しません。タスク経路では無効値が作成を失敗させます。agent-http 経路では無効値は ask-first の `manual` にフォールバックします。`MODE=` はどちらの経路でも既定値にはならず、agent-http では `manual`、タスク作成では 400 エラーになります。

## 有効になる条件

- `agent-http.mjs` ではコマンドラインのサブコマンドが `plan` の場合に限り参照されます。`plan` は `/plan <task>` を送り、その後プランを goal として開始する確認フローです。`MODE` が作る設定は、タスク作成 API には影響しません。
- `task-flow-s4b.mjs` は同ファイルを手動起動したときに読みます。スクリプトはタスクを現在時刻から約2分後に実行する設定で `POST /api/tasks` に送ります。`MODE` はそのタスクに保存されるモードです。
- OS/backend/build macro による分岐はこれらの読み取り箇所にはありません。タスク実行時に agent が利用できない場合の別経路もあり、タスクの `mode` が常に agent に適用されるとは限りません。

## 実行時の詳細

`agent-http.mjs` は `/plan` コマンドを受けたときに `process.env.MODE ?? 'manual'` を評価し、その値を共通リクエスト本文に入れます。環境変数はそのコマンド実行時に読み、以後この値を更新しても既に作られた本文には反映されません。ホストはチャット本文の mode を文字列として受け取り、agent bridge の `modeOf()` が既知の3値を保ち、それ以外を `DEFAULT_MODE` の `manual` にします。bridge はターン開始時にそのモードを適用し、設定確認に失敗すれば「so nothing ran」とする `mode-unavailable` エラーを返します。Manual の場合は gate の確認も必要です。モードは1ターンごとに適用されます。

`task-flow-s4b.mjs` は `MODE` をタスク作成 JSON に含めます。ホストの `validateTask()` が3値以外を拒否します。作成されたタスクのモードは agent task runner に渡されますが、実際の runner は agent が利用可能な場合にだけ選ばれます。agent が unavailable のとき、タスクサービスは別の `runTurn()` 経路に進みます。この環境変数自体に cache はありません。各スクリプトプロセスが該当箇所を実行した時点の値を読みます。

観測できる結果として、agent-http スクリプトはストリームのフレームを表示し、HTTP エラーなら status を含む例外を投げます。タスク経路では作成リクエストの失敗は HTTP 400 になり、確認スクリプトは `FAIL` を表示して終了コード 1 になります。Strata エンジン側で `MODE` を読む箇所は確認できません。

## 根拠

- `apps/host/scripts/agent-http.mjs:144-160` — `plan` コマンドでの読取、`manual` 既定値、HTTP API への転送。
- `apps/host/scripts/agent-http.mjs:18-23,34-38` — HTTP エラーの例外化、stream の status 判定。
- `apps/host/server/index.mjs:630-639,1980-1983,2009-2015` — チャット mode の受け渡しと agent turn の呼出し。
- `apps/host/server/agent/profile.mjs:39-54` — 有効な3値と無効値の `manual` fallback。
- `apps/host/server/agent/agent-bridge.mjs:304-328,408-411` — turn ごとの mode 適用、Manual gate 条件、適用失敗経路。
- `apps/host/scripts/task-flow-s4b.mjs:1-3,18-21,37-39` — 手動確認スクリプト、`bypass` 既定値、タスク作成 API への転送、失敗時終了。
- `apps/host/server/index.mjs:923-932,1266-1267` — タスク実行経路の選択と作成 API。
- `apps/host/server/tasks.mjs:8-22,61-71` — タスク mode の検証と作成時のエラー。
- `apps/host/server/agent/task-run.mjs:14-27` — 保存したタスク mode の agent turn への受け渡し。
