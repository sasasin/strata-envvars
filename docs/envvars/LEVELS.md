# `LEVELS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`LEVELS` は Strata の engine や通常の host 設定ではなく、同梱の手動 HTTP 診断スクリプト `apps/host/scripts/agent-http.mjs` の `effort` コマンドが比較する thinking level のリストです。`effort` は質問を各 level で順に送り、reasoning / 回答の文字数、出力 token 数、所要秒数、回答抜粋を JSON 行で出力します（`apps/host/scripts/agent-http.mjs:195-206`）。このスクリプトはブラウザーを介さず host に接続する手動用ツールで、`apps/host/package.json:7-27` の npm scripts には登録されていません。

## 値と判定

スクリプトは `process.env.LEVELS` が truthy ならその文字列に `split(',')` を適用し、結果の各要素をそのまま `thinking` としてリクエストします。未設定または空文字なら `['Off', 'Low', 'Medium', 'High', 'Max']` を使います。空白の trim、要素の検証、重複除去はありません。たとえば `LEVELS='Low, High,'` は `['Low', ' High', '']` になります。環境変数は `effort` 分岐の for 文に入る時に一度参照され、ループ中に再読込しません（`apps/host/scripts/agent-http.mjs:199-201`）。

このスクリプト自身は受理値の範囲を制限しません。送信先の処理では、agent 経路は `off`, `low`, `medium`, `high`, `max` のみを大文字小文字を無視して認識し、それ以外を `null` として level 指定なしで扱います（`apps/host/server/agent/profile.mjs:160-170`）。agent を使わない plain 経路では、`openai-chat` かつ reasoning 対応と判定されたモデルに限って同じ level 群を送信し、`max` は `high`、`off` は `none` に変換します。その他の値・モデル・protocol では level を provider リクエストに加えません（`apps/host/server/model-providers.mjs:159-164`）。したがって `LEVELS` の要素を受け付けるかは Strata host とモデル経路に依存し、無効値に対する統一エラーはありません。

## 有効になる条件

- スクリプトを `node apps/host/scripts/agent-http.mjs effort [質問] [thinking budget]` として `effort` コマンドで実行する必要があります。別コマンドでは `LEVELS` を参照しません（`apps/host/scripts/agent-http.mjs:13-15,195-201`）。
- `STRATA_URL` が必要です。未設定なら `STRATA_URL is required` を stderr に出して終了コード 2 で終了します（`apps/host/scripts/agent-http.mjs:13-14`）。
- API 接続が保存済みである必要があります。スクリプトは `/api/model-providers` の最後の connection とその最初の model を選びます。connection がなければエラーを投げて `connect` の実行を促します（`apps/host/scripts/agent-http.mjs:27-32`）。この処理は `LEVELS` による優先順位変更を行いません。
- `PLAIN` が空でない値なら各 chat リクエストに `agent: false` を付けて plain 経路を選びます。未設定または空文字の場合、agent が有効で chat session が作成できれば agent 経路が使われます。host の agent が利用できない場合は、remote model があるため通常の remote turn へ進みます（`apps/host/scripts/agent-http.mjs:201`; `apps/host/server/index.mjs:2004-2020,2035-2037`）。

## 実行時の詳細

各 level につき新しい session ID を作り、同じ質問、`mode: 'bypass'`、選択した remote model、`thinking: level`、数値化した budget を `/api/chat/stream` に POST します。既定質問は `What is 17 times 23, and is the result divisible by 3? Explain briefly.`、budget は `0` です（`apps/host/scripts/agent-http.mjs:197-201`）。これは同梱スクリプトが host に値を渡す挙動であり、engine の環境変数や生成結果への直接設定ではありません。

plain 経路では host が `thinking` と budget を remote turn に渡し、provider 層が対応する場合に限り API request に reasoning parameter を設定します（`apps/host/server/index.mjs:2026-2038,649-650`; `apps/host/server/model-providers.mjs:146-166`）。agent 経路では chat の thinking level を Harness の model selection に渡します。未対応の level はモデル既定値へ落とし、level 不指定での選択が失敗した場合には、level なしでもう一度選択を試みます（`apps/host/server/agent/agent-bridge.mjs:388-405`）。

スクリプトは受信 frame から `reasoning` と `delta` の文字数を集計し、最後の frame の token 数などとともに JSON 行を stdout に出します（`apps/host/scripts/agent-http.mjs:201-206`）。model API の失敗は host が `error` frame にする経路があり、スクリプト側の `stream()` は HTTP 非成功応答を例外にします（`apps/host/server/index.mjs:595-600`; `apps/host/scripts/agent-http.mjs:34-38`）。この診断スクリプトのコードには `LEVELS` 固有の警告・終了処理はありません。

## 候補一覧との照合

`000_envvers.md` の候補名には `LEVELS` が載っています（`000_envvers.md:434`）。Strata 全体の参照検索では、環境変数読み取りは上記の `process.env.LEVELS` だけでした。もう一つの出現 `bench/results/2026-10-06-community-2x-rtx-pro-4500-engine-0.1.40.1/parlast.py:2,4,40` はコマンドライン引数 `sys.argv[2]` から作るローカル変数で、環境変数ではありません。
