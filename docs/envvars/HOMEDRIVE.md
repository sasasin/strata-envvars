# `HOMEDRIVE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 本体が `HOMEDRIVE` の内容を設定として解釈する実装は見つからなかった。一方、agent 用 Harness を起動するとき、ホスト側環境から agent に引き継ぐ名前の許可リスト `KEEP` に `HOMEDRIVE` が含まれる。`agentEnvironment` は元環境のエントリーを列挙し、許可リストに一致する名前と値を出力環境へコピーするため、環境に `HOMEDRIVE` が存在すれば値を変更せず子 Harness の環境へ渡す（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

この処理は Harness 起動時の環境転送であり、Strata のモデル計算や通常の CLI / server engine の設定を変えるものではない。転送された値を Harness やその子プロセスがどう使うかは Strata 所有ソースの調査範囲外である。

## 値と判定

`HOMEDRIVE` 専用の値パーサー、文字列比較、数値変換、既定値はない。`KEEP` は環境変数名に対し大文字小文字を区別しない正規表現で照合し、`agentEnvironment` は値が `undefined` の項目だけを除外する。したがって名前が許可リストに一致して値が定義されていれば、空文字も含め値をそのままコピーする。`C:` などの値形式・境界・妥当性の検査は Strata では行わない（`app/host/server/agent/harness-runtime.mjs:20-36`）。

| 条件 | 未設定 | コピーされる値の例 | Strata が値を解釈しない例 |
|---|---|---|---|
| agent Harness の起動時 | 元環境にキーがなければコピーされない | `C:`, `D:`, 空文字（値が定義されている場合） | `0`, `true`, 空白を含む文字列なども、定義されていれば文字列のままコピー |

`agentEnvironment` の最後に追加環境 `extra` を展開するため、呼び出し元が同名キーを `extra` に明示した場合はコピー済みの値を上書きできる。現行の `startRuntime` は profile 環境などを `extra` として渡す（`app/host/server/agent/harness-runtime.mjs:34-36,80-83`; `app/host/server/agent/agent-bridge.mjs:303-305`）。

## 有効になる条件

- agent Harness が `HarnessProcess.start()` で起動される必要がある。Strata server/CLI engine の一般的な起動経路について `HOMEDRIVE` 固有の読み取りは見つからなかった（`app/host/server/agent/harness-runtime.mjs:75-83`）。
- 引き継ぎ元環境に名前が許可リストと一致する `HOMEDRIVE` 項目として存在する必要がある。正規表現は大文字小文字を区別しない（`app/host/server/agent/harness-runtime.mjs:20-32`）。
- `externalEnvironment` は通常、現在の `process.env` をコピー元にする。AppImage 起動時は `STRATA_ORIGINAL_ENV` に記録された元環境があればそれを使い、記録がなければ AppImage 固有項目を除去した環境を使う（`app/host/server/external-env.mjs:28-40,43-57,60-71`; `app/host/server/agent/harness-runtime.mjs:28-32`）。
- `agentEnvironment` は `SECRET_NAME`（`KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH` を含む名前）に一致する名前を除外するが、`HOMEDRIVE` は一致しない（`app/host/server/agent/harness-runtime.mjs:20-32`）。
- 子 Harness が受け取った値を利用するかどうか、または追加の子プロセスへどう伝えるかは、この Strata 側実装では規定されない。

## 実行時の詳細

`agentEnvironment` は Harness の各起動時に `externalEnvironment(base)` のエントリーを走査し、環境オブジェクトを組み立てる。`HarnessProcess.start()` がその結果を `spawn` の `env` に渡すため、この値について Strata 内に静的キャッシュや独自の起動後再読込はない。稼働中プロセスの環境を読み直す処理も見つからなかった。新しい起動では、その起動時点で渡された `process.env` 等が再度列挙される（`app/host/server/agent/harness-runtime.mjs:25-36,75-83`; `app/host/server/external-env.mjs:64-71`）。

別用途として `tools/packaging/smoke_terminal.py` の `clean_env` は Windows 用の隔離環境辞書に `"HOMEDRIVE": "C:"` を固定値で入れる。この値は呼び出し元の `HOMEDRIVE` を読んだものではなく、packaging smoke 実行時の子コマンド環境を構成する値である（`tools/packaging/smoke_terminal.py:56-81,96-100`）。これは smoke ツール内の処理であり、Strata の実行時設定を示すものではない。

## ログと測定値

`HOMEDRIVE` の有無や値を理由に Strata が出す専用ログ、警告、終了・失敗経路は見つからなかった。Harness の起動失敗ログは一般的な Harness 起動結果を扱うもので、`HOMEDRIVE` を判定していない（`app/host/server/agent/harness-runtime.mjs:88-114`）。測定値は該当しない。

## 根拠

- `app/host/server/agent/harness-runtime.mjs:20-36` — 名前許可リスト、secret 名の除外、環境の列挙と値のコピー、追加環境による上書き。
- `app/host/server/agent/harness-runtime.mjs:75-83` — 組み立てた環境を Harness 子プロセスに渡す。
- `app/host/server/agent/agent-bridge.mjs:294-305` — agent runtime 起動時に `HarnessProcess` を生成し環境を渡す。
- `app/host/server/external-env.mjs:28-40,43-57,60-71` — 通常環境、AppImage 起動元環境、AppImage 変数除去後の環境を選ぶ処理。
- `tools/packaging/smoke_terminal.py:56-81,96-100` — Windows smoke 用の環境辞書に `HOMEDRIVE=C:` を固定してサブプロセスへ渡す処理。
