# `DEMO_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

`DEMO_TOKEN` は Strata ホストが自プロセスの環境変数から読む設定ではない。モデルに設定された MCP サーバーの `env` オブジェクトにこのキーがあれば、Strata はその設定値をエージェント用プロセス環境に移し、MCP クライアント設定には生成環境変数から値を参照する形で登録する。たとえば先頭の有効なサーバーのキー `DEMO_TOKEN` は `STRATA_MCP_0_E_DEMO_TOKEN` という生成名になる（サーバーの順序・件数で番号は変わる）。通常のホスト環境に `DEMO_TOKEN` を設定するだけでは、この設定経路には入らない。[`app/host/server/agent/profile.mjs:93-96,108-114`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs)

## 値と判定

この名前に対する真偽値判定や数値変換はない。対象値は MCP 設定の `server.env` から取り出され、検証後に文字列として扱われる。未設定のホスト環境変数は参照されない。MCP の `env` にキーがない場合は対応する受け渡し項目が作られず、空文字列を設定した場合は空文字列の値がそのまま登録される。Settings から MCP サーバー設定を保存するときの `validateMcpServers` は env 値を文字列に限定し、16,000 文字超または NUL を含む値を拒否する。空白、大文字小文字、内容の形式について追加検査はない。[`app/host/server/native-settings.mjs:131-146`](../../../../Niko1221/Strata/app/host/server/native-settings.mjs) [`app/host/server/agent/profile.mjs:93-96,108-111`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs)

| 条件 | `DEMO_TOKEN` の扱い | 有効例 | 対象外・無効例 |
|---|---|---|---|
| モデル MCP 設定の stdio サーバーが有効 | `server.env` の値をエージェント環境へ加え、MCP 設定の `DEMO_TOKEN` に生成名を割り当てる | `env: { "DEMO_TOKEN": "abc" }` | ホスト側で `DEMO_TOKEN=abc` だけを設定 |
| MCP サーバー設定にこのキーがない | このキーの値は追加しない | — | `env` に `DEMO_TOKEN` がない |
| `server.env.DEMO_TOKEN` が空文字列 | 空文字列を渡す項目として扱う | `env: { "DEMO_TOKEN": "" }` | — |
| `server.env` の値が型・長さ・NUL 制約に違反 | MCP 設定の検証エラー | — | 数値など文字列以外、16,001 文字、NUL を含む文字列 |

## 有効になる条件

- 対象は Strata のエージェント機能で組み立てる MCP サーバー設定である。モデル既定インスタンスのサーバーと Tools 設定のサーバーが統合される。[`app/host/server/agent/profile.mjs:419-431`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs)
- サーバーが `disabled: true` なら行ごと除外され、環境値の参照も生成されない。無効なサーバー名、command と url の両方がない設定、重複する slug のサーバーも除外される。[`app/host/server/agent/profile.mjs:86-92`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs)
- `server.env` の項目を MCP 行へ含めるのは stdio の `command` がある場合である。URL 接続の行では `headers` が扱われ、`server.env` は行に含まれない。[`app/host/server/agent/profile.mjs:105-114`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs)
- この経路に OS / GPU backend / build macro 条件はない。対象の MCP 設定が有効な行としてプロファイルに入り、Strata がエージェント Harness を起動することが必要である。[`app/host/server/agent/profile.mjs:86-114,419-431`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs) [`app/host/server/agent/agent-bridge.mjs:295-312`](../../../../Niko1221/Strata/app/host/server/agent/agent-bridge.mjs)

## 実行時の詳細

`mcpRows` は有効な各サーバーの `env` エントリーごとに、キーを小文字化して slug 化し、英数字以外の連続部分をハイフンに置換した後、生成名のサフィックスで大文字化し、ハイフンをアンダースコアにする。値は `String(value)` で生成環境オブジェクトに追加され、MCP 設定には `@@JS:process.env.<生成名>@@` の参照が入る。従って `DEMO_TOKEN` という名前自体を Strata が `process.env.DEMO_TOKEN` として読むわけではない。[`app/host/server/agent/profile.mjs:93-96,108-111,137`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs)

生成された `profile.env` はプロファイル組み立て時に返され、Harness 起動用 `HarnessProcess` に渡る。起動時に `agentEnvironment` がホスト環境から KEY/TOKEN 等を含む名前を除外したうえで `extra` を結合するため、設定値は生成名で追加される。プロファイル YAML には credential の値ではなく名前への参照を置く。[`app/host/server/agent/profile.mjs:480-492`](../../../../Niko1221/Strata/app/host/server/agent/profile.mjs) [`app/host/server/agent/agent-bridge.mjs:301-305`](../../../../Niko1221/Strata/app/host/server/agent/agent-bridge.mjs) [`app/host/server/agent/harness-runtime.mjs:20-36,67-83`](../../../../Niko1221/Strata/app/host/server/agent/harness-runtime.mjs)

値の取り込みは MCP 設定からのプロファイル生成時で、ホストの `DEMO_TOKEN` を起動後に読み直す処理はない。生成値は起動する Harness の環境に渡される。Strata ソースだけからは MCP クライアントや外部 MCP サーバー内部での環境参照後の処理までは説明できない。

## 根拠

- `app/host/server/native-settings.mjs:131-146` — MCP サーバー設定の env 値の検証。
- `app/host/server/agent/profile.mjs:82-116,137,419-431,480-492` — MCP env キーの生成名への変換、プロファイル生成、モデルサーバーとの統合。
- `app/host/server/agent/agent-bridge.mjs:295-312` — 生成プロファイルと環境を Harness 起動に渡す箇所。
- `app/host/server/agent/harness-runtime.mjs:20-36,67-83` — agent 用環境のフィルタリングと Harness 子プロセス起動。
