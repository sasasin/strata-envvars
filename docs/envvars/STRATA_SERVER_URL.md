# `STRATA_SERVER_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の状態は `## main...origin/main` で、未コミット変更はありません。

## 役割

Strata の App Host が接続を試す Strata API worker の URL を指定します。指定先が Strata worker と確認できれば、App Host はそこを最初の推論バックエンドにします。URL を指定しない場合は `http://127.0.0.1:8095/v1` を使います。デスクトップアプリのホスト起動コードは、親プロセスでこの変数を Unicode 文字列として取得できた場合に子 Node ホストへ設定します（`apps/desktop/src-tauri/src/main.rs:487-491`）。この起動経路は Windows/macOS 向けです（同 `:495-501`）。

## 値と判定

| プロセス環境での値 | Strata の処理 |
|---|---|
| 未設定、空文字、空白だけ | `trim()` 後に空となるため既定値 `http://127.0.0.1:8095/v1`。 |
| 空白以外の値 | 前後の空白を除き、末尾の `/` をすべて除去する。末尾が大文字小文字を区別して `/v1` ならそのまま、そうでなければ `/v1` を追加する。 |
| URL として不正、応答なし、非 2xx の status 応答、または Strata worker と識別できない応答 | この変数の値自体を検証してエラー終了する処理はない。status probe の失敗は捕捉され、後続のバックエンド候補へ進む。 |

根拠: `apps/host/server/inference.mjs:19-20,44-49,59-82`。

## 有効になる条件

- Node の `apps/host/server` が推論ブリッジを使い、プロセス環境に値がある場合に評価されます。候補名の実際の参照は `apps/desktop/src-tauri/src/main.rs:489-490` と `apps/host/server/inference.mjs:46` です。その他の出現は同ファイルの説明コメントです。
- URL が Strata worker として採用されるには、`/v1/status` が成功し、JSON object の `service` が文字列 `strata` である必要があります。`/models` の取得はモデル一覧の補足に使われ、失敗しても status が Strata と確認できていれば採用されます（`apps/host/server/inference.mjs:59-78`）。
- Strata worker の probe が通らない場合、起動済みの Strata 管理エンジン、固定候補（llama.cpp、Ollama、LM Studio）の順に確認します。いずれも使えず `STRATA_REAL_ENGINE=1` または `STRATA_PACKAGED=1` の実行なら `unavailable` となり、デモ応答は使いません。それ以外の開発実行では demo backend に進み得ます。デスクトップの `host_command` は両 real-engine 変数を `1` に設定します（`apps/host/server/inference.mjs:38-42,84-157`; `apps/desktop/src-tauri/src/main.rs:469-473`）。
- CLI 引数や別の環境変数でこの URL を上書きする処理は、対象ソース内では見つかりませんでした。`STRATA_SERVER_URL` 自体に優先されるのは、上記の Strata worker probe が成功するかどうかであり、失敗時には別バックエンド選択へ移ります。

## 実行時の詳細

`detectBackend()` はまず `strataUrl()` で URL を組み立て、status endpoint を最大 900 ms で確認します。応答が 2xx で、JSON の `service` が `strata` のときに限り Strata backend として記録し、その `/models` から model ID を収集します。status の通信・JSON parse 失敗は `probeStrata()` 内で `null` になります（`apps/host/server/inference.mjs:59-90`）。

ホスト起動時に `apps/host/server/index.mjs:278` が `detectBackend({ force: true })` を呼び、その結果を `inference · ...` の起動ログに出します（同 `:280-284`; 表示文字列は `apps/host/server/inference.mjs:532-536`）。チャット推論では `streamChat()` が改めて `detectBackend()` を呼ぶため、URL は各呼び出しで再評価されます（同 `:84-86,199-205`）。値の parse 結果を static cache する実装はありません。なお、バックエンド状態は別途保持されます。Strata probe と管理エンジン確認の後、候補の再確認を最大 20 秒省く経路があります（同 `:28-29,98-110`）。

Strata worker が採用されると `/v1/chat/completions` に streaming POST します。HTTP が成功しない、または body がない場合は `Engine responded <status>` の Error を投げます（`apps/host/server/inference.mjs:199-234,239-267`）。Strata worker を含む全候補がなく real-engine が必須の場合は `No Strata engine answered at <URL> ... Simulated output is disabled in this build.` を error として返します（同 `:131-143,199-234`）。起動時には backend 名または `No Strata engine` 等が `inference · ...` に表示されます（同 `apps/host/server/index.mjs:278-284`; `apps/host/server/inference.mjs:532-536`）。probe の接続失敗そのものに対する専用 warning はありません。

## 根拠

- デスクトップ親プロセスから子ホストへの値の受け渡しと Windows/macOS の起動経路: `apps/desktop/src-tauri/src/main.rs:487-501`
- URL の既定値・正規化: `apps/host/server/inference.mjs:19-20,44-49`
- Strata worker の照合と timeout: `apps/host/server/inference.mjs:59-82`
- backend の優先順位・cache・real-engine 時の unavailable 分岐: `apps/host/server/inference.mjs:84-157`
- 起動時 probe / ログ、推論からの再 probe、real backend の選択: `apps/host/server/index.mjs:278-284`; `apps/host/server/inference.mjs:199-234`
- 推論 POST と HTTP 失敗: `apps/host/server/inference.mjs:239-267`
