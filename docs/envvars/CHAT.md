# `CHAT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

同梱の host HTTP 操作用 Node.js スクリプトで、API リクエストに渡すチャット ID（`sessionId`）を指定します。対象は `apps/host/scripts/agent-http.mjs` と `apps/host/scripts/agent3-http.mjs` で、Strata エンジンや host サーバーの一般設定ではありません。どちらのスクリプトもヘッダーで `CHAT` をチャット ID、未設定時は新しい ID と説明しています。

## 値と判定

値を数値・真偽値として parse せず、Node.js の `process.env.CHAT` の文字列をそのまま使います。`??` による既定値選択なので、未設定（`undefined`）だけが自動生成 ID に置き換わります。

| 状態 | スクリプトが使う値 |
|---|---|
| 未設定 | コマンドごとの接頭辞と `Date.now()` から作る ID（例: `c-...`, `g-...`, `t-...`） |
| 空文字 | 空文字のまま。既定 ID は生成しない |
| その他の文字列 | 変更せずそのまま `sessionId` として送信 |

長さ、文字種、大文字小文字の検査や trim はスクリプトにありません。CLI 引数による上書きもありません。`agent-http.mjs` では `stream`, `goal`, `goalbar`, `timeskip`, `plan`, `modeswitch`, `long` の各コマンドで参照され、`agent3-http.mjs` では `stream`, `goal`, `goalbar`, `timeskip` で参照されます。`connect` や、`agent-http.mjs` の `skill`, `effort`, `sampling` では参照されません。

## 有効になる条件

この変数が参照されるのは、上記のスクリプトを該当コマンドで起動した場合だけです。通常の Strata アプリ実行やエンジンの backend、OS、build macro が直接 `CHAT` を読む実装は確認できません。

スクリプトは `CHAT` の値を `sessionId` として HTTP JSON に渡します。host サーバーは `/api/chat/stream` で非空文字列の `sessionId` を chat ID として扱い、空文字は chat ID なし（`null`）として処理します。したがって `CHAT=''` は未設定時の自動 ID とは異なり、スクリプトから空の `sessionId` を送ります。Time-skip 開始でもサーバーは非空の `sessionId` だけを chat ID にします。

## 実行時の詳細

スクリプトがコマンド分岐に入ったときに `process.env.CHAT ?? ...` を評価し、そのコマンド内の API リクエストで値を共有します。プロセス起動時の固定定数ではなく分岐内の評価ですが、環境値を後から変更して再評価する処理や cache はありません。

`stream` では `/api/chat/stream` に `sessionId` を送ります。`goal` / `goalbar` / `plan` / `modeswitch` / `long` ではストリームや関連する goal・plan・queue 操作へ同じ ID を渡し、`timeskip` では `/api/timeskip/start` と停止要求に渡します。送信・後続利用の箇所は `apps/host/scripts/agent-http.mjs:85-86,94-105,110-120,123-134,147-163,167-182` と `apps/host/scripts/agent3-http.mjs:74-75,78-89,94-104,107-108,116-118` にあります。

CHAT 固有のログ、警告、終了処理はありません。HTTP 応答が成功でない場合、共通リクエスト関数 `j()` は path・HTTP status と応答内容を含む Error を投げます。チャットストリームの非成功応答も status と本文を含む Error になります（`apps/host/scripts/agent-http.mjs:18-23,35-38`。`agent3-http.mjs` にも同じ実装があります）。空の `sessionId` を受け取った `/api/chat/stream` は chat ID なしとして通常の turn 処理へ進み、Time-skip は同じ場合に chat ID を付けずに開始します（`apps/host/server/index.mjs:1980-2008,2026-2038,1132-1149`）。

## 根拠

- `apps/host/scripts/agent-http.mjs:1-14` — スクリプト用途と環境変数の説明。`STRATA_URL` は必須だが `CHAT` は任意。
- `apps/host/scripts/agent-http.mjs:85-86,94-95,110-112,123-124,147-150,167-182` — 未設定時の各接頭辞付き ID、`sessionId` への転送、同一コマンド内での利用。
- `apps/host/scripts/agent3-http.mjs:1-14,74-75,78-79,94-96,107-108` — agent3 HTTP スクリプトでの説明と全読み取り箇所。
- `apps/host/server/index.mjs:1980-2008,2026-2038` — chat stream が非空の文字列 `sessionId` を chat ID にする条件と turn への受け渡し。
- `apps/host/server/index.mjs:1132-1149` — Time-skip での非空 `sessionId` 判定。
