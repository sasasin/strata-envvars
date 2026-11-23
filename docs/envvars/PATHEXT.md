# `PATHEXT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `PATHEXT` を設定値として解釈せず、コーディングアシスタントの Harness プロセスへ渡す環境変数の許可リストに含める。`agentEnvironment()` は通常のユーザー環境から許可した名前だけをコピーし、`HarnessProcess.start()` がその環境で Harness を起動する（`app/host/server/agent/harness-runtime.mjs:20-36,75-84`）。Strata のモデル選択、生成内容、コマンドの拡張子解決をこの値で変えるコードはない。

## 値と判定

Strata は値を parse・比較・変換しない。`externalEnvironment(base)` の結果を列挙し、名前が大文字小文字を区別しない `KEEP` 正規表現に一致し、値が `undefined` でなく、秘密情報名フィルターにも一致しない場合、元の名前と値をそのまま出力環境へコピーする。`PATHEXT` は秘密情報名フィルターに一致しない（`app/host/server/agent/harness-runtime.mjs:20-33`）。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Harness の環境を作る場合 | `base` にキーがなければ出力にもない | `PATHEXT=.EXE;.CMD`、空文字列を含め、キーが存在すれば値をそのまま転送 | 値による無効判定なし。`0`、`false`、空白、その他の文字列も拒否・変換されない。名前は `PATHEXT` / `pathext` など大文字小文字を区別せず一致し、コピー時のキー表記は維持される |

`externalEnvironment()` が環境の元を選ぶ条件も転送結果に影響する。AppImage 外で記録がなければ現在の環境を使う。AppImage では `STRATA_ORIGINAL_ENV` の記録を復元し、記録がない・復元できない場合は AppImage 用の項目を除去した現在の環境を使う。後者の除去対象に `PATHEXT` は含まれない（`app/host/server/external-env.mjs:15-26,28-40,43-57,60-70`）。

## 有効になる条件

- Harness がインストール済みで、Strata がアシスタント用 Harness を起動する経路であること。Harness の場所が解決できない場合は起動前に利用不可となり、環境転送は行われない（`app/host/server/agent/harness-runtime.mjs:40-57`; 呼び出し元 `app/host/server/agent/agent-bridge.mjs:294-311`）。
- `agentEnvironment()` 自体に OS 判定はない。`PATHEXT` が親環境（AppImage の場合は上記の選択・復元後の環境）に存在すること（`app/host/server/agent/harness-runtime.mjs:23-33`; `app/host/server/external-env.mjs:67-70`）。
- `HarnessProcess.start()` が呼ばれた時点の環境が子プロセス用に作られる。設定値の妥当性や空文字かどうかは起動条件ではない（`app/host/server/agent/harness-runtime.mjs:75-84`）。

## 実行時の詳細

`agentEnvironment(base, extra)` は呼び出しごとに `externalEnvironment(base)` を列挙し、許可された環境項目を新しいオブジェクトへコピーする。関数内に `PATHEXT` 用のキャッシュはない。Harness 起動時には `agentEnvironment(process.env, { ...this.extraEnv, DSH_HOME: this.home })` の結果を `spawn()` に渡すため、起動後の親プロセス環境の変更は既に起動した子の環境を変更しない（`app/host/server/agent/harness-runtime.mjs:25-36,75-84`）。

起動元の `agent-bridge.mjs` は追加環境としてプロファイル環境と `STRATA_UPDATE_PAUSE_FILE` を渡す（`app/host/server/agent/agent-bridge.mjs:303-311`）。プロファイルが追加する MCP 用の秘密値は `STRATA_MCP_...` 名で格納されるため、通常のこの経路は `PATHEXT` を別値で上書きしない（`app/host/server/agent/profile.mjs:93-96,431-444`）。`agentEnvironment()` の `...extra` はコピー済み環境より後に展開されるため、関数の呼び出し元が明示的に `extra.PATHEXT` を渡せばその値が上書きするが、Harness 起動元の上記追加値にはそのキーがない（`app/host/server/agent/harness-runtime.mjs:36`; `app/host/server/agent/agent-bridge.mjs:303-304`）。

## ログと測定値

`PATHEXT` の有無や値に応じたログ、警告、終了、失敗分岐はない。Harness の起動時にアドレスが出ない・プロセスが先に終了する場合はエラーになる実装だが、`PATHEXT` による判定ではない（`app/host/server/agent/harness-runtime.mjs:94-115`）。関連する Strata の測定値はない。

## 根拠

- `app/host/server/agent/harness-runtime.mjs:20-36` — 許可名、秘密名の除外、環境値コピー。
- `app/host/server/agent/harness-runtime.mjs:75-84` — Harness 起動時の環境作成と子プロセスへの受け渡し。
- `app/host/server/external-env.mjs:15-26,28-40,43-57,60-70` — AppImage 時を含む元環境の選択と調整。
- `app/host/server/agent/agent-bridge.mjs:294-311` — Harness 起動経路と追加環境。
- `app/host/server/agent/profile.mjs:93-96,431-444` — プロファイルが追加する環境変数名。
- `tools/packaging/smoke_terminal.py:56-81` — Windows 用のパッケージ smoke 環境でテストスクリプトが `PATHEXT` を設定する箇所。これはテスト用環境の構築であり、Strata 本体による値の解釈ではない。
