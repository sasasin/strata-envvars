# `STRATA_SEARCH_KEY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Settings → Tools → Web search で保存した検索サービス用キーを、エージェント（Harness）プロセスへ渡すための環境変数です。ホストが任意の親プロセス環境から値を読む設定ではなく、保存済みの検索設定から `profile.env` に値を設定し、Harness 起動時に子プロセス環境へ明示的に渡します。キー値は Harness の profile patch には含めず、patch には環境変数名だけを設定します（`apps/host/server/agent/profile.mjs:304-311,338-344`、`apps/host/server/agent/agent-bridge.mjs:218-223`）。

## 値と判定

この環境変数を Strata が数値や真偽値として parse する箇所はありません。通常の設定経路では、`tools-settings.mjs` が保存値を文字列として取り込み、`profile.mjs` が設定済みサービスと空でないキーの組み合わせに限り、その文字列をそのまま `profile.env.STRATA_SEARCH_KEY` に代入します（`apps/host/server/agent/tools-settings.mjs:29-35,167-177`、`apps/host/server/agent/profile.mjs:304-311`）。

| 検索設定 | `profile.env` への設定 | Harness に渡す検索設定 |
|---|---|---|
| 検索ツールが OFF | 設定しない | 検索行を作らない |
| provider が `builtin`、または provider がキー対応でもキーが空 | 設定しない | DuckDuckGo を選ぶ（DeepSeek 行は無効） |
| provider が `exa` / `perplexity` / `deepseek` かつキーが空でない | 保存されたキーを設定 | 選択したサービスに対応する行を設定し、`STRATA_SEARCH_KEY` を参照させる |

`STRATA_SEARCH_KEY` が設定されない経路では、Harness 子プロセス環境の元になるホスト環境からも ambient credential は除かれます。`agentEnvironment()` は `KEY` を含む名前を `SECRET_NAME` として通常の継承対象から除外し、`profile.env` など `extra` の明示分だけを後から追加します（`apps/host/server/agent/harness-runtime.mjs:20-36,76-83`）。したがって、親環境に同名変数だけを設定しても、この経路で Harness に渡るとは限りません。

Settings API で新しく保存するキーは、前後の空白を trim した後、空文字、500 文字超、空白文字または NUL を含む値を拒否します。サービス変更時は以前のサービスに属するキーを空にします（`apps/host/server/agent/tools-settings.mjs:167-177`）。これは設定保存時の検証であり、環境変数値自体を受け取る parser の規則ではありません。既存設定の読み込みでは文字列型かどうかのみを確認し、保存時と同じ再検証はしません（同 `:29-35`）。

## 有効になる条件

- `search` ツールグループが OFF でないこと（`apps/host/server/agent/profile.mjs:304-311,330-331`）。
- `tools.search.provider` が `exa`、`perplexity`、`deepseek` のいずれかで、保存キーが空でないこと。provider の許容値は `builtin` を含む4種類です（`apps/host/server/agent/tools-settings.mjs:18,29-35`）。
- 実際の Harness 起動が必要です。API の選択やキーの設定だけでは環境変数を使う子プロセスは起動しません（`apps/host/server/agent/agent-bridge.mjs:212-229,250-274`）。

`exa` と `perplexity` では Strata の `strata-search.mjs` が `config.keyEnv` で示された名前から `process.env` を読み、キー付き provider を登録します（`apps/host/server/agent/plugins/strata-search.mjs:16-24`）。`deepseek` では Strata は Harness の `web-search-deepseek` 設定に `apiKeyEnv: 'STRATA_SEARCH_KEY'` を渡すところまでを行います（`apps/host/server/agent/profile.mjs:308-310`）。Harness 側の読み取りや通信動作はこの調査の対象外です。

## 実行時の詳細

`agent-bridge.mjs` はプロフィールを作り直して設定を確認し、Harness 起動時に `profile.env` を `HarnessProcess` に渡します。`HarnessProcess.start()` はそれを `agentEnvironment(process.env, { ...this.extraEnv, DSH_HOME: ... })` に合成して子プロセスを起動します（`apps/host/server/agent/agent-bridge.mjs:180-185,218-223`、`apps/host/server/agent/harness-runtime.mjs:67-83`）。このため、ホスト側の保存設定を変えただけで実行中プロセスの環境が書き換わるわけではありません。

プロフィールは次の要求時にも再生成されます。キー値は `toolsSignature` の入力に含まれ、変更が検出されると、進行中の turn が終わるまで待って Harness を止め、新しいプロフィールと環境で起動します（`apps/host/server/agent/profile.mjs:342-348`、`apps/host/server/agent/agent-bridge.mjs:250-274`）。Exa / Perplexity 用プラグインの `keyOf()` はサービス呼び出し時に `process.env[config.keyEnv] ?? ''` を評価するため、子プロセス内では固定された環境値を参照します（`apps/host/server/agent/plugins/strata-search.mjs:16-24`）。

不正なキーを送った場合、Strata 実装の Exa / Perplexity 呼び出しは HTTP 401/403 を「`<service> did not accept the key. Check it in Settings, Tools.`」という `SearchUnavailable` にします。通信失敗、429、その他の HTTP エラーもそれぞれ `WEB_PROVIDER_ERROR` / `WEB_RATE_LIMITED` 等へ変換します（`apps/host/server/web-search-keyed.mjs:10-25`）。DeepSeek のキー拒否時の具体的な表示・失敗動作は Harness 側なので、ここでは断定しません。

## 根拠

- 全参照検索: `STRATA_SEARCH_KEY` は Strata 所有ソースでは `apps/host/server/agent/profile.mjs:307,309,311,347` に現れ、動的な読み取りは `apps/host/server/agent/plugins/strata-search.mjs:17` の `process.env[config.keyEnv]` です。ほかの一致は README とテストにあり、候補名の参照を含めて確認しました。
- 設定の検証・保存値の公開範囲: `apps/host/server/agent/tools-settings.mjs:29-45,116-157,167-189`。
- キーの設定条件・profile patch との分離・変更署名: `apps/host/server/agent/profile.mjs:304-311,338-348`。
- 子プロセス環境のフィルタと明示的な追加: `apps/host/server/agent/harness-runtime.mjs:20-36,76-83`。
- 認証失敗などの Strata 側エラー変換: `apps/host/server/web-search-keyed.mjs:10-25`。
