# `COMSPEC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata は `COMSPEC` の値を解釈してコマンドを実行する設定としては使いません。DeepSeek Harness（Strata の agent 機能）を子プロセスとして起動するとき、環境変数名 `COMSPEC` を通常環境の allowlist に含め、環境値を Harness に引き渡します。Harness の shell tool が通常のユーザー環境を受け取れるようにするための転送です。

## 値と判定

| 入力環境の状態 | Strata の処理 |
|---|---|
| `COMSPEC` が存在しない | `KEEP` の判定対象になる値がないため、通常は子環境に追加されない。 |
| 空文字 | 値の真偽や内容を検査せず列挙された値をコピーするため、空文字のまま転送される。 |
| 任意の非空文字列 | 文字列比較、数値変換、パス検証をせず、その値のまま転送する。 |

環境名の allowlist 判定は正規表現末尾の `i` により大文字小文字を区別しません。値は `SECRET_NAME` の名前判定にも一致しないため、secret 名として除外されません。Strata 側に `COMSPEC` 専用の既定値や CLI 引数との優先順位はありません。agent 起動時の基礎環境にある値をコピーし、プロファイル由来の `extra` が同名キーを含む場合は `extra` が上書きします。ただし現行の `buildProfile()` が生成する `env` は Strata/MCP 用の名前付き値であり、`COMSPEC` を生成する処理はありません。

## 有効になる条件

- `COMSPEC` の転送処理は `HarnessProcess.start()` が Harness 子プロセスを起動する経路で使われます。Strata の通常の engine 起動や CLI 共通設定としては参照されません。
- `agentEnvironment()` は `externalEnvironment()` の結果から値を選びます。AppImage 外では現在の Strata プロセス環境をコピーします。AppImage の起動環境記録 `STRATA_ORIGINAL_ENV` があれば記録された元環境を使い、記録がない AppImage 起動では AppImage 専用値や AppImage 内を指す値を除いた環境を使います。これらの処理は `COMSPEC` を特別扱いしません。
- 実行 OS による `COMSPEC` 固有の分岐はありません。Windows の smoke script にも参照がありますが、これは packaging 検証用コードであり、アプリの実行時設定ではありません。

## 実行時の詳細

agent の起動ごとに `HarnessProcess.start()` が `agentEnvironment(process.env, ...)` を呼び、そこから作ったオブジェクトを Node の `spawn()` の `env` に渡します。したがって Strata サーバーの起動後にプロセス環境が変わった場合でも、次回の agent 起動時に参照される値はその時点の `process.env`（AppImage では `externalEnvironment()` が選ぶ環境）です。起動済み Harness の環境は子プロセス起動時に渡されたスナップショットであり、後の環境変更は遡って反映されません。

Strata は `COMSPEC` の内容に応じたログ、警告、終了コード、fallback を実装していません。Harness が `COMSPEC` をどう使うかは外部コンポーネント側の動作なので、ここでは扱いません。Harness の起動自体は `spawn()` の error、起動 timeout、または子プロセスの exit により失敗として通知されますが、Strata コード上でそれらを `COMSPEC` に結び付ける判定はありません。

## 根拠

- `apps/host/server/agent/harness-runtime.mjs:20-36` — `COMSPEC` を含む allowlist、名前の大文字小文字を無視する判定、環境値のコピー、および追加環境との合成。
- `apps/host/server/agent/harness-runtime.mjs:76-104` — 起動時の環境作成、`spawn()` への引き渡し、起動失敗経路。
- `apps/host/server/external-env.mjs:28-40,43-57,60-71` — AppImage の記録環境の復元と、記録がない場合の環境整理。`COMSPEC` 固有の除外はない。
- `apps/host/server/agent/agent-bridge.mjs:205-222` — Harness runtime の生成と起動箇所。
- `apps/host/server/agent/profile.mjs:88-96,196-200,294-298,348` — プロファイル環境は生成した変数値を保持し、`buildProfile()` が返す。`COMSPEC` の生成はない。
- `packaging/smoke_terminal.py:56-81` — packaging smoke script は Windows でのみ `os.environ.get("COMSPEC", "")` を読み、空値を既定として子コマンド用の clean environment に設定する。これは検証スクリプト固有の処理である。
