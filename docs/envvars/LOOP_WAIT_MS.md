# `LOOP_WAIT_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/agent2-flow.mjs` の実アプリ操作シナリオで、`/loop` の最初の応答後に二回目の実行を待つための timeout を指定します。Strata のサーバーや通常のアプリ実行を設定する変数ではありません。このスクリプトを実行し、かつ `SKIP` に `loop` が含まれない場合だけ参照されます（`apps/host/scripts/agent2-flow.mjs:2-13,86-88`）。

## 値と判定

| 状態・値 | スクリプトが使う値 |
|---|---|
| 未設定 | `150000`（ミリ秒） |
| 設定あり | `Number(process.env.LOOP_WAIT_MS)` の結果 |

未設定の判定は nullish coalescing（`??`）です。環境変数が空文字なら未設定扱いにはならず、JavaScript の `Number("")` の結果である `0` が timeout 引数になります。数値として読める文字列は数値へ変換され、負数も含め変換後の値をそのまま渡します。数値に変換できない文字列は `NaN` になります。スクリプト内に整数限定、範囲チェック、clamp、無効値時の fallback はありません（`apps/host/scripts/agent2-flow.mjs:98-99`）。

CLI 引数、設定ファイル、他の環境変数との優先順位は実装されていません。明示設定値は既定値 `150000` を置き換えます。

## 有効になる条件

- `node scripts/agent2-flow.mjs` でこのシナリオスクリプトを実行する。
- `SKIP` のカンマ区切り項目に `loop` がない。
- スクリプトが `/loop 1m ...` を送信し、最初の応答を待ち終えて二回目の実行待ち箇所に進む。

通常の Strata アプリ実行、サーバーモード、GPU backend、モデル状態を変える読み取り箇所は見つかりませんでした。値が変えるのはシナリオスクリプト側の待機時間です。

## 実行時の詳細

`LOOP_WAIT_MS` は二回目を待つ直前に一度読み、`Number(...)` で変換して `page.waitForFunction` の `timeout` オプションに渡します。値はプロセス開始後に環境から再取得されません。待機 Promise が reject した場合、`.catch(() => {})` でその reject を無視して後続へ進み、チャット内の対象メッセージ数が初回より増えたかを `check` で判定します（`apps/host/scripts/agent2-flow.mjs:91-103`）。

判定結果は標準出力に `ok` または `FAIL` として出ます。失敗フラグが立つとスクリプト末尾で終了コード `1`、立たなければ `0` で終了します（`apps/host/scripts/agent2-flow.mjs:28-29,175-180`）。timeout に渡された値が不正または極端な場合に待機 API がどう扱うかは、その API の挙動に依存し、この Strata スクリプト自身は検証・補正しません。

## 根拠

- `apps/host/scripts/agent2-flow.mjs:12-13` — シナリオスクリプトの使用環境変数として記載され、既定 timeout を説明。
- `apps/host/scripts/agent2-flow.mjs:86-103` — `SKIP` による loop シナリオの条件、初回応答後の環境変数読み取り、timeout への受け渡し、二回目実行の判定。
- `apps/host/scripts/agent2-flow.mjs:28-29,171-180` — 判定ログと最終終了コード。

リポジトリ全体を `rg -n --hidden --glob '!.git/**' -S 'LOOP_WAIT_MS'` で検索した結果、候補一覧にある名前の参照はこのスクリプト内のコメントと読み取りだけでした。したがって `000_envvers.md` の候補は同梱シナリオスクリプト用の実際の環境読み取りを指しますが、Strata アプリ本体の環境設定ではありません。
