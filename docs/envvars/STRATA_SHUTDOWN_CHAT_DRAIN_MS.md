# `STRATA_SHUTDOWN_CHAT_DRAIN_MS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

App Host が終了するとき、進行中のチャット保存と `chatStore` の書き込みキューを待つ時間をミリ秒で指定する。`app/host/server/index.mjs` のモジュール評価時に値を読み、`shutdown()` の最初の `drainChatStore()` 呼び出しに渡す。チャット保存の内容や通常の保存処理は変えず、終了時に待つ時間だけを変える。サーバーのシグナル終了、アプリ内終了、およびシェルからの終了は同じ `shutdown()` を通る（`app/host/server/index.mjs:2572-2587`, `app/host/server/app-ui.mjs:106-110`）。

## 値と判定

値は `Number(process.env.STRATA_SHUTDOWN_CHAT_DRAIN_MS) || 5000` で数値化し、その後 `Math.max(500, ...)` と `Math.min(15000, ...)` で 500〜15000 に制限する。環境変数が未設定、空文字、数値化後に 0 または NaN となる文字列なら `5000` にフォールバックする。`Number()` は文字列全体を変換するため、前後の空白は許容するが、`0anything` や `true` は数値にならず既定値になる。数値文字列の小数・指数表記なども変換対象となる。`Infinity` は上限、`-Infinity` は下限に制限される。大文字小文字の比較は行わない（`app/host/server/index.mjs:2572`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| App Host | `5000` ms | 数値化後の正の値。500 未満は 500 ms、15000 超は 15000 ms に制限される（例: `750`、`1e3`、`Infinity`）。 | 空文字、`0`、`-0`、数値化できない文字列（例: `0anything`、`true`）は `5000` ms。負数は値自体としては数値だが、待ち時間は下限の `500` ms になる。 |

`drainChatStore()` 側でも正の有限値を整数ミリ秒に切り捨てる。環境変数から得た値は先に上下限処理されるため、実際の待機上限は 500〜15000 ミリ秒の整数となる（`app/host/server/chat-store.mjs:210-227`）。

## 有効になる条件

- `app/host/server/index.mjs` が実行され、`shutdown()` が呼び出されること。App Host の通常の終了シグナル（`SIGINT`、`SIGTERM`、`SIGHUP`、`SIGBREAK`）、アプリ内の終了、および認証済みシェル要求がこの処理を使う（`app/host/server/index.mjs:1463-1467`, `2574-2587`; `app/host/server/app-ui.mjs:106-110`）。
- 親プロセス消失による終了経路は、別変数 `STRATA_EXIT_WITH_PARENT=1` の場合に限り、この同じ `shutdown()` を呼び出す（`app/host/server/index.mjs:2588-2596`）。
- OS、GPU backend、モデルの有無による値の分岐はない。Control の有無はチャット drain 値を変えないが、別途設定される強制終了期限は Control がある場合 45000 ms、ない場合 10000 ms である（`app/host/server/index.mjs:143-144`, `2577`）。

## 実行時の詳細

値は `index.mjs` がモジュールを評価するときに一度 `const CHAT_DRAIN_MS` として計算され、終了時に再読込されない。したがって同じプロセスの実行中に環境変数を変えても反映されない（`app/host/server/index.mjs:2572-2580`）。

終了処理は重複実行を抑止し、タスクのタイマーとタスク受付を閉じた後、強制終了用タイマーを設定して HTTP server の close を開始する。次に `inFlightChatSaves` の保存処理を待ち、続けて `chatStore.idle()` で保存キューを待つ。両方を指定時間内に完了できない場合、`drainChatStore()` は `{ drained: false }` を返すが、呼び出し元は結果を記録せず、そのまま接続を閉じて他のコンポーネントを停止する。その後、追加で `timeoutMs: 1000` の drain を行ってから `process.exit(0)` を呼ぶ（`app/host/server/index.mjs:2574-2584`; `app/host/server/chat-store.mjs:206-229`）。

全体の強制終了タイマーは Control の有無に応じて 10 秒または 45 秒で `process.exit(0)` を呼ぶ。したがって drain 値がその期限より長い場合、全体タイマーが先に終了させる可能性がある。タイムアウト値の環境変数による変更や、子プロセスへの値の転送はこの実装にはない（`app/host/server/index.mjs:2577-2584`）。

## ログと測定値

この変数の値、drain の成否、drain timeout を報告するログは実装されていない。drain 結果も `shutdown()` で参照されない。終了経路は最終的に `process.exit(0)` を指定するが、全体タイマーによる終了も同じ終了コードを指定する（`app/host/server/index.mjs:2577-2584`）。この変数に関する性能測定値は確認できない。

## 根拠

- `app/host/server/index.mjs:2572-2584` — 値の変換・clamp、shutdown のタイムアウトと drain 順序。
- `app/host/server/index.mjs:131-137`, `1070-1100` — HTTP チャット保存の追跡と進行中保存の集合。
- `app/host/server/index.mjs:1463-1467`, `2586-2596` — シェル要求、シグナル、親プロセス消失からの shutdown 呼び出し。
- `app/host/server/app-ui.mjs:106-110` — ブラウザモードのアプリ終了経路。
- `app/host/server/chat-store.mjs:201-229` — 保存キューの待機、timeout の有界化、drain 結果。
