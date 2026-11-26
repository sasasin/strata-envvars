# `STRATA_SEARCH_KEY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ホストアプリの Web 検索設定に保存された Exa / Perplexity / DeepSeek の API key を、coding assistant の Harness プロセスへ渡すための環境変数名である。環境変数そのものを設定する利用者向け CLI オプションではなく、Settings → Tools に保存された検索サービスと key から Strata が値を設定する。検索グループが無効、サービスが builtin、または key が空なら Strata はこの名前を agent 用環境に追加しない。profile には key の値ではなく環境変数名だけを含める（`app/host/server/agent/profile.mjs:440-447,480-485`）。

## 値と判定

Strata はこの名前を `getenv` で読むのではない。`buildProfile` が設定オブジェクト `tools.search.key` を判定し、条件を満たすと `env.STRATA_SEARCH_KEY` に代入する。保存設定の正規化では provider を `builtin` / `exa` / `perplexity` / `deepseek` のいずれかに限定し、key は文字列以外なら空文字にする。Settings 更新経由で key を登録すると前後空白を除去し、空文字、501 文字以上、空白または NUL を含む値を拒否する。一方、key のサービス側での有効性や文字種は Strata では検証しない（`app/host/server/agent/tools-settings.mjs:19,30-36,183-193`）。

| 条件 | unset / 空文字 | 値が設定される条件 | 無効・非該当の例 |
|---|---|---|---|
| 検索グループが有効 | provider が `builtin`、または key が空なら環境変数を追加しない。builtin の検索設定を使う | provider が `exa` / `perplexity` / `deepseek` のいずれかで、key が空でない文字列なら、その文字列を設定 | 未設定・`""` は false 扱い。provider が未知なら正規化で `builtin` となる |
| 検索グループが無効 | 値を追加せず、Web 検索用 profile entry も作らない | なし | 保存 key があっても `tools.off` に `search` があれば使わない |
| 通常の Settings 更新で保存する key | 空文字は拒否され、保存値を消す値としても受け付けない | 前後空白を除いた 1〜500 文字で、空白文字と NUL を含まない文字列 | 空白だけ、空白入り、NUL 入り、501 文字以上は拒否。`true` / `false` / `0` に特別な意味はなく、文字列としての key |

`buildProfile` の有効判定は文字列全体の parse や `1` 比較ではなく、許可された provider かつ `tools.search.key` の truthiness である。従って通常の保存経路では空 key は設定されず、任意の非空文字列は形式検証なしに設定される。設定ファイルに手で空白だけの文字列を置いた場合は正規化で trim されないため truthy として扱われるが、Settings 更新経由ではその値は保存できない（`app/host/server/agent/tools-settings.mjs:30-36,183-193`; `app/host/server/agent/profile.mjs:440-447`）。

## 有効になる条件

- agent bridge が利用可能で、Harness runtime を起動すること。Strata は profile を組み立て、Harness の子プロセス起動時に `profile.env` を追加環境として渡す（`app/host/server/agent/agent-bridge.mjs:295-312`; `app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。
- Settings → Tools で Search the web が有効であること。無効なら検索 provider の entry 自体を作らない（`app/host/server/agent/profile.mjs:440-447`）。
- 有料検索 provider の場合は `exa` / `perplexity` / `deepseek` のいずれかを選び、その provider に属する非空 key を保存していること。provider を変更すると既存 key を空に戻す（`app/host/server/agent/tools-settings.mjs:183-192`）。
- Exa / Perplexity は Strata の `strata-web-search` plugin を登録する経路である。plugin は設定名 `config.keyEnv` を通じて `process.env[config.keyEnv]` を検索時に参照する。DuckDuckGo 経路には key は使われない（`app/host/server/agent/profile.mjs:444-447`; `app/host/server/agent/plugins/strata-search.mjs:16-24`）。
- DeepSeek を選んだ場合、Strata は Harness の `web-search-deepseek` entry に `apiKeyEnv: 'STRATA_SEARCH_KEY'` を渡す。Harness provider 内での読み取りや通信の細部は Strata 所有コードではないため、ここでは断定しない（`app/host/server/agent/profile.mjs:444-445`）。
- OS、GPU backend、モデル種別、CLI 引数による分岐はこの値設定箇所にはない。環境変数名に `KEY` が含まれるため、親プロセスからの値は agent の通常環境を作る際に秘密情報として除外される。Strata が profile に明示した値だけが追加環境として子プロセスに渡る（`app/host/server/agent/harness-runtime.mjs:20-36,80-83`）。

## 実行時の詳細

`buildProfileNow` は Settings を読み直して profile を作る。条件が成立すると `profile.env` に key を入れ、Harness 起動時に `agentEnvironment` の `extra` として渡す。このため値は起動する Harness プロセスの環境に固定される。Exa / Perplexity 用 plugin の `keyOf` は `apply` 時ではなく provider が key を求めるたびに `process.env[config.keyEnv] ?? ''` を評価するが、実行中の親 Strata の設定変更で既存 child process の環境値は書き換わらない（`app/host/server/agent/agent-bridge.mjs:251-263,295-312,334-355`; `app/host/server/agent/harness-runtime.mjs:25-36,75-83`; `app/host/server/agent/plugins/strata-search.mjs:16-23`）。

key は profile patch へ書かず、agent が利用できる環境変数として分離する。値そのものは profile の署名に含まれ、Web 検索設定の signature にも含まれるため、key の変更は次の message で runtime が既存値と異なると判定される。既存 runtime が動作中なら idle になるのを待って停止し、新しい profile で起動する。key は画面へは渡さず、画面側に返るのは `keySet` の真偽値だけである。起動ログ保存時や失敗情報では追加環境の値を redact する（`app/host/server/agent/profile.mjs:480-491`; `app/host/server/agent/tools-settings.mjs:124-130,145-163`; `app/host/server/agent/agent-bridge.mjs:347-364`; `app/host/server/agent/harness-runtime.mjs:88-112`）。

この変数自体の値に対する CLI 引数や別の環境変数による優先順位はない。検索 service の選択は Settings の provider による。key が空、または provider が `builtin` なら `keyed` は null となり、検索グループが有効な場合は Strata が DuckDuckGo provider を profile に指定する（`app/host/server/agent/profile.mjs:440-447`）。

## ログと測定値

Strata は key の設定・未設定を示す専用ログを出さない。Exa / Perplexity の検索要求で Strata の `web-search-keyed.mjs` が 401 または 403 を受けると `SearchUnavailable` に `"<service> did not accept the key. Check it in Settings, Tools."` を設定する。429 は `"<service> says there have been too many searches. Try again in a minute."`、通信失敗は `"The search could not reach <service>. Check the internet connection and try again."` とする（`app/host/server/web-search-keyed.mjs:10-25`）。これらは検索処理のエラーであり、この環境変数を設定しただけで出る起動ログではない。DeepSeek provider 側の失敗表示は Strata 所有コードから確認できない。

## 根拠

- 設定値の正規化、画面向けの `keySet`、更新時の validation: `app/host/server/agent/tools-settings.mjs:19-36,124-130,145-163,183-193`
- provider と key の判定、profile entry、signature: `app/host/server/agent/profile.mjs:440-447,480-492`
- Settings 読み直し、profile 生成、runtime 更新: `app/host/server/agent/agent-bridge.mjs:251-263,295-312,334-364`
- 親環境の秘密値除外と Harness への追加環境の引き渡し: `app/host/server/agent/harness-runtime.mjs:20-36,75-112`
- 動的環境名参照と Exa / Perplexity plugin の登録: `app/host/server/agent/plugins/strata-search.mjs:13-24`
- Exa / Perplexity の key 使用と Strata 側のエラー処理: `app/host/server/web-search-keyed.mjs:10-25,28-64`
