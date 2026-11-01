# `USER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のホストアプリがコーディングエージェント用の DeepSeek Harness を起動するとき、ホスト環境にある `USER` を子プロセス環境へ引き継ぐための許可リスト項目です。Strata は値をユーザー名として解析したり、アプリ内の設定・モデル選択に使ったりしません。

候補一覧に対する大文字完全一致検索では、実行時コードにある `USER` の参照は Harness 環境フィルターの許可リストでした。`tools/test_strata_bench.py` にも `USERNAME` または `USER` を読む箇所がありますが、これはテストコードなので調査対象の実装根拠にはしていません（同ファイル 169-172 行）。

## 値と判定

| 入力 | Strata の扱い |
|---|---|
| `USER` が環境にない | フィルターの入力に存在せず、転送されません。 |
| 値が空文字 | `undefined` ではないため除外されず、空文字のまま転送されます。 |
| 値が空でない | 内容の検証・変換をせず、そのまま転送されます。 |
| キー名の大小文字 | 許可リスト正規表現は `i` フラグ付きなので `USER` と `user` などに一致します。 |

`agentEnvironment()` は `externalEnvironment(base)` の各キーと値を列挙し、値が `undefined`、許可リストに不一致、または秘密情報名フィルターに一致する場合に除外します。残った値を同じキーで出力オブジェクトへ設定します。`USER` は秘密情報名フィルターには一致しません。最後に `extra` を展開するため、呼び出し側が同名キーを渡した場合はその値が許可リストからコピーした値を上書きします（`apps/host/server/agent/harness-runtime.mjs:20-36`）。

## 有効になる条件

この転送はホストアプリが Harness プロセスを起動する場合に限られます。Harness はエージェント機能を使うチャット経路で遅延起動されます。チャット要求に session ID があり、エージェントが無効でなく、ローカル Strata モデルまたは API モデルが使えることが要求側の条件です。Harness コンポーネントが利用可能なら、そのプロセスを開始します（`apps/host/server/index.mjs:2001-2018`, `apps/host/server/agent/agent-bridge.mjs:205-224`）。通常のチャット経路や Harness を起動しない場合、ここでの `USER` 転送は起きません。

AppImage 環境では、`externalEnvironment()` は起動時の環境を記録した `STRATA_ORIGINAL_ENV` があればそれを復元してフィルターに渡します。記録がない場合は AppImage 専用の項目を除去した現在の環境を使います。AppImage 外では現在の環境のコピーを使います（`apps/host/server/external-env.mjs:28-40,43-57,60-71`）。したがって、転送される値はこの処理が選ぶ入力環境に `USER`（または大文字小文字を変えた同名キー）として存在するかに依存します。

## 実行時の詳細

`HarnessProcess.start()` が Harness 用の Node 子プロセスを `spawn()` する時点で `agentEnvironment(process.env, ...)` を評価します。環境値は起動時にコピーされ、Strata による後続の再読込や cache はありません。`USER` の値だけで起動を成功・失敗させる分岐、数値変換、CLI 引数との優先順位はありません（`apps/host/server/agent/harness-runtime.mjs:25-36,75-84`）。

Strata は転送先 Harness 内で `USER` がどう使われるかをこの実装では制御しません。`USER` 固有のログ、警告、終了条件もありません。Harness 起動が失敗する場合は一般的な起動エラー処理を通り、チャットにエージェント失敗として通知されますが、`USER` によるものとはコードから結び付けられません（`apps/host/server/agent/harness-runtime.mjs:94-104`, `apps/host/server/agent/agent-bridge.mjs:205-224`）。

## 根拠

- 許可リスト、環境のコピーとフィルター、`extra` による上書き: `apps/host/server/agent/harness-runtime.mjs:20-36`。
- Harness 子プロセスの起動時に環境を渡す箇所: `apps/host/server/agent/harness-runtime.mjs:75-84`。
- AppImage 元環境の復元とフィルター入力: `apps/host/server/external-env.mjs:28-40,43-57,60-71`。
- エージェント経路の条件と Harness 起動: `apps/host/server/index.mjs:2001-2018`, `apps/host/server/agent/agent-bridge.mjs:205-224`。
