# `DSH_TELEMETRY_DISABLED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストプロセスや engine の動作を切り替える読み取り箇所は見つからない。Strata はエージェント用 Harness を起動するとき、子プロセスの環境に `DSH_TELEMETRY_DISABLED=1` を設定する。したがって本書で確認できるのは、この値を子プロセスへ渡す Strata 側の処理までであり、Harness がこの変数をどう解釈するか、何が無効になるかは対象外である。設定は `agentEnvironment` と `HarnessProcess.start` に実装されている（`app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

## 値と判定

Strata はこの変数を読み取って値を判定・変換するのではなく、`agentEnvironment` の返却オブジェクトに文字列 `'1'` を固定で加える。ホストの環境にこの変数が未設定、空文字、`0`、`false` などで存在しても、ホスト環境のコピー処理では `KEEP` の許可リストに含まれないため引き継がれず、通常の起動値は `'1'` になる。大文字小文字、空白、数値としての妥当性を Strata は検査しない（`app/host/server/agent/harness-runtime.mjs:20-36`）。

`extra` は固定値の後に展開されるため、関数の呼び出し元が同じ名前を渡した場合はその値が上書きする。ただし本番の呼び出しは `HarnessProcess.start` の一箇所で、`agent-bridge.mjs` が渡す `profile.env` と `STRATA_UPDATE_PAUSE_FILE`、さらに Harness の `DSH_HOME` を `extra` に含める。`profile.env` はモデル/API キーや `STRATA_MCP_*` など Strata が生成した値で構成され、`DSH_TELEMETRY_DISABLED` の上書き項目は作られないため、本番経路では固定値 `'1'` が渡る（`app/host/server/agent/agent-bridge.mjs:294-305`; `app/host/server/agent/profile.mjs:314-318,338-344,431-432,481-493`; `app/host/server/agent/harness-runtime.mjs:36,80-83`）。

| 条件 | ホスト側の値 | Strata が子 Harness に渡す値 |
|---|---|---|
| 本番のエージェント起動 | 未設定、空文字、`0`、`false` を含め問わない | `1` |
| `agentEnvironment(base, extra)` に同名の `extra` を渡す場合 | `base` 内の値は許可リストに残らない | `extra` の同名値で上書き |

## 有効になる条件

- `HarnessProcess.start` が呼ばれるエージェント起動経路で適用される。通常の Strata ホストや engine の環境値を変更する処理ではない（`app/host/server/agent/harness-runtime.mjs:75-83`）。
- Harness の実行ファイルが見つかり依存ファイルが揃っていることが起動条件である。見つからない場合、ブリッジは `AgentUnavailable` を投げるため子プロセス自体が起動せず、この変数も渡されない（`app/host/server/agent/harness-runtime.mjs:43-57`; `app/host/server/agent/agent-bridge.mjs:294-297`）。
- OS、GPU backend、ビルド macro、CLI 引数による Strata 側の分岐はない。Harness 起動引数は `--profile web` などで、CLI 引数によるこの値の切り替えはない（`app/host/server/agent/harness-runtime.mjs:75-83`）。

## 実行時の詳細

環境オブジェクトは Harness の各起動時に `agentEnvironment(process.env, ...)` として組み立てられ、`spawn` の `env` オプションで子プロセスに渡される。Strata 側にこの変数の static cache や再読み込み処理はなく、値は起動時に固定される。稼働中の子プロセスに対する後からの変更経路はない。Strata の通常の本番呼び出しでは固定値を上書きする引数も渡さない（`app/host/server/agent/harness-runtime.mjs:26-36,75-83`; `app/host/server/agent/agent-bridge.mjs:303-305`）。

## ログと測定値

この変数の値を記録・警告する Strata のログ、専用の終了・失敗経路、測定値は見つからない。起動失敗時には Harness の起動エラーが処理されるが、当該変数に起因すると Strata が判定する分岐はない（`app/host/server/agent/harness-runtime.mjs:94-114`）。

## 根拠

- `app/host/server/agent/harness-runtime.mjs:20-36` — ホスト環境の許可リスト処理と `DSH_TELEMETRY_DISABLED: '1'` の設定。
- `app/host/server/agent/harness-runtime.mjs:75-83` — 起動ごとに組み立てた環境を Harness の `spawn` に渡す。
- `app/host/server/agent/agent-bridge.mjs:294-305` — 本番の Harness 起動と、`profile.env` などの追加環境。
- `app/host/server/agent/profile.mjs:314-318,338-344,431-432,481-493` — 追加環境値の生成と返却。
- `app/host/server/agent/harness-runtime.mjs:43-57,94-114` — Harness の存在確認と起動失敗処理。
