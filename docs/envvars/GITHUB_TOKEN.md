# `GITHUB_TOKEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の設定値として `GITHUB_TOKEN` を読み取る実装はありません。確認できた Strata の実行時の関係は、web profile の Harness 子プロセスへホスト環境を渡す際に、一般的な allowlist でこの名前を含む ambient credential を除外することです。テストは `GITHUB_TOKEN` を除外対象の例として明示しています。

## 値と判定

値の内容、空文字、数値形式は判定されません。`agentEnvironment()` はホスト環境の各エントリーを走査し、名前が `KEEP` allowlist に合わないものを子環境へ代入する前に除外します。`GITHUB_TOKEN` は allowlist にないため、ホスト環境に未設定・空・非空のどの値であっても、ambient 値としては Harness の子プロセス環境へ渡りません。テストでは非空の値を与え、返却環境に名前が含まれないことを確認しています。

この一般 helper はフィルター後に `extra` を追加し、同名キーがあればその値で上書きします。Harness 起動元は `extra` に `profile.env` と `DSH_HOME` を渡します。従って呼び出し元が `extra` に明示的に `GITHUB_TOKEN` を含めた場合は渡り得ますが、調査した `buildProfile()` は `STRATA_LOCAL_KEY_*` と `STRATA_MCP_*` のような生成名を `env` に作り、`GITHUB_TOKEN` という名前は作りません（`apps/host/server/agent/harness-runtime.mjs:25-36,67-83`; `apps/host/server/agent/agent-bridge.mjs:214-215`; `apps/host/server/agent/profile.mjs:196-200,220-225,88-96`）。

## 有効になる条件

除外は web profile の Harness 子プロセスを作る経路で適用されます。`HarnessProcess.start()` は `spawn()` の `env` に `agentEnvironment(process.env, { ...this.extraEnv, DSH_HOME: this.home })` を指定します。AppImage 起動時は `externalEnvironment()` が記録済みの起動元環境（または AppImage 固有値を除いた環境）を返し、それ以外では `process.env` のコピーを返します。その結果に対して `agentEnvironment()` の allowlist が適用されます（`apps/host/server/agent/harness-runtime.mjs:20-36,76-83`; `apps/host/server/external-env.mjs:28-40,43-70`）。

## 実行時の詳細

環境は `HarnessProcess.start()` 時に組み立てられます。ホストの `GITHUB_TOKEN` がこの時点で存在しても Harness 子プロセスには継承されません。Strata はその値を parse、cache、ログ出力せず、未設定時の代替値や CLI との優先順位も設けていません。明示 `extra` による上書きだけが一般 helper の例外です。

リポジトリ内での候補名の他の出現は GitHub Actions の workflow 設定・コメント・文書、またはこの除外動作を試すテストです。たとえば `.github/workflows/docker-images.yml:94-96` は GitHub Actions の `${{ secrets.GITHUB_TOKEN }}` を `REGISTRY_TOKEN` に割り当てて `docker login` に渡します。これは Strata アプリケーションが環境変数 `GITHUB_TOKEN` を読む箇所ではありません。`docs/envvars/000_envvers.md` の候補掲載は、このリポジトリ内に名前の参照があることを示しますが、Strata の設定用環境変数であることは示しません。

## 根拠

- `apps/host/server/agent/harness-runtime.mjs:20-36`: 環境変数名 allowlist、環境の走査、`extra` の後置マージ。
- `apps/host/server/agent/harness-runtime.mjs:76-83`: Harness 子プロセス起動時の環境構築。
- `apps/host/server/agent/agent-bridge.mjs:214-215`: 呼び出し元が `profile.env` を追加環境として渡す。
- `apps/host/server/agent/profile.mjs:88-96,196-200,220-225`: profile の追加環境名の生成。
- `apps/host/tests/agent-events.test.mjs:61-64`: `GITHUB_TOKEN` を入力し、子プロセス用環境から落ちることを検証。
- `.github/workflows/docker-images.yml:91-96`: Actions secret を `REGISTRY_TOKEN` として使う workflow。
