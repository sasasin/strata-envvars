# `DSH_HOME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部 Harness の環境変数の解釈・保存動作は対象外。

## 役割

Strata の App Host が起動する Harness 子プロセスに、Harness 用ホームディレクトリを `DSH_HOME` として渡します。Strata 側でこの値を使って設定やセッションを読み込むのではなく、Strata が用意したパスを子プロセスの環境へ設定する処理です。

## 値と判定

Strata は起動元プロセスの `DSH_HOME` を採用しません。agent 用の環境を作る際、親環境から継承する変数は `KEEP` の allowlist に含まれる名前だけであり、`DSH_HOME` は含まれません。その後、子プロセス向けの追加環境に `DSH_HOME: this.home` を最後に指定します。このため、親側の値が未設定、空文字、任意の文字列のいずれでも、Strata が子へ渡す値は `this.home` です。また `this.extraEnv` に同名の値があっても `this.home` で上書きされます。

`this.home` は `createAgentBridge` の `dataDir` から作られる `join(dataDir, 'agent', 'home')` です。Strata はこの値を数値や真偽値に変換せず、環境変数名として子へ設定します。コード上、このパスに対する `DSH_HOME` 固有の空文字・相対パス・境界値検証や fallback はありません。

## 有効になる条件

この設定は App Host の agent bridge が Harness を起動する経路で使われます。モデル route が選ばれ、agent runtime が必要になったとき `HarnessProcess` を作成し、Harness の Node 子プロセスを起動します。コマンドラインには `--profile web`、`--patch`、`--port 0`、`--no-open` を渡し、`DSH_HOME` は別途子プロセス環境に設定します。これらの CLI 引数による `DSH_HOME` の代替や優先順位は Strata コードにはありません。

## 実行時の詳細

`createAgentBridge` は agent の状態領域を `join(dataDir, 'agent')` とし、Harness 用ホームをその下の `home` に定めます。runtime 起動時にはホームディレクトリと作業ディレクトリを再帰作成し、`HarnessProcess.start()` も spawn の直前に `this.home` を再帰作成します。続いて `agentEnvironment(process.env, { ...this.extraEnv, DSH_HOME: this.home })` が構成した環境を Node 子プロセスに渡します。`agentEnvironment` は `externalEnvironment(base)` を通した値のうち allowlist に入るものだけをコピーし、固定の Harness 用値を追加してから `extra` を展開するため、最後の `DSH_HOME` が子の値になります。

Strata のこの経路で `DSH_HOME` を読み直したり static cache したりする箇所はありません。値は `HarnessProcess` 作成時に持つ `home` で決まり、起動ごとに子環境へ設定されます。Strata は外部 Harness がその値をどう解釈するか、どのファイルをそこへ保存するかをこのコードで制御・検証しません。

ホーム／作業ディレクトリ作成や子プロセス起動が失敗した場合は、通常の agent 起動失敗になります。起動中に子が終了すると `the agent exited during start (code ...)`、所定時間内にアドレスを出さない場合は `the agent did not print its address within ...s` のエラー経路になります。成功時は Strata のログに Harness の version、PID、route 数が出ます。`DSH_HOME` の実値を Strata がログ出力する箇所は確認できません。

## 根拠

- `apps/host/server/agent/agent-bridge.mjs:120-124` — agent の状態 root と `home` の組み立て。
- `apps/host/server/agent/agent-bridge.mjs:205-223` — runtime 起動時の directory 作成、`HarnessProcess` 生成と起動。
- `apps/host/server/agent/harness-runtime.mjs:20-36` — 継承環境の allowlist と `extra` の適用順。
- `apps/host/server/agent/harness-runtime.mjs:60-69,75-104` — `home` の保持、再帰作成、CLI 引数、子プロセスへの `DSH_HOME` 設定、起動失敗経路。
- `apps/host/server/agent/agent-bridge.mjs:216-232` — 子プロセス終了・Harness 起動成功時の Strata ログ。

`DSH_HOME` の他の参照では、`integrations/harness/` の bridge / e2e 用スクリプトが検証用に環境から値を読み、または設定します。これらはテスト・受け入れ確認用コードであり、通常の Strata 実行時の環境変数読み取りとは扱っていません。`packaging/acceptance_matrix.py` と `docs/work/ACCEPTANCE-EVIDENCE.md` の記述は受け入れ資料です。`docs/DETAILS.md` にこの変数の Strata 動作説明は見つかりませんでした。
