# `STRATA_SERVER_URL`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。Strata 所有のデスクトップ起動コードと App Host を対象に確認した。

## 役割

App Host が Strata Python API worker を探すときに、worker の URL を明示する変数。未設定または空白だけなら既定の `http://127.0.0.1:8095/v1` を使い、設定があればその URL を Strata worker の最初の接続先にする。推論リクエストは検出した Strata worker の `/chat/completions` へ中継される。

## 値と判定

`process.env.STRATA_SERVER_URL?.trim()` で読み、前後の JavaScript `trim()` 対象の空白を除く。値が未設定か、trim 後に空文字なら既定 URL に戻る。非空なら末尾の `/` をすべて除去し、結果が大文字小文字を区別して `/v1` で終わらなければ `/v1` を付加する。

| 値 | 使用する base URL |
|---|---|
| 未設定、空文字、空白のみ | `http://127.0.0.1:8095/v1` |
| `http://host:8095` | `http://host:8095/v1` |
| `http://host:8095/` | `http://host:8095/v1` |
| `http://host:8095/v1/` | `http://host:8095/v1` |
| `http://host:8095/V1` | `http://host:8095/V1/v1` |

スキーム、host、port、path の妥当性はこの関数では検証しない。数値変換や真偽値化もしない。値を URL として解釈して `/v1` を足すだけなので、空白を含む不正 URL などは後続の `fetch` が失敗する。

根拠: `apps/host/server/inference.mjs:19-20,44-49`。

## 有効になる条件

App Host の推論 backend 検出に適用される。デスクトップ Tauri の Windows/macOS 用 `host_command()` は、親プロセスにこの環境変数が存在する場合、その値を Node App Host の環境へ設定する。未設定の場合は明示設定を加えず、App Host 側の既定 URL が使われる。ソース checkout から App Host を直接起動する場合も、Node プロセスの環境変数がそのまま読み取られる。

指定 URL への接続だけで Strata backend と認定されるわけではない。`/v1/status` が成功し JSON object を返し、その `service` が文字列 `strata` と一致する必要がある。条件を満たさない、HTTP error、JSON 解析失敗、timeout、接続エラーではこの URL の候補を採用しない。

指定先が利用できない場合も探索は終了しない。続けて Host が管理する llama.cpp engine、次に既定 URL の llama.cpp / Ollama / LM Studio を確認する。どれも利用できない場合、実 engine 必須モードでは unavailable backend になり、開発用 demo モードでは demo backend になり得る。したがって、この変数は接続先を固定・強制する設定ではない。

根拠: `apps/desktop/src-tauri/src/main.rs:432-477`; `apps/host/server/inference.mjs:84-157`。

## 実行時の詳細

App Host 起動時、`server/index.mjs` は `detectBackend({ force: true })` を一度実行し、その結果から起動ログの `inference · ...` 表示を決める。チャットの `streamChat()` も推論ごとに `detectBackend()` を呼び、Strata backend と認識された場合は、その `baseUrl` を使って `/chat/completions` へリクエストを送る。

各 `detectBackend()` 呼び出しで `strataUrl()` が環境を読み直し、Strata worker probe を先に実行する。したがって値はこの関数内に固定キャッシュされない。一方、Strata probe が失敗し、既存 backend が engine 以外で、直前の検出から20秒未満かつ `force` が false の場合は、その既存 backend を返すコード経路がある。その経路では他候補を再検出しない。通常の `streamChat()` 呼び出しは force を渡さない。

Strata probe は `/v1/status` に最大900 ms の timeout でアクセスする。認定後、`/models` も同じ timeout で照会し、返却された model ID、status の model/context/loaded/dialects を backend 情報として保持する。モデル一覧取得に失敗しても、status で Strata と確認できていれば backend は採用され、models は空配列になる。実際の生成は `${baseUrl}/chat/completions` へ POST する。

根拠: `apps/host/server/index.mjs:258-264`; `apps/host/server/inference.mjs:59-80,84-157,199-235,239-266`。

## 根拠

- URL の既定値と正規化: `apps/host/server/inference.mjs:19-20,44-49`
- Strata worker の識別と状態・model取得: `apps/host/server/inference.mjs:59-80`
- 検出順、キャッシュ、fallback、unavailable/demo: `apps/host/server/inference.mjs:84-157`
- 検出結果に応じた生成先: `apps/host/server/inference.mjs:199-235,239-266`
- 起動時検出とログ: `apps/host/server/index.mjs:258-264`
- デスクトップから App Host への引き渡し: `apps/desktop/src-tauri/src/main.rs:432-477`
