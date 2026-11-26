# `STRATA_SERVER_URL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

App Host の推論ブリッジが、Strata の API worker を探す URL を指定する。`detectBackend()` はこの URL を最初に probe し、Strata worker と確認できればその `baseUrl` を使ってチャット要求を転送する。接続先そのものを起動したり、モデルをロードしたりはしない。worker が応答しない場合や Strata worker と確認できない場合は、supervisor 管理下の engine、既知の localhost OpenAI-compatible server、または build 設定に応じた unavailable/demo 経路へ進む（`app/host/server/inference.mjs:53-58,68-90,93-167,209-247`）。

## 値と判定

App Host は `process.env.STRATA_SERVER_URL?.trim()` で前後の空白を除く。未設定または trim 後に空なら `http://127.0.0.1:8095/v1` を使う。値があれば末尾の `/` をすべて除き、結果が大文字小文字を区別して `/v1` で終わる場合はその値を使い、そうでなければ `/v1` を付け足す。URL parser による検証、scheme・host・port の検査、値全体の比較はない（`app/host/server/inference.mjs:20-21,53-58`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| App Host の URL 正規化 | `http://127.0.0.1:8095/v1` | trim と末尾 `/` 除去の後 `/v1` で終わる値はそのまま。それ以外は末尾に `/v1` を追加する。例: `http://127.0.0.1:9000` → `http://127.0.0.1:9000/v1`、`http://127.0.0.1:9000/v1///` → `http://127.0.0.1:9000/v1` | 値文字列として拒否される形式はコード上定義されていない。空文字および空白だけの値は unset と同じ既定値になる。 |

したがって `1`、`true`、`false`、`0` に特別な真偽値の意味はなく、いずれも文字列 URL として処理され、通常はそれぞれ `/v1` が付く。大文字小文字は trim と末尾スラッシュ処理を除いて変換されない。たとえば `http://host/V1` は `/v1` と一致しないため `/v1` が追加される。空白は前後だけ除去し、内部の空白は検査しない。構文不正などで `fetch()` が失敗した場合、`probeStrata()` は `null` を返して次の backend 探索へ進む（`app/host/server/inference.mjs:55-58,68-90`）。

## 有効になる条件

- App Host の推論ブリッジを通る推論経路で参照される。起動時に `detectBackend({ force: true })` が一度走り、チャットの `streamChat()` からも `detectBackend()` が呼ばれる（`app/host/server/index.mjs:306-314,732-767`; `app/host/server/inference.mjs:93-100,209-223`）。
- 指定先が `/v1/status` に成功応答し、JSON object の `service` が文字列 `strata` と完全一致すると、Strata backend として採用される。条件を満たさない、HTTP が成功しない、JSON が読めない、または fetch が失敗する場合は採用されず、他 backend の探索へ進む（`app/host/server/inference.mjs:68-90,93-117`）。
- 指定先が Strata worker と認識されても、モデル一覧取得は採用条件ではない。`/models` の応答から `data[].id` を backend 情報に入れるが、取得失敗時は空一覧になる。`/status` の `model` がなければ chat 要求の model id は `strata` になる（`app/host/server/inference.mjs:75-86,212-223`）。
- URL probe が失敗した場合、すでに動作中の supervisor engine があればそちらが優先される。その次に、既知の localhost 候補（llama.cpp、Ollama、LM Studio）が探索される。URL はこれらを無効化する専用・排他的な指定ではない（`app/host/server/inference.mjs:23-27,93-139`）。
- Strata URL と他 backend が見つからない場合の最後の扱いは `STRATA_REAL_ENGINE` / `STRATA_PACKAGED` に依存する。real engine 必須なら `unavailable`、そうでなければ demo backend になる。`STRATA_FORCE_DEMO=1` は packaged build 以外で real engine 必須判定を解除する。この条件は URL の優先順位ではなく、すべての probe が失敗した後の fallback を変える（`app/host/server/inference.mjs:40-50,142-166`）。
- Windows/macOS の Tauri shell は、起動時に親プロセスの `STRATA_SERVER_URL` を `std::env::var` で読み、取得できれば App Host の `Command` に同じ値を設定する。`std::env::var` が成功しない場合はこの明示設定を行わない（`app/desktop/src-tauri/src/main.rs:503-551,554-560`）。

## 実行時の詳細

Rust shell の forwarding は App Host 起動時に一度行われる。App Host 側の `strataUrl()` は `detectBackend()` が呼ばれるたびに環境変数を読み直し、関数内やモジュール内に URL の cache はない。したがって App Host プロセス内で環境値が変更されれば次の probe で参照される。一方、`detectBackend()` は Strata probe の失敗後に backend を最大 20 秒再利用する経路を持つため、変更後の Strata probe が失敗した場合に fallback backend の表示・選択が直ちに更新されるとは限らない。`force: true` はこの fallback cache を迂回する（`app/host/server/inference.mjs:37-38,53-58,93-120`）。

Strata worker として採用されると、チャット要求は `${baseUrl}/chat/completions` に POST される。probe 時には `${baseUrl}` から `/v1` を除いた URL の `/v1/status` と、`${baseUrl}/models` を GET する。probe 先が不正または応答しない場合は Strata worker としては採用されず、後続探索または fallback に移る（`app/host/server/inference.mjs:68-90,212-223,251-279`）。

real engine 必須の状態ですべての backend が見つからない場合、backend の `error` に `No Strata engine answered at <正規化後URL> and no supervised engine is running. Start Strata (or load a model) and retry. Simulated output is disabled in this build.` が入る。チャットはこの error を例外にし、要求処理が `type: 'error'` frame として返す。起動時ログは `inference · ...` 行に backend 名または Control の engine 状態を出し、health endpoint は `currentBackend()` を返す（`app/host/server/inference.mjs:142-154,241-244,546-550`; `app/host/server/index.mjs:308-314,785-796,1407-1415`）。

## 根拠

- `app/desktop/src-tauri/src/main.rs:501-551,554-560` — App Host 起動コマンドと環境変数の引き渡し。
- `app/host/server/inference.mjs:20-27,37-38,53-58` — 既定 URL、候補、cache 状態、値の正規化。
- `app/host/server/inference.mjs:68-120,142-167` — Strata worker の probe、採用・fallback・cache。
- `app/host/server/inference.mjs:209-247,251-279` — 推論経路の選択と HTTP 転送。
- `app/host/server/index.mjs:306-314,732-767,785-796,1407-1415` — 起動時判定、チャット要求、エラー frame、health 応答。
