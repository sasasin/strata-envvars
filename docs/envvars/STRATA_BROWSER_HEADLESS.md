# `STRATA_BROWSER_HEADLESS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata のデスクトップ Host が Harness 用プロファイルにブラウザー MCP サーバーを登録するとき、値が文字列 `1` なら、そのサーバーの起動引数に `--headless` を追加します。Strata が行うのは引数の組み立てとプロファイルへの登録です。ブラウザー設定で有効になっており、利用可能なブラウザーと MCP CLI の両方がある場合に限り登録されます（`apps/host/server/agent/profile.mjs:300-303`）。

## 値と判定

| 環境変数の値 | Strata が生成するブラウザー MCP 引数 |
|---|---|
| unset、空文字、`0`、`true`、`01` など、文字列 `1` と完全一致しない値 | `--headless` を追加しない |
| `1` | `--headless` を追加する |

数値や真偽値への変換はせず、Node.js の `process.env.STRATA_BROWSER_HEADLESS === '1'` で比較します。大文字小文字、空白、前後の文字も含めて完全一致が必要です。CLI 引数や他の環境変数による優先順位・上書き処理はこの実装にありません（`apps/host/server/agent/profile.mjs:301-302`）。

## 有効になる条件

- Strata デスクトップ Host のエージェント Harness プロファイル生成経路で評価されます。Strata の推論エンジン（CUDA/HIP/SYCL）や OS ごとの分岐はありません（`apps/host/server/agent/profile.mjs:196, 300-303`）。
- `tools.browserEnabled` が真で、`tools.browserPath` と `tools.browserCli` が存在するときだけブラウザー MCP 設定が作られます。どれかが満たされなければ、この環境変数はプロファイル上の引数に反映されません（同 `:301-303`）。
- 値が `1` でも、Strata がブラウザーを直接起動したり別のブラウザー設定を変更したりするわけではありません。生成される設定は Node 実行ファイルを command とし、Playwright MCP CLI に `--browser chromium --isolated`、条件付きの `--headless`、`--executable-path <browserPath>` を渡します（同 `:302`）。CLI 側の `--headless` の解釈やブラウザー内部の動作はこの調査の対象外です。

## 実行時の詳細

環境変数は `buildProfile()` がブラウザー MCP の引数配列を組み立てる時点で読みます。エージェント Bridge は状態表示用のプロファイル生成時と、実行環境を確保する各回に `buildProfileNow()` を呼びます（`apps/host/server/agent/agent-bridge.mjs:173-179, 186-200, 243-248`）。したがって、この値自体を Strata が長期キャッシュする静的変数はありません。ただし、稼働中の Harness は再利用され、ブラウザー行を含む `toolsSignature` が変わった場合に、次の実行環境確保時に既存の実行環境をアイドルまで待って停止し、新しいプロファイルで起動します（`apps/host/server/agent/profile.mjs:342-348`; `apps/host/server/agent/agent-bridge.mjs:254-267`）。プロセス起動後に環境値を変更した場合、その時点の Harness や既に起動済みのブラウザー MCP サーバーへ遡って引数が適用されるわけではありません。

Harness の起動には生成済みプロファイルがファイルとして渡されます。Harness 子プロセスの環境は Strata によるフィルター済み環境です（`apps/host/server/agent/agent-bridge.mjs:205-222`; `apps/host/server/agent/harness-runtime.mjs:25-36, 75-83`）。この変数はそのフィルターの許可リストにはなく、値を Harness に環境変数として転送する実装もありません。Strata が渡すのはプロファイル内の MCP 引数です。

## 観測できる結果

Strata 側で確認できる効果は、生成プロファイルのブラウザー MCP 引数に `--headless` が含まれるかどうかです。この分岐に固有のログ、警告、エラー、終了処理はありません（`apps/host/server/agent/profile.mjs:300-303`）。Harness 自体の起動失敗時には一般的なエージェント起動エラー処理がありますが、この環境変数の値を検証したり、値に応じた診断を出したりするものではありません（`apps/host/server/agent/agent-bridge.mjs:256-265`）。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:629`。
- 候補名の全参照検索では、Host 実装 `apps/host/server/agent/profile.mjs:302` に環境値の読み取りが一か所ありました。`apps/host/scripts/agent2-tools-flow.mjs:6` はコメント、`apps/host/tests/agent-tools-settings.test.mjs:385-387` はテスト用設定であり、本番の読み取り根拠にはしていません。
- ブラウザー行の条件と引数生成: `apps/host/server/agent/profile.mjs:300-303`。
- プロファイル生成・再利用判定: `apps/host/server/agent/agent-bridge.mjs:173-179, 243-267`; `apps/host/server/agent/profile.mjs:342-348`。
- Harness 起動と子プロセス環境: `apps/host/server/agent/agent-bridge.mjs:205-222`; `apps/host/server/agent/harness-runtime.mjs:25-36, 75-83`。
