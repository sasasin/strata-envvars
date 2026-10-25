# Strata CLI オプション文書 索引

この索引は Strata のユーザー向け CLI 入口と、そのコマンド階層ごとのオプション文書を列挙します。リンク先の文書は今後作成する予定の項目も含みます。したがって、現時点でリンク先の Markdown が未作成でも、この索引では予定パスとして掲載しています。

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。

文書配置と調査基準は [`001_investigation.md`](001_investigation.md)、CLI 入口と配布形態は [`000_cli_tools.md`](000_cli_tools.md) を参照してください。各コマンドの概要ページは `docs/cli/<tool-id>/<command-path>/README.md`、オプション文書は `docs/cli/<tool-id>/<command-path>/<option-name>.md` に置きます。以下の「コマンド概要」とオプションのリンク先は、今後作成する予定のものも含みます。短縮名・同じ parser action の alias は正規の長い名前の文書にまとめます。

## 索引の対象境界

- `strata-terminal`: `strata_cli/cli.py` と登録されたサブコマンド parser、および `strata_cli/launch/cmd.py` の `launch` / `connect`。POSIX/Windows の wrapper は同じ Python CLI を起動するため共通索引です。
- `strata-engine`: CMake で作られるネイティブ `strata` 推論エンジンの `src/program/generate.cpp` の引数 parser。`--native` から起動する別ファミリー実装への引数転送もエンジンのスコープに含めます。
- `source-setup`: `setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` が委譲する `setup.py` のオプション。ラッパー独自の引数解釈はなく、同じオプション文書を共有します。
- `quick-benchmark`: `bench.sh` / `BENCH.bat` が委譲する `tools/strata_bench.py` のオプション。
- GitHub Release installers `install.sh` / `install.ps1` は呼び出し時の CLI 引数を解釈せず、設定は環境変数で行うため、この索引に CLI option 文書はありません。環境変数文書側を参照してください。
- `CMakeLists.txt` 等で生成される `*_test`、`*_parity`、`*_bench`、個別 probe はビルド条件・個別用途の開発/検証プログラムです。製品 CLI のサブコマンドとして一括索引化せず、対象に含める場合は各プログラムの利用者・build target・parser を確認して別の tool-id として追加します。

## `strata-terminal`

Python 製 Terminal CLI (`strata.py`、`strata_cli/`)。最上位の `strata --help` と `--version`、その配下のコマンドごとに parser スコープを分けています。各オプション名は個別文書への予定リンクです。

### `strata` (トップレベル)

- [コマンド概要](strata-terminal/root/README.md)

- [`--help`（alias: `-h`）](strata-terminal/root/--help.md)
- [`--version`](strata-terminal/root/--version.md)

### `strata serve` (serve)

- [コマンド概要](strata-terminal/serve/README.md)

- [`--batch-groups`](strata-terminal/serve/--batch-groups.md)
- [`--batch-telemetry`（alias: `--no-batch-telemetry`）](strata-terminal/serve/--batch-telemetry.md)
- [`--engine`](strata-terminal/serve/--engine.md)
- [`--help`（alias: `-h`）](strata-terminal/serve/--help.md)
- [`--host`](strata-terminal/serve/--host.md)
- [`--json`](strata-terminal/serve/--json.md)
- [`--max-queue`](strata-terminal/serve/--max-queue.md)
- [`--offline`](strata-terminal/serve/--offline.md)
- [`--output`](strata-terminal/serve/--output.md)
- [`--parallel`](strata-terminal/serve/--parallel.md)
- [`--plan`](strata-terminal/serve/--plan.md)
- [`--port`](strata-terminal/serve/--port.md)
- [`--profile`（alias: `--config`）](strata-terminal/serve/--profile.md)
- [`--queue-timeout`](strata-terminal/serve/--queue-timeout.md)
- [`--quiet`](strata-terminal/serve/--quiet.md)
- [`--ready-file`](strata-terminal/serve/--ready-file.md)
- [`--shutdown-timeout`](strata-terminal/serve/--shutdown-timeout.md)

### `strata profile` (profile)

- [コマンド概要](strata-terminal/profile/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/--help.md)

### `strata profile create` (profile/create)

- [コマンド概要](strata-terminal/profile/create/README.md)

- [`--from-config`](strata-terminal/profile/create/--from-config.md)
- [`--help`（alias: `-h`）](strata-terminal/profile/create/--help.md)
- [`--json`](strata-terminal/profile/create/--json.md)
- [`--output`](strata-terminal/profile/create/--output.md)
- [`--quiet`](strata-terminal/profile/create/--quiet.md)

### `strata profile list` (profile/list)

- [コマンド概要](strata-terminal/profile/list/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/list/--help.md)
- [`--json`](strata-terminal/profile/list/--json.md)
- [`--output`](strata-terminal/profile/list/--output.md)
- [`--quiet`](strata-terminal/profile/list/--quiet.md)

### `strata profile show` (profile/show)

- [コマンド概要](strata-terminal/profile/show/README.md)

- [`--effective`](strata-terminal/profile/show/--effective.md)
- [`--help`（alias: `-h`）](strata-terminal/profile/show/--help.md)
- [`--json`](strata-terminal/profile/show/--json.md)
- [`--output`](strata-terminal/profile/show/--output.md)
- [`--quiet`](strata-terminal/profile/show/--quiet.md)

### `strata profile validate` (profile/validate)

- [コマンド概要](strata-terminal/profile/validate/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/validate/--help.md)
- [`--json`](strata-terminal/profile/validate/--json.md)
- [`--output`](strata-terminal/profile/validate/--output.md)
- [`--quiet`](strata-terminal/profile/validate/--quiet.md)

### `strata profile set` (profile/set)

- [コマンド概要](strata-terminal/profile/set/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/set/--help.md)
- [`--json`](strata-terminal/profile/set/--json.md)
- [`--output`](strata-terminal/profile/set/--output.md)
- [`--plan`](strata-terminal/profile/set/--plan.md)
- [`--quiet`](strata-terminal/profile/set/--quiet.md)

### `strata profile use-config` (profile/use-config)

- [コマンド概要](strata-terminal/profile/use-config/README.md)

- [`--from-config`](strata-terminal/profile/use-config/--from-config.md)
- [`--help`（alias: `-h`）](strata-terminal/profile/use-config/--help.md)
- [`--if-revision`](strata-terminal/profile/use-config/--if-revision.md)
- [`--json`](strata-terminal/profile/use-config/--json.md)
- [`--output`](strata-terminal/profile/use-config/--output.md)
- [`--plan`](strata-terminal/profile/use-config/--plan.md)
- [`--quiet`](strata-terminal/profile/use-config/--quiet.md)

### `strata profile edit` (profile/edit)

- [コマンド概要](strata-terminal/profile/edit/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/edit/--help.md)
- [`--json`](strata-terminal/profile/edit/--json.md)
- [`--output`](strata-terminal/profile/edit/--output.md)
- [`--quiet`](strata-terminal/profile/edit/--quiet.md)

### `strata profile history` (profile/history)

- [コマンド概要](strata-terminal/profile/history/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/history/--help.md)
- [`--json`](strata-terminal/profile/history/--json.md)
- [`--output`](strata-terminal/profile/history/--output.md)
- [`--quiet`](strata-terminal/profile/history/--quiet.md)

### `strata profile rollback` (profile/rollback)

- [コマンド概要](strata-terminal/profile/rollback/README.md)

- [`--help`（alias: `-h`）](strata-terminal/profile/rollback/--help.md)
- [`--json`](strata-terminal/profile/rollback/--json.md)
- [`--output`](strata-terminal/profile/rollback/--output.md)
- [`--quiet`](strata-terminal/profile/rollback/--quiet.md)
- [`--to`](strata-terminal/profile/rollback/--to.md)

### `strata repair-access` (repair-access)

- [コマンド概要](strata-terminal/repair-access/README.md)

- [`--help`（alias: `-h`）](strata-terminal/repair-access/--help.md)
- [`--output`](strata-terminal/repair-access/--output.md)

### `strata doctor` (doctor)

- [コマンド概要](strata-terminal/doctor/README.md)

- [`--components`](strata-terminal/doctor/--components.md)
- [`--help`（alias: `-h`）](strata-terminal/doctor/--help.md)
- [`--json`](strata-terminal/doctor/--json.md)
- [`--live`](strata-terminal/doctor/--live.md)
- [`--output`](strata-terminal/doctor/--output.md)
- [`--profile`](strata-terminal/doctor/--profile.md)
- [`--quiet`](strata-terminal/doctor/--quiet.md)

### `strata components` (components)

- [コマンド概要](strata-terminal/components/README.md)

- [`--help`（alias: `-h`）](strata-terminal/components/--help.md)

### `strata components verify` (components/verify)

- [コマンド概要](strata-terminal/components/verify/README.md)

- [`--help`（alias: `-h`）](strata-terminal/components/verify/--help.md)
- [`--json`](strata-terminal/components/verify/--json.md)
- [`--live`](strata-terminal/components/verify/--live.md)
- [`--output`](strata-terminal/components/verify/--output.md)
- [`--profile`](strata-terminal/components/verify/--profile.md)
- [`--quiet`](strata-terminal/components/verify/--quiet.md)

### `strata components plan` (components/plan)

- [コマンド概要](strata-terminal/components/plan/README.md)

- [`--backend`](strata-terminal/components/plan/--backend.md)
- [`--help`（alias: `-h`）](strata-terminal/components/plan/--help.md)
- [`--output`](strata-terminal/components/plan/--output.md)
- [`--target`](strata-terminal/components/plan/--target.md)

### `strata components backends` (components/backends)

- [コマンド概要](strata-terminal/components/backends/README.md)

- [`--help`（alias: `-h`）](strata-terminal/components/backends/--help.md)
- [`--output`](strata-terminal/components/backends/--output.md)

### `strata components engine` (components/engine)

- [コマンド概要](strata-terminal/components/engine/README.md)

- [`--backend`](strata-terminal/components/engine/--backend.md)
- [`--components-dir`](strata-terminal/components/engine/--components-dir.md)
- [`--full`](strata-terminal/components/engine/--full.md)
- [`--help`（alias: `-h`）](strata-terminal/components/engine/--help.md)
- [`--output`](strata-terminal/components/engine/--output.md)

### `strata components update` (components/update)

- [コマンド概要](strata-terminal/components/update/README.md)

- [`--app`](strata-terminal/components/update/--app.md)
- [`--app-version`](strata-terminal/components/update/--app-version.md)
- [`--backend`](strata-terminal/components/update/--backend.md)
- [`--check`](strata-terminal/components/update/--check.md)
- [`--components-dir`](strata-terminal/components/update/--components-dir.md)
- [`--feed`](strata-terminal/components/update/--feed.md)
- [`--force`](strata-terminal/components/update/--force.md)
- [`--help`（alias: `-h`）](strata-terminal/components/update/--help.md)
- [`--json`](strata-terminal/components/update/--json.md)
- [`--model-config`](strata-terminal/components/update/--model-config.md)
- [`--no-control`](strata-terminal/components/update/--no-control.md)
- [`--no-engine`](strata-terminal/components/update/--no-engine.md)
- [`--output`](strata-terminal/components/update/--output.md)
- [`--quiet`](strata-terminal/components/update/--quiet.md)
- [`--wait`](strata-terminal/components/update/--wait.md)

### `strata components rollback` (components/rollback)

- [コマンド概要](strata-terminal/components/rollback/README.md)

- [`--backend`](strata-terminal/components/rollback/--backend.md)
- [`--components-dir`](strata-terminal/components/rollback/--components-dir.md)
- [`--feed`](strata-terminal/components/rollback/--feed.md)
- [`--force`](strata-terminal/components/rollback/--force.md)
- [`--help`（alias: `-h`）](strata-terminal/components/rollback/--help.md)
- [`--json`](strata-terminal/components/rollback/--json.md)
- [`--model-config`](strata-terminal/components/rollback/--model-config.md)
- [`--output`](strata-terminal/components/rollback/--output.md)
- [`--quiet`](strata-terminal/components/rollback/--quiet.md)
- [`--wait`](strata-terminal/components/rollback/--wait.md)

### `strata update` (update)

- [コマンド概要](strata-terminal/update/README.md)

- [`--app`](strata-terminal/update/--app.md)
- [`--app-version`](strata-terminal/update/--app-version.md)
- [`--backend`](strata-terminal/update/--backend.md)
- [`--check`](strata-terminal/update/--check.md)
- [`--components-dir`](strata-terminal/update/--components-dir.md)
- [`--feed`](strata-terminal/update/--feed.md)
- [`--force`](strata-terminal/update/--force.md)
- [`--help`（alias: `-h`）](strata-terminal/update/--help.md)
- [`--json`](strata-terminal/update/--json.md)
- [`--model-config`](strata-terminal/update/--model-config.md)
- [`--no-control`](strata-terminal/update/--no-control.md)
- [`--no-engine`](strata-terminal/update/--no-engine.md)
- [`--output`](strata-terminal/update/--output.md)
- [`--quiet`](strata-terminal/update/--quiet.md)
- [`--wait`](strata-terminal/update/--wait.md)

### `strata models` (models)

- [コマンド概要](strata-terminal/models/README.md)

- [`--help`（alias: `-h`）](strata-terminal/models/--help.md)

### `strata models list` (models/list)

- [コマンド概要](strata-terminal/models/list/README.md)

- [`--connection`](strata-terminal/models/list/--connection.md)
- [`--credential-env`](strata-terminal/models/list/--credential-env.md)
- [`--help`（alias: `-h`）](strata-terminal/models/list/--help.md)
- [`--install-dir`](strata-terminal/models/list/--install-dir.md)
- [`--installed`](strata-terminal/models/list/--installed.md)
- [`--json`](strata-terminal/models/list/--json.md)
- [`--output`](strata-terminal/models/list/--output.md)
- [`--quiet`](strata-terminal/models/list/--quiet.md)
- [`--served`](strata-terminal/models/list/--served.md)
- [`--timeout`](strata-terminal/models/list/--timeout.md)
- [`--url`](strata-terminal/models/list/--url.md)

### `strata models inspect` (models/inspect)

- [コマンド概要](strata-terminal/models/inspect/README.md)

- [`--help`（alias: `-h`）](strata-terminal/models/inspect/--help.md)
- [`--install-dir`](strata-terminal/models/inspect/--install-dir.md)
- [`--json`](strata-terminal/models/inspect/--json.md)
- [`--output`](strata-terminal/models/inspect/--output.md)
- [`--quiet`](strata-terminal/models/inspect/--quiet.md)

### `strata models import` (models/import)

- [コマンド概要](strata-terminal/models/import/README.md)

- [`--help`（alias: `-h`）](strata-terminal/models/import/--help.md)
- [`--json`](strata-terminal/models/import/--json.md)
- [`--output`](strata-terminal/models/import/--output.md)
- [`--plan`](strata-terminal/models/import/--plan.md)
- [`--quiet`](strata-terminal/models/import/--quiet.md)

### `strata models move` (models/move)

- [コマンド概要](strata-terminal/models/move/README.md)

- [`--cancel-file`](strata-terminal/models/move/--cancel-file.md)
- [`--from`](strata-terminal/models/move/--from.md)
- [`--help`（alias: `-h`）](strata-terminal/models/move/--help.md)
- [`--install-dir`](strata-terminal/models/move/--install-dir.md)
- [`--json`](strata-terminal/models/move/--json.md)
- [`--leave`](strata-terminal/models/move/--leave.md)
- [`--output`](strata-terminal/models/move/--output.md)
- [`--plan`](strata-terminal/models/move/--plan.md)
- [`--quiet`](strata-terminal/models/move/--quiet.md)
- [`--resume`](strata-terminal/models/move/--resume.md)
- [`--status`](strata-terminal/models/move/--status.md)

### `strata drafting` (drafting)

- [コマンド概要](strata-terminal/drafting/README.md)

- [`--help`（alias: `-h`）](strata-terminal/drafting/--help.md)

### `strata drafting plan` (drafting/plan)

- [コマンド概要](strata-terminal/drafting/plan/README.md)

- [`--config`](strata-terminal/drafting/plan/--config.md)
- [`--data-dir`](strata-terminal/drafting/plan/--data-dir.md)
- [`--family`](strata-terminal/drafting/plan/--family.md)
- [`--help`（alias: `-h`）](strata-terminal/drafting/plan/--help.md)
- [`--mode`](strata-terminal/drafting/plan/--mode.md)
- [`--output`](strata-terminal/drafting/plan/--output.md)

### `strata drafting fetch` (drafting/fetch)

- [コマンド概要](strata-terminal/drafting/fetch/README.md)

- [`--config`](strata-terminal/drafting/fetch/--config.md)
- [`--data-dir`](strata-terminal/drafting/fetch/--data-dir.md)
- [`--family`](strata-terminal/drafting/fetch/--family.md)
- [`--help`（alias: `-h`）](strata-terminal/drafting/fetch/--help.md)
- [`--if-needed`](strata-terminal/drafting/fetch/--if-needed.md)
- [`--mode`](strata-terminal/drafting/fetch/--mode.md)
- [`--output`](strata-terminal/drafting/fetch/--output.md)

### `strata engine` (engine)

- [コマンド概要](strata-terminal/engine/README.md)

- [`--help`（alias: `-h`）](strata-terminal/engine/--help.md)

### `strata engine calibrate` (engine/calibrate)

- [コマンド概要](strata-terminal/engine/calibrate/README.md)

- [`--apply-result`](strata-terminal/engine/calibrate/--apply-result.md)
- [`--exclusive`](strata-terminal/engine/calibrate/--exclusive.md)
- [`--help`（alias: `-h`）](strata-terminal/engine/calibrate/--help.md)
- [`--json`](strata-terminal/engine/calibrate/--json.md)
- [`--measure`](strata-terminal/engine/calibrate/--measure.md)
- [`--out`](strata-terminal/engine/calibrate/--out.md)
- [`--output`](strata-terminal/engine/calibrate/--output.md)
- [`--plan`](strata-terminal/engine/calibrate/--plan.md)
- [`--profile`](strata-terminal/engine/calibrate/--profile.md)
- [`--quiet`](strata-terminal/engine/calibrate/--quiet.md)
- [`--review-result`](strata-terminal/engine/calibrate/--review-result.md)
- [`--review-rollback`](strata-terminal/engine/calibrate/--review-rollback.md)
- [`--rollback-result`](strata-terminal/engine/calibrate/--rollback-result.md)

### `strata install` (install)

- [コマンド概要](strata-terminal/install/README.md)

- [`--help`（alias: `-h`）](strata-terminal/install/--help.md)
- [`--update`](strata-terminal/install/--update.md)

### `strata runtime` (runtime)

- [コマンド概要](strata-terminal/runtime/README.md)

- [`--help`（alias: `-h`）](strata-terminal/runtime/--help.md)

### `strata runtime start` (runtime/start)

- [コマンド概要](strata-terminal/runtime/start/README.md)

- [`--die-with-pid`](strata-terminal/runtime/start/--die-with-pid.md)
- [`--help`（alias: `-h`）](strata-terminal/runtime/start/--help.md)
- [`--json`](strata-terminal/runtime/start/--json.md)
- [`--output`](strata-terminal/runtime/start/--output.md)
- [`--plan`](strata-terminal/runtime/start/--plan.md)
- [`--profile`](strata-terminal/runtime/start/--profile.md)
- [`--quiet`](strata-terminal/runtime/start/--quiet.md)
- [`--shutdown-timeout`](strata-terminal/runtime/start/--shutdown-timeout.md)
- [`--wait`](strata-terminal/runtime/start/--wait.md)

### `strata runtime status` (runtime/status)

- [コマンド概要](strata-terminal/runtime/status/README.md)

- [`--help`（alias: `-h`）](strata-terminal/runtime/status/--help.md)
- [`--json`](strata-terminal/runtime/status/--json.md)
- [`--output`](strata-terminal/runtime/status/--output.md)
- [`--profile`](strata-terminal/runtime/status/--profile.md)
- [`--quiet`](strata-terminal/runtime/status/--quiet.md)

### `strata runtime verify` (runtime/verify)

- [コマンド概要](strata-terminal/runtime/verify/README.md)

- [`--help`（alias: `-h`）](strata-terminal/runtime/verify/--help.md)
- [`--if-instance-id`](strata-terminal/runtime/verify/--if-instance-id.md)
- [`--if-owner-id`](strata-terminal/runtime/verify/--if-owner-id.md)
- [`--json`](strata-terminal/runtime/verify/--json.md)
- [`--load`](strata-terminal/runtime/verify/--load.md)
- [`--output`](strata-terminal/runtime/verify/--output.md)
- [`--plan`](strata-terminal/runtime/verify/--plan.md)
- [`--profile`](strata-terminal/runtime/verify/--profile.md)
- [`--quiet`](strata-terminal/runtime/verify/--quiet.md)
- [`--wait`](strata-terminal/runtime/verify/--wait.md)

### `strata runtime stop` (runtime/stop)

- [コマンド概要](strata-terminal/runtime/stop/README.md)

- [`--help`（alias: `-h`）](strata-terminal/runtime/stop/--help.md)
- [`--if-instance-id`](strata-terminal/runtime/stop/--if-instance-id.md)
- [`--if-owner-id`](strata-terminal/runtime/stop/--if-owner-id.md)
- [`--json`](strata-terminal/runtime/stop/--json.md)
- [`--output`](strata-terminal/runtime/stop/--output.md)
- [`--plan`](strata-terminal/runtime/stop/--plan.md)
- [`--profile`](strata-terminal/runtime/stop/--profile.md)
- [`--quiet`](strata-terminal/runtime/stop/--quiet.md)
- [`--wait`](strata-terminal/runtime/stop/--wait.md)

### `strata runtime cleanup` (runtime/cleanup)

- [コマンド概要](strata-terminal/runtime/cleanup/README.md)

- [`--help`（alias: `-h`）](strata-terminal/runtime/cleanup/--help.md)
- [`--json`](strata-terminal/runtime/cleanup/--json.md)
- [`--output`](strata-terminal/runtime/cleanup/--output.md)
- [`--profile`](strata-terminal/runtime/cleanup/--profile.md)
- [`--quiet`](strata-terminal/runtime/cleanup/--quiet.md)

### `strata runtime restart` (runtime/restart)

- [コマンド概要](strata-terminal/runtime/restart/README.md)

- [`--allow-source-migration`](strata-terminal/runtime/restart/--allow-source-migration.md)
- [`--allow-source-switch`](strata-terminal/runtime/restart/--allow-source-switch.md)
- [`--help`（alias: `-h`）](strata-terminal/runtime/restart/--help.md)
- [`--if-instance-id`](strata-terminal/runtime/restart/--if-instance-id.md)
- [`--if-owner-id`](strata-terminal/runtime/restart/--if-owner-id.md)
- [`--if-profile-revision`](strata-terminal/runtime/restart/--if-profile-revision.md)
- [`--if-source-sha256`](strata-terminal/runtime/restart/--if-source-sha256.md)
- [`--json`](strata-terminal/runtime/restart/--json.md)
- [`--output`](strata-terminal/runtime/restart/--output.md)
- [`--plan`](strata-terminal/runtime/restart/--plan.md)
- [`--profile`](strata-terminal/runtime/restart/--profile.md)
- [`--quiet`](strata-terminal/runtime/restart/--quiet.md)
- [`--startup-wait`](strata-terminal/runtime/restart/--startup-wait.md)
- [`--wait`](strata-terminal/runtime/restart/--wait.md)

### `strata ops` (ops)

- [コマンド概要](strata-terminal/ops/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/--help.md)

### `strata ops init` (ops/init)

- [コマンド概要](strata-terminal/ops/init/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/init/--help.md)
- [`--json`](strata-terminal/ops/init/--json.md)
- [`--output`](strata-terminal/ops/init/--output.md)
- [`--profile`](strata-terminal/ops/init/--profile.md)
- [`--quiet`](strata-terminal/ops/init/--quiet.md)

### `strata ops list` (ops/list)

- [コマンド概要](strata-terminal/ops/list/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/list/--help.md)
- [`--json`](strata-terminal/ops/list/--json.md)
- [`--output`](strata-terminal/ops/list/--output.md)
- [`--profile`](strata-terminal/ops/list/--profile.md)
- [`--quiet`](strata-terminal/ops/list/--quiet.md)

### `strata ops create` (ops/create)

- [コマンド概要](strata-terminal/ops/create/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/create/--help.md)
- [`--json`](strata-terminal/ops/create/--json.md)
- [`--kind`](strata-terminal/ops/create/--kind.md)
- [`--output`](strata-terminal/ops/create/--output.md)
- [`--profile`](strata-terminal/ops/create/--profile.md)
- [`--quiet`](strata-terminal/ops/create/--quiet.md)

### `strata ops show` (ops/show)

- [コマンド概要](strata-terminal/ops/show/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/show/--help.md)
- [`--json`](strata-terminal/ops/show/--json.md)
- [`--output`](strata-terminal/ops/show/--output.md)
- [`--profile`](strata-terminal/ops/show/--profile.md)
- [`--quiet`](strata-terminal/ops/show/--quiet.md)

### `strata ops edit` (ops/edit)

- [コマンド概要](strata-terminal/ops/edit/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/edit/--help.md)
- [`--json`](strata-terminal/ops/edit/--json.md)
- [`--output`](strata-terminal/ops/edit/--output.md)
- [`--profile`](strata-terminal/ops/edit/--profile.md)
- [`--quiet`](strata-terminal/ops/edit/--quiet.md)

### `strata ops set` (ops/set)

- [コマンド概要](strata-terminal/ops/set/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/set/--help.md)
- [`--json`](strata-terminal/ops/set/--json.md)
- [`--output`](strata-terminal/ops/set/--output.md)
- [`--plan`](strata-terminal/ops/set/--plan.md)
- [`--profile`](strata-terminal/ops/set/--profile.md)
- [`--quiet`](strata-terminal/ops/set/--quiet.md)

### `strata ops history` (ops/history)

- [コマンド概要](strata-terminal/ops/history/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/history/--help.md)
- [`--json`](strata-terminal/ops/history/--json.md)
- [`--output`](strata-terminal/ops/history/--output.md)
- [`--profile`](strata-terminal/ops/history/--profile.md)
- [`--quiet`](strata-terminal/ops/history/--quiet.md)

### `strata ops rollback` (ops/rollback)

- [コマンド概要](strata-terminal/ops/rollback/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/rollback/--help.md)
- [`--json`](strata-terminal/ops/rollback/--json.md)
- [`--output`](strata-terminal/ops/rollback/--output.md)
- [`--profile`](strata-terminal/ops/rollback/--profile.md)
- [`--quiet`](strata-terminal/ops/rollback/--quiet.md)
- [`--to`](strata-terminal/ops/rollback/--to.md)

### `strata ops plan` (ops/plan)

- [コマンド概要](strata-terminal/ops/plan/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/plan/--help.md)
- [`--json`](strata-terminal/ops/plan/--json.md)
- [`--output`](strata-terminal/ops/plan/--output.md)
- [`--profile`](strata-terminal/ops/plan/--profile.md)
- [`--quiet`](strata-terminal/ops/plan/--quiet.md)

### `strata ops run` (ops/run)

- [コマンド概要](strata-terminal/ops/run/README.md)

- [`--exclusive`](strata-terminal/ops/run/--exclusive.md)
- [`--help`（alias: `-h`）](strata-terminal/ops/run/--help.md)
- [`--if-instance-id`](strata-terminal/ops/run/--if-instance-id.md)
- [`--if-owner-id`](strata-terminal/ops/run/--if-owner-id.md)
- [`--if-profile-revision`](strata-terminal/ops/run/--if-profile-revision.md)
- [`--if-revision`](strata-terminal/ops/run/--if-revision.md)
- [`--if-source-sha256`](strata-terminal/ops/run/--if-source-sha256.md)
- [`--json`](strata-terminal/ops/run/--json.md)
- [`--output`](strata-terminal/ops/run/--output.md)
- [`--profile`](strata-terminal/ops/run/--profile.md)
- [`--quiet`](strata-terminal/ops/run/--quiet.md)

### `strata ops runs` (ops/runs)

- [コマンド概要](strata-terminal/ops/runs/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/runs/--help.md)
- [`--json`](strata-terminal/ops/runs/--json.md)
- [`--limit`](strata-terminal/ops/runs/--limit.md)
- [`--output`](strata-terminal/ops/runs/--output.md)
- [`--profile`](strata-terminal/ops/runs/--profile.md)
- [`--quiet`](strata-terminal/ops/runs/--quiet.md)

### `strata ops result` (ops/result)

- [コマンド概要](strata-terminal/ops/result/README.md)

- [`--help`（alias: `-h`）](strata-terminal/ops/result/--help.md)
- [`--json`](strata-terminal/ops/result/--json.md)
- [`--output`](strata-terminal/ops/result/--output.md)
- [`--profile`](strata-terminal/ops/result/--profile.md)
- [`--quiet`](strata-terminal/ops/result/--quiet.md)

### `strata bench` (bench)

- [コマンド概要](strata-terminal/bench/README.md)

- [`--help`（alias: `-h`）](strata-terminal/bench/--help.md)

### `strata bench run` (bench/run)

- [コマンド概要](strata-terminal/bench/run/README.md)

- [`--background`](strata-terminal/bench/run/--background.md)
- [`--build-options`](strata-terminal/bench/run/--build-options.md)
- [`--concurrency`](strata-terminal/bench/run/--concurrency.md)
- [`--condition`](strata-terminal/bench/run/--condition.md)
- [`--credential-env`](strata-terminal/bench/run/--credential-env.md)
- [`--custom-pack`](strata-terminal/bench/run/--custom-pack.md)
- [`--help`（alias: `-h`）](strata-terminal/bench/run/--help.md)
- [`--json`](strata-terminal/bench/run/--json.md)
- [`--load-timeout`](strata-terminal/bench/run/--load-timeout.md)
- [`--model-revision`](strata-terminal/bench/run/--model-revision.md)
- [`--no-start`](strata-terminal/bench/run/--no-start.md)
- [`--optional-concurrency`](strata-terminal/bench/run/--optional-concurrency.md)
- [`--out`](strata-terminal/bench/run/--out.md)
- [`--output`](strata-terminal/bench/run/--output.md)
- [`--profile`](strata-terminal/bench/run/--profile.md)
- [`--quantization`](strata-terminal/bench/run/--quantization.md)
- [`--quiet`](strata-terminal/bench/run/--quiet.md)
- [`--repeat`](strata-terminal/bench/run/--repeat.md)
- [`--request-timeout`](strata-terminal/bench/run/--request-timeout.md)
- [`--require-managed-match`](strata-terminal/bench/run/--require-managed-match.md)
- [`--skip-model-hash`](strata-terminal/bench/run/--skip-model-hash.md)
- [`--source-revision`](strata-terminal/bench/run/--source-revision.md)
- [`--suite`](strata-terminal/bench/run/--suite.md)
- [`--telemetry-credential-env`](strata-terminal/bench/run/--telemetry-credential-env.md)
- [`--tokenizer-revision`](strata-terminal/bench/run/--tokenizer-revision.md)
- [`--track`](strata-terminal/bench/run/--track.md)
- [`--track-notes`](strata-terminal/bench/run/--track-notes.md)
- [`--url`](strata-terminal/bench/run/--url.md)

### `strata bench cancel` (bench/cancel)

- [コマンド概要](strata-terminal/bench/cancel/README.md)

- [`--help`（alias: `-h`）](strata-terminal/bench/cancel/--help.md)
- [`--output`](strata-terminal/bench/cancel/--output.md)
- [`--path`](strata-terminal/bench/cancel/--path.md)
- [`--profile`](strata-terminal/bench/cancel/--profile.md)

### `strata bench report` (bench/report)

- [コマンド概要](strata-terminal/bench/report/README.md)

- [`--help`（alias: `-h`）](strata-terminal/bench/report/--help.md)
- [`--json`](strata-terminal/bench/report/--json.md)
- [`--out`](strata-terminal/bench/report/--out.md)
- [`--output`](strata-terminal/bench/report/--output.md)
- [`--quiet`](strata-terminal/bench/report/--quiet.md)

### `strata bench compare` (bench/compare)

- [コマンド概要](strata-terminal/bench/compare/README.md)

- [`--help`（alias: `-h`）](strata-terminal/bench/compare/--help.md)
- [`--json`](strata-terminal/bench/compare/--json.md)
- [`--out`](strata-terminal/bench/compare/--out.md)
- [`--output`](strata-terminal/bench/compare/--output.md)
- [`--quiet`](strata-terminal/bench/compare/--quiet.md)

### `strata timeskip` (timeskip)

- [コマンド概要](strata-terminal/timeskip/README.md)

- [`--help`（alias: `-h`）](strata-terminal/timeskip/--help.md)

### `strata timeskip run` (timeskip/run)

- [コマンド概要](strata-terminal/timeskip/run/README.md)

- [`--attempts`](strata-terminal/timeskip/run/--attempts.md)
- [`--help`（alias: `-h`）](strata-terminal/timeskip/run/--help.md)
- [`--output`](strata-terminal/timeskip/run/--output.md)
- [`--prompt`](strata-terminal/timeskip/run/--prompt.md)
- [`--revise-command`](strata-terminal/timeskip/run/--revise-command.md)
- [`--state-dir`](strata-terminal/timeskip/run/--state-dir.md)
- [`--workspace`](strata-terminal/timeskip/run/--workspace.md)

### `strata timeskip status` (timeskip/status)

- [コマンド概要](strata-terminal/timeskip/status/README.md)

- [`--help`（alias: `-h`）](strata-terminal/timeskip/status/--help.md)
- [`--output`](strata-terminal/timeskip/status/--output.md)
- [`--state-dir`](strata-terminal/timeskip/status/--state-dir.md)

### `strata timeskip list` (timeskip/list)

- [コマンド概要](strata-terminal/timeskip/list/README.md)

- [`--help`（alias: `-h`）](strata-terminal/timeskip/list/--help.md)
- [`--output`](strata-terminal/timeskip/list/--output.md)
- [`--state-dir`](strata-terminal/timeskip/list/--state-dir.md)

### `strata timeskip apply` (timeskip/apply)

- [コマンド概要](strata-terminal/timeskip/apply/README.md)

- [`--attempt`](strata-terminal/timeskip/apply/--attempt.md)
- [`--dry-run`](strata-terminal/timeskip/apply/--dry-run.md)
- [`--help`（alias: `-h`）](strata-terminal/timeskip/apply/--help.md)
- [`--output`](strata-terminal/timeskip/apply/--output.md)
- [`--restore`](strata-terminal/timeskip/apply/--restore.md)
- [`--state-dir`](strata-terminal/timeskip/apply/--state-dir.md)
- [`--workspace`](strata-terminal/timeskip/apply/--workspace.md)

### `strata tune` (tune)

- [コマンド概要](strata-terminal/tune/README.md)

- [`--help`（alias: `-h`）](strata-terminal/tune/--help.md)

### `strata tune plan` (tune/plan)

- [コマンド概要](strata-terminal/tune/plan/README.md)

- [`--backend`](strata-terminal/tune/plan/--backend.md)
- [`--engine`](strata-terminal/tune/plan/--engine.md)
- [`--help`（alias: `-h`）](strata-terminal/tune/plan/--help.md)
- [`--hold`](strata-terminal/tune/plan/--hold.md)
- [`--model`](strata-terminal/tune/plan/--model.md)
- [`--objective`](strata-terminal/tune/plan/--objective.md)
- [`--output`](strata-terminal/tune/plan/--output.md)
- [`--repeats`](strata-terminal/tune/plan/--repeats.md)
- [`--time`](strata-terminal/tune/plan/--time.md)
- [`--trials`](strata-terminal/tune/plan/--trials.md)

### `strata tune run` (tune/run)

- [コマンド概要](strata-terminal/tune/run/README.md)

- [`--api-expect`](strata-terminal/tune/run/--api-expect.md)
- [`--api-port`](strata-terminal/tune/run/--api-port.md)
- [`--api-prompt`](strata-terminal/tune/run/--api-prompt.md)
- [`--backend`](strata-terminal/tune/run/--backend.md)
- [`--boot-timeout`](strata-terminal/tune/run/--boot-timeout.md)
- [`--config`](strata-terminal/tune/run/--config.md)
- [`--context`](strata-terminal/tune/run/--context.md)
- [`--engine`](strata-terminal/tune/run/--engine.md)
- [`--full-digests`](strata-terminal/tune/run/--full-digests.md)
- [`--help`（alias: `-h`）](strata-terminal/tune/run/--help.md)
- [`--hold`](strata-terminal/tune/run/--hold.md)
- [`--max-new`](strata-terminal/tune/run/--max-new.md)
- [`--mode`](strata-terminal/tune/run/--mode.md)
- [`--model`](strata-terminal/tune/run/--model.md)
- [`--model-path`](strata-terminal/tune/run/--model-path.md)
- [`--objective`](strata-terminal/tune/run/--objective.md)
- [`--output`](strata-terminal/tune/run/--output.md)
- [`--prompt-tokens`](strata-terminal/tune/run/--prompt-tokens.md)
- [`--repeats`](strata-terminal/tune/run/--repeats.md)
- [`--request-timeout`](strata-terminal/tune/run/--request-timeout.md)
- [`--state-dir`](strata-terminal/tune/run/--state-dir.md)
- [`--time`](strata-terminal/tune/run/--time.md)
- [`--trials`](strata-terminal/tune/run/--trials.md)

### `strata tune apply` (tune/apply)

- [コマンド概要](strata-terminal/tune/apply/README.md)

- [`--config`](strata-terminal/tune/apply/--config.md)
- [`--context`](strata-terminal/tune/apply/--context.md)
- [`--help`（alias: `-h`）](strata-terminal/tune/apply/--help.md)
- [`--model-path`](strata-terminal/tune/apply/--model-path.md)
- [`--output`](strata-terminal/tune/apply/--output.md)
- [`--state-dir`](strata-terminal/tune/apply/--state-dir.md)

### `strata tune rollback` (tune/rollback)

- [コマンド概要](strata-terminal/tune/rollback/README.md)

- [`--help`（alias: `-h`）](strata-terminal/tune/rollback/--help.md)
- [`--output`](strata-terminal/tune/rollback/--output.md)
- [`--state-dir`](strata-terminal/tune/rollback/--state-dir.md)

### `strata tune status` (tune/status)

- [コマンド概要](strata-terminal/tune/status/README.md)

- [`--help`（alias: `-h`）](strata-terminal/tune/status/--help.md)
- [`--output`](strata-terminal/tune/status/--output.md)
- [`--state-dir`](strata-terminal/tune/status/--state-dir.md)

### `strata tune list` (tune/list)

- [コマンド概要](strata-terminal/tune/list/README.md)

- [`--help`（alias: `-h`）](strata-terminal/tune/list/--help.md)
- [`--output`](strata-terminal/tune/list/--output.md)
- [`--state-dir`](strata-terminal/tune/list/--state-dir.md)

### `strata tune auto` (tune/auto)

- [コマンド概要](strata-terminal/tune/auto/README.md)

- [`--allow-not-repeatable`](strata-terminal/tune/auto/--allow-not-repeatable.md)
- [`--allow-small-differences`](strata-terminal/tune/auto/--allow-small-differences.md)
- [`--boot-timeout`](strata-terminal/tune/auto/--boot-timeout.md)
- [`--goal`](strata-terminal/tune/auto/--goal.md)
- [`--gpu-lock`](strata-terminal/tune/auto/--gpu-lock.md)
- [`--help`（alias: `-h`）](strata-terminal/tune/auto/--help.md)
- [`--leave-ram`](strata-terminal/tune/auto/--leave-ram.md)
- [`--mode`](strata-terminal/tune/auto/--mode.md)
- [`--name`](strata-terminal/tune/auto/--name.md)
- [`--no-quiet-check`](strata-terminal/tune/auto/--no-quiet-check.md)
- [`--no-save`](strata-terminal/tune/auto/--no-save.md)
- [`--output`](strata-terminal/tune/auto/--output.md)
- [`--serve-dir`](strata-terminal/tune/auto/--serve-dir.md)
- [`--status-file`](strata-terminal/tune/auto/--status-file.md)
- [`--time`](strata-terminal/tune/auto/--time.md)
- [`--use`](strata-terminal/tune/auto/--use.md)
- [`--work-dir`](strata-terminal/tune/auto/--work-dir.md)

### `strata presets` (presets)

- [コマンド概要](strata-terminal/presets/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/--help.md)

### `strata presets list` (presets/list)

- [コマンド概要](strata-terminal/presets/list/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/list/--help.md)
- [`--model`](strata-terminal/presets/list/--model.md)
- [`--output`](strata-terminal/presets/list/--output.md)

### `strata presets status` (presets/status)

- [コマンド概要](strata-terminal/presets/status/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/status/--help.md)
- [`--output`](strata-terminal/presets/status/--output.md)

### `strata presets show` (presets/show)

- [コマンド概要](strata-terminal/presets/show/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/show/--help.md)
- [`--output`](strata-terminal/presets/show/--output.md)

### `strata presets apply` (presets/apply)

- [コマンド概要](strata-terminal/presets/apply/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/apply/--help.md)
- [`--output`](strata-terminal/presets/apply/--output.md)

### `strata presets rename` (presets/rename)

- [コマンド概要](strata-terminal/presets/rename/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/rename/--help.md)
- [`--output`](strata-terminal/presets/rename/--output.md)

### `strata presets delete` (presets/delete)

- [コマンド概要](strata-terminal/presets/delete/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/delete/--help.md)
- [`--output`](strata-terminal/presets/delete/--output.md)

### `strata presets undo` (presets/undo)

- [コマンド概要](strata-terminal/presets/undo/README.md)

- [`--config`](strata-terminal/presets/undo/--config.md)
- [`--help`（alias: `-h`）](strata-terminal/presets/undo/--help.md)
- [`--output`](strata-terminal/presets/undo/--output.md)

### `strata presets export` (presets/export)

- [コマンド概要](strata-terminal/presets/export/README.md)

- [`--file`](strata-terminal/presets/export/--file.md)
- [`--help`（alias: `-h`）](strata-terminal/presets/export/--help.md)
- [`--output`](strata-terminal/presets/export/--output.md)

### `strata presets import` (presets/import)

- [コマンド概要](strata-terminal/presets/import/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/import/--help.md)
- [`--output`](strata-terminal/presets/import/--output.md)

### `strata presets effective` (presets/effective)

- [コマンド概要](strata-terminal/presets/effective/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/effective/--help.md)
- [`--output`](strata-terminal/presets/effective/--output.md)

### `strata presets off` (presets/off)

- [コマンド概要](strata-terminal/presets/off/README.md)

- [`--help`（alias: `-h`）](strata-terminal/presets/off/--help.md)
- [`--output`](strata-terminal/presets/off/--output.md)

### `strata presets recheck` (presets/recheck)

- [コマンド概要](strata-terminal/presets/recheck/README.md)

- [`--boot-timeout`](strata-terminal/presets/recheck/--boot-timeout.md)
- [`--gpu-lock`](strata-terminal/presets/recheck/--gpu-lock.md)
- [`--help`（alias: `-h`）](strata-terminal/presets/recheck/--help.md)
- [`--no-quiet-check`](strata-terminal/presets/recheck/--no-quiet-check.md)
- [`--output`](strata-terminal/presets/recheck/--output.md)
- [`--serve-dir`](strata-terminal/presets/recheck/--serve-dir.md)
- [`--status-file`](strata-terminal/presets/recheck/--status-file.md)
- [`--work-dir`](strata-terminal/presets/recheck/--work-dir.md)

### `strata launch` (launch)

- [コマンド概要](strata-terminal/launch/README.md)

- [`--access`](strata-terminal/launch/--access.md)
- [`--api-key`](strata-terminal/launch/--api-key.md)
- [`--api-key-env`](strata-terminal/launch/--api-key-env.md)
- [`--context`](strata-terminal/launch/--context.md)
- [`--data-dir`](strata-terminal/launch/--data-dir.md)
- [`--delete-preset`](strata-terminal/launch/--delete-preset.md)
- [`--drafting`](strata-terminal/launch/--drafting.md)
- [`--dsv41-package`](strata-terminal/launch/--dsv41-package.md)
- [`--family`](strata-terminal/launch/--family.md)
- [`--feed`](strata-terminal/launch/--feed.md)
- [`--gpu`](strata-terminal/launch/--gpu.md)
- [`--gpu-roles`](strata-terminal/launch/--gpu-roles.md)
- [`--help`（alias: `-h`）](strata-terminal/launch/--help.md)
- [`--kv`](strata-terminal/launch/--kv.md)
- [`--list-presets`](strata-terminal/launch/--list-presets.md)
- [`--model`](strata-terminal/launch/--model.md)
- [`--model-path`](strata-terminal/launch/--model-path.md)
- [`--move-data`](strata-terminal/launch/--move-data.md)
- [`--mtp`](strata-terminal/launch/--mtp.md)
- [`--new-key`](strata-terminal/launch/--new-key.md)
- [`--no-api-key`](strata-terminal/launch/--no-api-key.md)
- [`--no-tui`](strata-terminal/launch/--no-tui.md)
- [`--open`](strata-terminal/launch/--open.md)
- [`--output`](strata-terminal/launch/--output.md)
- [`--parallel`](strata-terminal/launch/--parallel.md)
- [`--plan`](strata-terminal/launch/--plan.md)
- [`--pool-cores`](strata-terminal/launch/--pool-cores.md)
- [`--port`](strata-terminal/launch/--port.md)
- [`--preset`](strata-terminal/launch/--preset.md)
- [`--restart`](strata-terminal/launch/--restart.md)
- [`--retune`](strata-terminal/launch/--retune.md)
- [`--save-preset`](strata-terminal/launch/--save-preset.md)
- [`--set`](strata-terminal/launch/--set.md)
- [`--show-key`](strata-terminal/launch/--show-key.md)
- [`--status`](strata-terminal/launch/--status.md)
- [`--stop`](strata-terminal/launch/--stop.md)
- [`--tune`](strata-terminal/launch/--tune.md)
- [`--tune-allow-small`](strata-terminal/launch/--tune-allow-small.md)
- [`--vision`](strata-terminal/launch/--vision.md)
- [`--yes`](strata-terminal/launch/--yes.md)

### `strata connect` (connect)

- [コマンド概要](strata-terminal/connect/README.md)

- [`--check`](strata-terminal/connect/--check.md)
- [`--context`](strata-terminal/connect/--context.md)
- [`--help`（alias: `-h`）](strata-terminal/connect/--help.md)
- [`--key`](strata-terminal/connect/--key.md)
- [`--key-env`](strata-terminal/connect/--key-env.md)
- [`--model`](strata-terminal/connect/--model.md)
- [`--output`](strata-terminal/connect/--output.md)
- [`--preset`](strata-terminal/connect/--preset.md)
- [`--show-key`](strata-terminal/connect/--show-key.md)
- [`--url`](strata-terminal/connect/--url.md)
- [`--write`](strata-terminal/connect/--write.md)
- [`--yes`](strata-terminal/connect/--yes.md)

### `strata status` (status)

- [コマンド概要](strata-terminal/status/README.md)

- [`--connection`](strata-terminal/status/--connection.md)
- [`--credential-env`](strata-terminal/status/--credential-env.md)
- [`--help`（alias: `-h`）](strata-terminal/status/--help.md)
- [`--json`](strata-terminal/status/--json.md)
- [`--output`](strata-terminal/status/--output.md)
- [`--quiet`](strata-terminal/status/--quiet.md)
- [`--timeout`](strata-terminal/status/--timeout.md)
- [`--url`](strata-terminal/status/--url.md)

### `strata monitor` (monitor)

- [コマンド概要](strata-terminal/monitor/README.md)

- [`--color`](strata-terminal/monitor/--color.md)
- [`--connection`](strata-terminal/monitor/--connection.md)
- [`--credential-env`](strata-terminal/monitor/--credential-env.md)
- [`--glyphs`](strata-terminal/monitor/--glyphs.md)
- [`--help`（alias: `-h`）](strata-terminal/monitor/--help.md)
- [`--interval`](strata-terminal/monitor/--interval.md)
- [`--json`](strata-terminal/monitor/--json.md)
- [`--once`](strata-terminal/monitor/--once.md)
- [`--output`](strata-terminal/monitor/--output.md)
- [`--quiet`](strata-terminal/monitor/--quiet.md)
- [`--requests`](strata-terminal/monitor/--requests.md)
- [`--theme`](strata-terminal/monitor/--theme.md)
- [`--timeout`](strata-terminal/monitor/--timeout.md)
- [`--url`](strata-terminal/monitor/--url.md)

### `strata logs` (logs)

- [コマンド概要](strata-terminal/logs/README.md)

- [`--connection`](strata-terminal/logs/--connection.md)
- [`--credential-env`](strata-terminal/logs/--credential-env.md)
- [`--follow`](strata-terminal/logs/--follow.md)
- [`--help`（alias: `-h`）](strata-terminal/logs/--help.md)
- [`--interval`](strata-terminal/logs/--interval.md)
- [`--json`](strata-terminal/logs/--json.md)
- [`--output`](strata-terminal/logs/--output.md)
- [`--quiet`](strata-terminal/logs/--quiet.md)
- [`--source`](strata-terminal/logs/--source.md)
- [`--timeout`](strata-terminal/logs/--timeout.md)
- [`--url`](strata-terminal/logs/--url.md)

### `strata connection` (connection)

- [コマンド概要](strata-terminal/connection/README.md)

- [`--help`（alias: `-h`）](strata-terminal/connection/--help.md)

### `strata connection create` (connection/create)

- [コマンド概要](strata-terminal/connection/create/README.md)

- [`--credential-env`](strata-terminal/connection/create/--credential-env.md)
- [`--help`（alias: `-h`）](strata-terminal/connection/create/--help.md)
- [`--json`](strata-terminal/connection/create/--json.md)
- [`--output`](strata-terminal/connection/create/--output.md)
- [`--prefix`](strata-terminal/connection/create/--prefix.md)
- [`--quiet`](strata-terminal/connection/create/--quiet.md)
- [`--url`](strata-terminal/connection/create/--url.md)

### `strata connection show` (connection/show)

- [コマンド概要](strata-terminal/connection/show/README.md)

- [`--help`（alias: `-h`）](strata-terminal/connection/show/--help.md)
- [`--json`](strata-terminal/connection/show/--json.md)
- [`--output`](strata-terminal/connection/show/--output.md)
- [`--quiet`](strata-terminal/connection/show/--quiet.md)

### `strata connection list` (connection/list)

- [コマンド概要](strata-terminal/connection/list/README.md)

- [`--help`（alias: `-h`）](strata-terminal/connection/list/--help.md)
- [`--json`](strata-terminal/connection/list/--json.md)
- [`--output`](strata-terminal/connection/list/--output.md)
- [`--quiet`](strata-terminal/connection/list/--quiet.md)

### `strata connection set` (connection/set)

- [コマンド概要](strata-terminal/connection/set/README.md)

- [`--help`（alias: `-h`）](strata-terminal/connection/set/--help.md)
- [`--if-revision`](strata-terminal/connection/set/--if-revision.md)
- [`--json`](strata-terminal/connection/set/--json.md)
- [`--output`](strata-terminal/connection/set/--output.md)
- [`--plan`](strata-terminal/connection/set/--plan.md)
- [`--quiet`](strata-terminal/connection/set/--quiet.md)

### `strata config` (config)

- [コマンド概要](strata-terminal/config/README.md)

- [`--help`（alias: `-h`）](strata-terminal/config/--help.md)

### `strata config show` (config/show)

- [コマンド概要](strata-terminal/config/show/README.md)

- [`--connection`](strata-terminal/config/show/--connection.md)
- [`--credential-env`](strata-terminal/config/show/--credential-env.md)
- [`--effective`](strata-terminal/config/show/--effective.md)
- [`--help`（alias: `-h`）](strata-terminal/config/show/--help.md)
- [`--json`](strata-terminal/config/show/--json.md)
- [`--output`](strata-terminal/config/show/--output.md)
- [`--quiet`](strata-terminal/config/show/--quiet.md)
- [`--timeout`](strata-terminal/config/show/--timeout.md)
- [`--url`](strata-terminal/config/show/--url.md)

### `strata code` (code)

- [コマンド概要](strata-terminal/code/README.md)

- [`--help`（alias: `-h`）](strata-terminal/code/--help.md)
- [`--quiet`](strata-terminal/code/--quiet.md)
- [`--resume`](strata-terminal/code/--resume.md)
- [`--workspace`](strata-terminal/code/--workspace.md)

### `strata code run` (code/run)

- [コマンド概要](strata-terminal/code/run/README.md)

- [`--help`（alias: `-h`）](strata-terminal/code/run/--help.md)
- [`--output`](strata-terminal/code/run/--output.md)
- [`--policy`](strata-terminal/code/run/--policy.md)
- [`--prompt-file`](strata-terminal/code/run/--prompt-file.md)
- [`--quiet`](strata-terminal/code/run/--quiet.md)

### `strata code sessions` (code/sessions)

- [コマンド概要](strata-terminal/code/sessions/README.md)

- [`--help`（alias: `-h`）](strata-terminal/code/sessions/--help.md)
- [`--json`](strata-terminal/code/sessions/--json.md)
- [`--output`](strata-terminal/code/sessions/--output.md)
- [`--quiet`](strata-terminal/code/sessions/--quiet.md)

## `strata-engine`

CMake で生成する推論エンジン (`strata` / `strata.exe`)。Terminal CLI の同名 wrapper とは別のプログラムです。一覧は `src/program/generate.cpp` の引数 parser および parser より前に処理される早期終了フラグを基にしています。`--model` は Qwen3.6 専用実装への振り分けで使われます。短縮表記と同一動作の alias は正規名の文書にまとめます。

### `strata` (エンジン引数)

- [コマンド概要](strata-engine/root/README.md)

- [`--adapt-async`](strata-engine/root/--adapt-async.md)
- [`--adapt-decay`](strata-engine/root/--adapt-decay.md)
- [`--adapt-every`](strata-engine/root/--adapt-every.md)
- [`--adapt-min-gain`](strata-engine/root/--adapt-min-gain.md)
- [`--adapt-swaps`](strata-engine/root/--adapt-swaps.md)
- [`--aux-cpus`](strata-engine/root/--aux-cpus.md)
- [`--batch`（alias: `--slots`）](strata-engine/root/--batch.md)
- [`--batch-groups`](strata-engine/root/--batch-groups.md)
- [`--batch-mtp`](strata-engine/root/--batch-mtp.md)
- [`--check-logits`](strata-engine/root/--check-logits.md)
- [`--control-vector`](strata-engine/root/--control-vector.md)
- [`--control-vector-layer-range`](strata-engine/root/--control-vector-layer-range.md)
- [`--control-vector-scaled`](strata-engine/root/--control-vector-scaled.md)
- [`--conversation-cache-mib`](strata-engine/root/--conversation-cache-mib.md)
- [`--conversation-cache-min-free-mib`](strata-engine/root/--conversation-cache-min-free-mib.md)
- [`--conversation-cache-min-tokens`](strata-engine/root/--conversation-cache-min-tokens.md)
- [`--conversation-cache-park-gain`](strata-engine/root/--conversation-cache-park-gain.md)
- [`--conversation-cache-slots`](strata-engine/root/--conversation-cache-slots.md)
- [`--coupled-draft`](strata-engine/root/--coupled-draft.md)
- [`--cpu-oracle-q8-0`](strata-engine/root/--cpu-oracle-q8-0.md)
- [`--cvec-dir`](strata-engine/root/--cvec-dir.md)
- [`--cvec-mode`](strata-engine/root/--cvec-mode.md)
- [`--draft`](strata-engine/root/--draft.md)
- [`--draft-cap`](strata-engine/root/--draft-cap.md)
- [`--draft-conf`](strata-engine/root/--draft-conf.md)
- [`--draft-model`](strata-engine/root/--draft-model.md)
- [`--dump-final-r`](strata-engine/root/--dump-final-r.md)
- [`--dump-halves`](strata-engine/root/--dump-halves.md)
- [`--dump-layers`](strata-engine/root/--dump-layers.md)
- [`--dump-logits`](strata-engine/root/--dump-logits.md)
- [`--dump-mixed`](strata-engine/root/--dump-mixed.md)
- [`--dump-residual`](strata-engine/root/--dump-residual.md)
- [`--dump-routing`](strata-engine/root/--dump-routing.md)
- [`--embd-gguf`](strata-engine/root/--embd-gguf.md)
- [`--eos-ids`](strata-engine/root/--eos-ids.md)
- [`--expert-cache`](strata-engine/root/--expert-cache.md)
- [`--expert-cache-cpu-order`](strata-engine/root/--expert-cache-cpu-order.md)
- [`--expert-cache-device1`](strata-engine/root/--expert-cache-device1.md)
- [`--expert-cache-device2`](strata-engine/root/--expert-cache-device2.md)
- [`--expert-cache-device3`](strata-engine/root/--expert-cache-device3.md)
- [`--expert-cache-per-layer`](strata-engine/root/--expert-cache-per-layer.md)
- [`--expert-cache-remote-placement`](strata-engine/root/--expert-cache-remote-placement.md)
- [`--expert-profile`](strata-engine/root/--expert-profile.md)
- [`--expert-profile-save`](strata-engine/root/--expert-profile-save.md)
- [`--expert-profile-save-every`](strata-engine/root/--expert-profile-save-every.md)
- [`--families`](strata-engine/root/--families.md)
- [`--gpu`](strata-engine/root/--gpu.md)
- [`--gpu-only-full`](strata-engine/root/--gpu-only-full.md)
- [`--gpu-stages`](strata-engine/root/--gpu-stages.md)
- [`--gr-fp32-activations`](strata-engine/root/--gr-fp32-activations.md)
- [`--gr-native-mmvf`](strata-engine/root/--gr-native-mmvf.md)
- [`--graph-only`](strata-engine/root/--graph-only.md)
- [`--greedy`](strata-engine/root/--greedy.md)
- [`--help`（alias: `-h`）](strata-engine/root/--help.md)
- [`--host-core`](strata-engine/root/--host-core.md)
- [`--keep-canonical`](strata-engine/root/--keep-canonical.md)
- [`--kv`](strata-engine/root/--kv.md)
- [`--kv-grow`](strata-engine/root/--kv-grow.md)
- [`--kv-resident`](strata-engine/root/--kv-resident.md)
- [`--layer-split`](strata-engine/root/--layer-split.md)
- [`--logits-stride`](strata-engine/root/--logits-stride.md)
- [`--lookup-chain`](strata-engine/root/--lookup-chain.md)
- [`--lookup-chain-min`](strata-engine/root/--lookup-chain-min.md)
- [`--max-context`](strata-engine/root/--max-context.md)
- [`--max-new`](strata-engine/root/--max-new.md)
- [`--memory-limit-mib`](strata-engine/root/--memory-limit-mib.md)
- [`--mmap-experts`](strata-engine/root/--mmap-experts.md)
- [`--mtp`](strata-engine/root/--mtp.md)
- [`--mtp-draft-vocab`](strata-engine/root/--mtp-draft-vocab.md)
- [`--mtp-hnorm`](strata-engine/root/--mtp-hnorm.md)
- [`--mtp-max-t`](strata-engine/root/--mtp-max-t.md)
- [`--mtp-q4`](strata-engine/root/--mtp-q4.md)
- [`--mtp-window`](strata-engine/root/--mtp-window.md)
- [`--native`](strata-engine/root/--native.md)
- [`--native-bf16`](strata-engine/root/--native-bf16.md)
- [`--native-bf16-extra`](strata-engine/root/--native-bf16-extra.md)
- [`--native-dense-gguf`](strata-engine/root/--native-dense-gguf.md)
- [`--native-flash-attn-short`](strata-engine/root/--native-flash-attn-short.md)
- [`--native-gdn`](strata-engine/root/--native-gdn.md)
- [`--native-head-gguf`](strata-engine/root/--native-head-gguf.md)
- [`--native-moe-combine`](strata-engine/root/--native-moe-combine.md)
- [`--native-ple-key`](strata-engine/root/--native-ple-key.md)
- [`--native-ple-postops`](strata-engine/root/--native-ple-postops.md)
- [`--native-qsa`](strata-engine/root/--native-qsa.md)
- [`--native-qsa-indexer`](strata-engine/root/--native-qsa-indexer.md)
- [`--native-rope`](strata-engine/root/--native-rope.md)
- [`--native-router`](strata-engine/root/--native-router.md)
- [`--no-capture`](strata-engine/root/--no-capture.md)
- [`--no-coupled-draft`](strata-engine/root/--no-coupled-draft.md)
- [`--no-fast-attn`](strata-engine/root/--no-fast-attn.md)
- [`--no-fast-select`](strata-engine/root/--no-fast-select.md)
- [`--no-fused-gdn`](strata-engine/root/--no-fused-gdn.md)
- [`--no-fused-gr`](strata-engine/root/--no-fused-gr.md)
- [`--no-hit-poke`](strata-engine/root/--no-hit-poke.md)
- [`--no-host-worker`](strata-engine/root/--no-host-worker.md)
- [`--no-kv-grow`](strata-engine/root/--no-kv-grow.md)
- [`--no-ple`](strata-engine/root/--no-ple.md)
- [`--no-ple-prefetch`](strata-engine/root/--no-ple-prefetch.md)
- [`--no-pool`](strata-engine/root/--no-pool.md)
- [`--no-prefill-borrow`](strata-engine/root/--no-prefill-borrow.md)
- [`--no-publish-kernel`](strata-engine/root/--no-publish-kernel.md)
- [`--no-spec-split`](strata-engine/root/--no-spec-split.md)
- [`--no-split-rows`](strata-engine/root/--no-split-rows.md)
- [`--no-token-graph`](strata-engine/root/--no-token-graph.md)
- [`--pack`](strata-engine/root/--pack.md)
- [`--pcie-frac`](strata-engine/root/--pcie-frac.md)
- [`--pcie-mode`](strata-engine/root/--pcie-mode.md)
- [`--peer-adapt-swaps`](strata-engine/root/--peer-adapt-swaps.md)
- [`--peer-device`](strata-engine/root/--peer-device.md)
- [`--peer-prefill-rows`](strata-engine/root/--peer-prefill-rows.md)
- [`--peer-reserve-mib`](strata-engine/root/--peer-reserve-mib.md)
- [`--peer-slots`](strata-engine/root/--peer-slots.md)
- [`--pipeline-windows`](strata-engine/root/--pipeline-windows.md)
- [`--ple-delay-us`](strata-engine/root/--ple-delay-us.md)
- [`--ple-gguf`](strata-engine/root/--ple-gguf.md)
- [`--ple-inflight`](strata-engine/root/--ple-inflight.md)
- [`--ple-io`](strata-engine/root/--ple-io.md)
- [`--ple-row-cache`](strata-engine/root/--ple-row-cache.md)
- [`--ple-sync-submit`](strata-engine/root/--ple-sync-submit.md)
- [`--pool-affinity`](strata-engine/root/--pool-affinity.md)
- [`--pool-cores`](strata-engine/root/--pool-cores.md)
- [`--pool-tasks`](strata-engine/root/--pool-tasks.md)
- [`--pool-workers`](strata-engine/root/--pool-workers.md)
- [`--prefill`](strata-engine/root/--prefill.md)
- [`--prefill-head-alias`](strata-engine/root/--prefill-head-alias.md)
- [`--prefill-pipe`](strata-engine/root/--prefill-pipe.md)
- [`--prefill-until`](strata-engine/root/--prefill-until.md)
- [`--prompt-cache`](strata-engine/root/--prompt-cache.md)
- [`--prompt-cache-every`](strata-engine/root/--prompt-cache-every.md)
- [`--prompt-cache-root`](strata-engine/root/--prompt-cache-root.md)
- [`--prompt-cache-spread`](strata-engine/root/--prompt-cache-spread.md)
- [`--prompt-cache-tail`](strata-engine/root/--prompt-cache-tail.md)
- [`--remote-expert-opt`](strata-engine/root/--remote-expert-opt.md)
- [`--resident-budget-gib`](strata-engine/root/--resident-budget-gib.md)
- [`--resident-cpu-experts`](strata-engine/root/--resident-cpu-experts.md)
- [`--resident-experts`](strata-engine/root/--resident-experts.md)
- [`--rope-freq-base`](strata-engine/root/--rope-freq-base.md)
- [`--rope-freq-scale`](strata-engine/root/--rope-freq-scale.md)
- [`--rope-scale`](strata-engine/root/--rope-scale.md)
- [`--rope-scaling`](strata-engine/root/--rope-scaling.md)
- [`--seed`](strata-engine/root/--seed.md)
- [`--serve`](strata-engine/root/--serve.md)
- [`--session-min-free-mib`](strata-engine/root/--session-min-free-mib.md)
- [`--session-save-reclaim`](strata-engine/root/--session-save-reclaim.md)
- [`--shared-expert-arena`](strata-engine/root/--shared-expert-arena.md)
- [`--shared-late`](strata-engine/root/--shared-late.md)
- [`--short-read`](strata-engine/root/--short-read.md)
- [`--spec`](strata-engine/root/--spec.md)
- [`--spec-corrupt`](strata-engine/root/--spec-corrupt.md)
- [`--spec-follow`](strata-engine/root/--spec-follow.md)
- [`--spec-min-p`](strata-engine/root/--spec-min-p.md)
- [`--spec-oracle`](strata-engine/root/--spec-oracle.md)
- [`--spec-split`](strata-engine/root/--spec-split.md)
- [`--split-device`](strata-engine/root/--split-device.md)
- [`--split-skip-if-fits`](strata-engine/root/--split-skip-if-fits.md)
- [`--stage-timing`](strata-engine/root/--stage-timing.md)
- [`--stats`](strata-engine/root/--stats.md)
- [`--stop-eos`](strata-engine/root/--stop-eos.md)
- [`--stream-token`](strata-engine/root/--stream-token.md)
- [`--suffix-draft`](strata-engine/root/--suffix-draft.md)
- [`--sync-every-layer`](strata-engine/root/--sync-every-layer.md)
- [`--tail-role-token`](strata-engine/root/--tail-role-token.md)
- [`--temperature`](strata-engine/root/--temperature.md)
- [`--tokens`](strata-engine/root/--tokens.md)
- [`--tokens-file`](strata-engine/root/--tokens-file.md)
- [`--top-k`](strata-engine/root/--top-k.md)
- [`--top-p`](strata-engine/root/--top-p.md)
- [`--trim-stage-weights`](strata-engine/root/--trim-stage-weights.md)
- [`--turn-token`](strata-engine/root/--turn-token.md)
- [`--version`（alias: `-V`）](strata-engine/root/--version.md)
- [`--vision`](strata-engine/root/--vision.md)
- [`--vram-elastic`](strata-engine/root/--vram-elastic.md)
- [`--vram-reserve-later-mib`](strata-engine/root/--vram-reserve-later-mib.md)
- [`--vram-reserve-mib`](strata-engine/root/--vram-reserve-mib.md)
- [`--vram-segment-mib`](strata-engine/root/--vram-segment-mib.md)
- [`--window-hashes`](strata-engine/root/--window-hashes.md)
- [`--yarn-attn-factor`](strata-engine/root/--yarn-attn-factor.md)
- [`--yarn-beta-fast`](strata-engine/root/--yarn-beta-fast.md)
- [`--yarn-beta-slow`](strata-engine/root/--yarn-beta-slow.md)
- [`--yarn-ext-factor`](strata-engine/root/--yarn-ext-factor.md)
- [`--yarn-orig-ctx`](strata-engine/root/--yarn-orig-ctx.md)

### `strata` / `strata-q36` (Qwen3.6 専用 parser; model 選択時または別 executable)

- [コマンド概要](strata-engine/qwen36/README.md)

Qwen3.6 family に振り分けられたとき `strata` が使う parser です。同じフラグでも通常 engine parser と意味が違う場合があるため、独立した `qwen36/` scope にしています。CMake では `strata-q36` として単独 executable も生成します。

- [`--batch`（alias: `--slots`）](strata-engine/qwen36/--batch.md)
- [`--batch-mtp`](strata-engine/qwen36/--batch-mtp.md)
- [`--bench-pp`](strata-engine/qwen36/--bench-pp.md)
- [`--bench-tg`](strata-engine/qwen36/--bench-tg.md)
- [`--chunk`（alias: `--prefill`）](strata-engine/qwen36/--chunk.md)
- [`--cpu-threads`](strata-engine/qwen36/--cpu-threads.md)
- [`--draft-vocab`](strata-engine/qwen36/--draft-vocab.md)
- [`--dump-full-logits`](strata-engine/qwen36/--dump-full-logits.md)
- [`--emb`](strata-engine/qwen36/--emb.md)
- [`--expert-slots`](strata-engine/qwen36/--expert-slots.md)
- [`--expert-vram`](strata-engine/qwen36/--expert-vram.md)
- [`--force`](strata-engine/qwen36/--force.md)
- [`--gpu`](strata-engine/qwen36/--gpu.md)
- [`--greedy`](strata-engine/qwen36/--greedy.md)
- [`--hybrid-rows`](strata-engine/qwen36/--hybrid-rows.md)
- [`--max-context`（alias: `--ctx`）](strata-engine/qwen36/--max-context.md)
- [`--max-new`](strata-engine/qwen36/--max-new.md)
- [`--model`（alias: `--native`）](strata-engine/qwen36/--model.md)
- [`--mtp`](strata-engine/qwen36/--mtp.md)
- [`--n`](strata-engine/qwen36/--n.md)
- [`--native`](strata-engine/qwen36/--native.md)
- [`--no-graph`](strata-engine/qwen36/--no-graph.md)
- [`--no-token-graph`](strata-engine/qwen36/--no-token-graph.md)
- [`--no-warmup`](strata-engine/qwen36/--no-warmup.md)
- [`--pool-workers`](strata-engine/qwen36/--pool-workers.md)
- [`--serve`](strata-engine/qwen36/--serve.md)
- [`--tokens`](strata-engine/qwen36/--tokens.md)
- [`--vision`](strata-engine/qwen36/--vision.md)

### `strata-dsv41` (optional DeepSeek-V4.1 engine executable)

- [コマンド概要](strata-engine-dsv41/root/README.md)

`STRATA_BUILD_DSV41=ON` の build で生成される独立 engine CLI です。Release での配布有無はこの source inventory からは断定しません。

- [`--cpu-threads`](strata-engine-dsv41/root/--cpu-threads.md)
- [`--dspark`](strata-engine-dsv41/root/--dspark.md)
- [`--dspark-block`](strata-engine-dsv41/root/--dspark-block.md)
- [`--dspark-conf`](strata-engine-dsv41/root/--dspark-conf.md)
- [`--dump-image`](strata-engine-dsv41/root/--dump-image.md)
- [`--dump-logits`](strata-engine-dsv41/root/--dump-logits.md)
- [`--encode-image`](strata-engine-dsv41/root/--encode-image.md)
- [`--eos`](strata-engine-dsv41/root/--eos.md)
- [`--expert-profile`](strata-engine-dsv41/root/--expert-profile.md)
- [`--gpus`](strata-engine-dsv41/root/--gpus.md)
- [`--help`](strata-engine-dsv41/root/--help.md)
- [`--ids`](strata-engine-dsv41/root/--ids.md)
- [`--images`](strata-engine-dsv41/root/--images.md)
- [`--layer-split`](strata-engine-dsv41/root/--layer-split.md)
- [`--max-context`](strata-engine-dsv41/root/--max-context.md)
- [`--mmap-experts`](strata-engine-dsv41/root/--mmap-experts.md)
- [`--n`](strata-engine-dsv41/root/--n.md)
- [`--no-expert-cache`](strata-engine-dsv41/root/--no-expert-cache.md)
- [`--pack`](strata-engine-dsv41/root/--pack.md)
- [`--pack-info`](strata-engine-dsv41/root/--pack-info.md)
- [`--prefill-chunk`](strata-engine-dsv41/root/--prefill-chunk.md)
- [`--profile-run`](strata-engine-dsv41/root/--profile-run.md)
- [`--reserve-mib`](strata-engine-dsv41/root/--reserve-mib.md)
- [`--score`](strata-engine-dsv41/root/--score.md)
- [`--score-out`](strata-engine-dsv41/root/--score-out.md)
- [`--seed`](strata-engine-dsv41/root/--seed.md)
- [`--serve`](strata-engine-dsv41/root/--serve.md)
- [`--size`](strata-engine-dsv41/root/--size.md)
- [`--spec-eval`](strata-engine-dsv41/root/--spec-eval.md)
- [`--ssd-cache`](strata-engine-dsv41/root/--ssd-cache.md)
- [`--ssd-policy`](strata-engine-dsv41/root/--ssd-policy.md)
- [`--temperature`](strata-engine-dsv41/root/--temperature.md)
- [`--threads`](strata-engine-dsv41/root/--threads.md)
- [`--tp`](strata-engine-dsv41/root/--tp.md)
- [`--verbose`（alias: `-v`）](strata-engine-dsv41/root/--verbose.md)
- [`--version`](strata-engine-dsv41/root/--version.md)
- [`--vision`](strata-engine-dsv41/root/--vision.md)
- [`--vram-experts`](strata-engine-dsv41/root/--vram-experts.md)
- [`--window`](strata-engine-dsv41/root/--window.md)

## CMake 生成の単体 CLI（診断・開発用）

`000_cli_tools.md` の関連実行ファイル欄にある単体 CLI を、製品の推論エンジンとは別 tool-id として掲載します。これらは用途や build target が異なり、通常の Terminal CLI のサブコマンドではありません。`strata-dequant` にはオプション parser がなく、GGUF ファイルの位置引数だけを受け付けます。


### `strata-plan` (`src/plan/plan_main.cpp`)

- [コマンド概要](strata-plan/root/README.md)

- [`--dense`](strata-plan/root/--dense.md)
- [`--embd`](strata-plan/root/--embd.md)
- [`--help`](strata-plan/root/--help.md)
- [`--max-context`](strata-plan/root/--max-context.md)
- [`--pool`](strata-plan/root/--pool.md)
- [`--state`](strata-plan/root/--state.md)
- [`--vram`](strata-plan/root/--vram.md)
- [`--workspace`](strata-plan/root/--workspace.md)

### `strata-device` (`src/core/device_main.cpp`)

- [コマンド概要](strata-device/root/README.md)

- [`--help`（alias: `-h`）](strata-device/root/--help.md)
- [`--list-devices`](strata-device/root/--list-devices.md)
- [`--selftest`](strata-device/root/--selftest.md)

### `strata-load` (`src/core/load_main.cpp`)

- [コマンド概要](strata-load/root/README.md)

- [`--chunk-mb`](strata-load/root/--chunk-mb.md)
- [`--file`](strata-load/root/--file.md)
- [`--help`](strata-load/root/--help.md)
- [`--layers`](strata-load/root/--layers.md)
- [`--no-pin`](strata-load/root/--no-pin.md)
- [`--stream`](strata-load/root/--stream.md)
- [`--threads`](strata-load/root/--threads.md)

### `strata-concurrent` (`src/core/concurrent_main.cpp`)

- [コマンド概要](strata-concurrent/root/README.md)

- [`--cpu-threads`](strata-concurrent/root/--cpu-threads.md)
- [`--experts`](strata-concurrent/root/--experts.md)
- [`--file`](strata-concurrent/root/--file.md)
- [`--gpu-roles`](strata-concurrent/root/--gpu-roles.md)

### `strata-overlap` (`src/core/overlap_main.cpp`)

- [コマンド概要](strata-overlap/root/README.md)

- [`--experts`](strata-overlap/root/--experts.md)
- [`--file`](strata-overlap/root/--file.md)
- [`--tpr`](strata-overlap/root/--tpr.md)

### `strata-gguf` (`src/artifact/gguf_reader.cpp`)

- [コマンド概要](strata-gguf/root/README.md)

- [`--check`](strata-gguf/root/--check.md)

### `strata-dequant` (`src/artifact/dequant.cpp`)

- [コマンド概要](strata-dequant/root/README.md)

- オプションなし（位置引数のみ）
## `source-setup`

`setup.py` は初回 setup、既存環境の更新、モデル設定変更を担います。POSIX/Windows の wrapper はここへ引数を渡します。以下は `setup.py --help` の option inventory です。

### `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers

- [コマンド概要](source-setup/root/README.md)

- [`--api-key`](source-setup/root/--api-key.md)
- [`--backend`](source-setup/root/--backend.md)
- [`--browser`](source-setup/root/--browser.md)
- [`--build`](source-setup/root/--build.md)
- [`--calibrate`](source-setup/root/--calibrate.md)
- [`--check`](source-setup/root/--check.md)
- [`--context`](source-setup/root/--context.md)
- [`--cuda`](source-setup/root/--cuda.md)
- [`--data-dir`](source-setup/root/--data-dir.md)
- [`--draft-vocab`](source-setup/root/--draft-vocab.md)
- [`--dsv41-package`](source-setup/root/--dsv41-package.md)
- [`--experimental-speed-projection`](source-setup/root/--experimental-speed-projection.md)
- [`--family`](source-setup/root/--family.md)
- [`--gguf-dir`](source-setup/root/--gguf-dir.md)
- [`--gpu`](source-setup/root/--gpu.md)
- [`--gpu-roles`](source-setup/root/--gpu-roles.md)
- [`--gpus`](source-setup/root/--gpus.md)
- [`--help`（alias: `-h`）](source-setup/root/--help.md)
- [`--host`](source-setup/root/--host.md)
- [`--inspect`](source-setup/root/--inspect.md)
- [`--kv`](source-setup/root/--kv.md)
- [`--kv-streaming`](source-setup/root/--kv-streaming.md)
- [`--layer-split`](source-setup/root/--layer-split.md)
- [`--low-ram`](source-setup/root/--low-ram.md)
- [`--model`](source-setup/root/--model.md)
- [`--models-dir`](source-setup/root/--models-dir.md)
- [`--move-data`](source-setup/root/--move-data.md)
- [`--mtp`](source-setup/root/--mtp.md)
- [`--no-browser`](source-setup/root/--no-browser.md)
- [`--no-remote-expert-opt`](source-setup/root/--no-remote-expert-opt.md)
- [`--no-start`](source-setup/root/--no-start.md)
- [`--parallel`](source-setup/root/--parallel.md)
- [`--port`](source-setup/root/--port.md)
- [`--prebuilt`](source-setup/root/--prebuilt.md)
- [`--remote-expert-opt`](source-setup/root/--remote-expert-opt.md)
- [`--replicas`](source-setup/root/--replicas.md)
- [`--resident-budget-gib`](source-setup/root/--resident-budget-gib.md)
- [`--rollback-engine`](source-setup/root/--rollback-engine.md)
- [`--rope-scale`](source-setup/root/--rope-scale.md)
- [`--rope-scaling`](source-setup/root/--rope-scaling.md)
- [`--set-default-data-dir`](source-setup/root/--set-default-data-dir.md)
- [`--setup`](source-setup/root/--setup.md)
- [`--source`](source-setup/root/--source.md)
- [`--update`](source-setup/root/--update.md)
- [`--vision`](source-setup/root/--vision.md)
- [`--vision-tokens`](source-setup/root/--vision-tokens.md)
- [`--vram-reserve-mib`](source-setup/root/--vram-reserve-mib.md)
- [`--yes`](source-setup/root/--yes.md)

## `quick-benchmark`

`bench.sh` / `BENCH.bat` が起動するローカル quick benchmark (`tools/strata_bench.py`)。標準比較ベンチマークの `strata bench run` は上記 Terminal CLI 索引にあります。

### `bench.sh` / `BENCH.bat`

- [コマンド概要](quick-benchmark/root/README.md)

- [`--api-key`](quick-benchmark/root/--api-key.md)
- [`--clients`](quick-benchmark/root/--clients.md)
- [`--compare`](quick-benchmark/root/--compare.md)
- [`--compare-only`](quick-benchmark/root/--compare-only.md)
- [`--config`](quick-benchmark/root/--config.md)
- [`--gpu`](quick-benchmark/root/--gpu.md)
- [`--help`（alias: `-h`）](quick-benchmark/root/--help.md)
- [`--long`](quick-benchmark/root/--long.md)
- [`--out`](quick-benchmark/root/--out.md)
- [`--port`](quick-benchmark/root/--port.md)
- [`--quiet`](quick-benchmark/root/--quiet.md)
- [`--ready-timeout`](quick-benchmark/root/--ready-timeout.md)
- [`--runs`](quick-benchmark/root/--runs.md)
- [`--think`](quick-benchmark/root/--think.md)
- [`--url`](quick-benchmark/root/--url.md)

## Release installer

Release から配布される `install.sh`（POSIX）と `install.ps1`（Windows）は CLI 引数を定義していません。インストール先などを環境変数で上書きする仕様は対応する `docs/<ENVVAR>.md` に記録し、ここではオプション文書を作成しません。

## 更新時の確認

この索引を更新するときは、`strata_cli/cli.py` および各登録 parser、`setup.py`、`tools/strata_bench.py`、推論エンジンの argv parser を現行 checkout で再確認してください。コマンド/オプションの追加・削除・alias 変更を反映し、`tool-id + command-path + option identity` ごとのパスを維持します。ラッパーが parser へ委譲するだけなら重複登録せず、CMake 開発用 binary は製品 CLI と区別します。

## 更新手順と次回の調査指示

Strata のソースコードが更新されたら、`/home/sasasin/src/github.com/Niko1221/Strata` の更新後 checkout を調査し、この索引を現行のコマンド構造と parser に合わせて更新してください。既存リンクへの追記だけで済ませず、削除・改名・移動されたコマンドやオプション、parser の統合・分岐も見直します。この作業では索引を更新し、リンク先のコマンド概要やオプション文書が未作成でも、規約に合う予定パスを Markdown リンクとして列挙します。

### 調査手順

1. **対象 revision と作業状態を記録する。** Strata リポジトリで `git rev-parse HEAD`、`git status --short --branch`、必要に応じて `git log -1 --format='%h %cs %s'` を確認します。未コミット変更があれば調査対象に含め、既存の変更を上書きしないでください。索引に完全な commit SHA と調査日を記録します。
2. **ツール一覧を照合する。** [`000_cli_tools.md`](000_cli_tools.md) と Strata checkout のルート、`bin/`、`packaging/`、`tools/`、`strata_cli/`、`src/`、各 `CMakeLists.txt` を見直します。CLI のソース、委譲 wrapper、ビルド生成 executable、Release installer と配布対象を区別し、索引に追加・削除すべき tool-id を決めます。
3. **コマンド階層を列挙する。** Terminal CLI は `strata_cli/cli.py` の root parser と、そこから登録される各 module の parser 定義をたどります。`launch` / `connect`、update、drafting 等、別 module で登録される parser も含めます。安全に実行でき、調査 checkout と同じ revision の CLI がある場合は `--help` を補助に使えますが、parser のソース定義を根拠として照合します。
4. **各 parser のオプションと alias を列挙する。** `argparse` 等の宣言、手書き C/C++ の `argv` 解析、早期処理される `--version` / `--families` のようなフラグを確認します。推論エンジンは通常の `src/program/generate.cpp` の parser に加え、Qwen3.6 などの条件付き parser、独立 executable、build 条件を確認します。`setup.py` と `tools/strata_bench.py` はそれぞれの parser を調べ、`setup.sh` / `.bat`、update wrapper、quick-benchmark wrapper が引数を委譲するだけなら重複登録しません。
5. **対象境界を再判定する。** `000_cli_tools.md` に挙がる単体診断 CLI は個別の tool-id として扱います。CMake の `*_test`、`*_parity`、`*_bench`、個別 probe は製品 CLI と混同せず、利用者向け・開発用・テスト用の区分と既存一覧の方針に沿って対象を判断します。Release installer が CLI 引数を持たない場合は、オプションリンクを作らずその事実を記載します。ネットワーク上の Release 実体を確認できない場合は、ソースに基づく予想を実配布物として断定しないでください。
6. **一意な予定パスとコマンド概要を索引化する。** 各コマンド階層について `docs/cli/<tool-id>/<command-path>/README.md` の「コマンド概要」リンクを一つ置き、その節の先頭にします。root command は `root/` を使い、条件付きで parser や意味が分かれる場合は `001_investigation.md` の規約に沿って scope を分離します。各 option は `docs/cli/<tool-id>/<command-path>/<option-name>.md` にリンクします。同一 parser action の alias は正規名の一文書にまとめ、別の挙動・parser を同じリンクに押し込めません。リンク先ファイルが未作成でも、索引には予定リンクとして残します。
7. **節内の順序と網羅性を整える。** コマンド見出しの順番は維持し、各コマンド節では「コマンド概要」を先頭、その後のオプションを表示される正規名の ASCII コード順に並べます。全てのコマンド見出しに概要リンクが一つあること、コマンドごとの parser の全 option が漏れなく列挙されること、同じ tool-id / command path / option identity のリンクが重複しないことを確認します。
8. **根拠と索引の境界を更新する。** 冒頭の commit hash と調査日、ツール説明、対象境界、更新手順を今回実際に調べた checkout に合わせます。オプションの値や効果を個別文書に記載するのは別作業です。この索引更新だけを依頼された場合は、その文書を作成したことにせず、予定リンクとして列挙します。ソース変更、build、GPU 実行、性能測定、テストは依頼がない限り行いません。

### 次回の依頼文

次回以降は、次のように依頼してください（この節「更新手順と次回の調査指示」を指します）。

> Strata ソースコードが更新されたので、`/home/sasasin/src/github.com/sasasin/strata-envvars/docs/cli/README.md` の「更新手順と次回の調査指示」に従って、`/home/sasasin/src/github.com/Niko1221/Strata` を調査し、`docs/cli/README.md` を最新の内容に更新してください。全 CLI tool-id とコマンド階層、各 parser のオプションと alias、条件付き engine parser、CMake 生成の対象 CLI を確認してください。全コマンドに `README.md` の概要リンクを置き、各コマンド節では概要リンクを先頭、その後のオプションを ASCII コード順にしてください。オプション文書と概要ページが未作成の場合も、規約どおりの Markdown 予定リンクとして列挙し、現行 Release を確認できない内容は推測で補わないでください。

