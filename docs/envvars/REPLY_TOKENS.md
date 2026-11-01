# `REPLY_TOKENS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`apps/host/scripts/chat-growth-proxy.mjs` がデモ用の長い応答を作る際、`POST /api/chat/stream` で生成する回答部分の長さを決めます。Strata 本体のサーバー設定ではなく、同梱のコメント上 “Throwaway” とされるチャット画面の成長測定用 proxy script 専用です。同じファイルの説明では、proxy は `/api/chat/stream` 以外をデモ host に転送します。`chat-growth.mjs` はこの proxy を測定用 host とともに使うスクリプトとして記載しています（`apps/host/scripts/chat-growth-proxy.mjs:1,9-25`; `apps/host/scripts/chat-growth.mjs:1`).

## 値と判定

スクリプトのモジュール評価時に `Number(process.env.REPLY_TOKENS ?? 12000)` を一度評価します。`??` は未設定（`undefined`）のときだけ既定値を使うため、設定された文字列を `Number` で数値化します。整数性や範囲は検査されず、parse 失敗時の fallback もありません。

| 環境値 | `TOK` | この proxy の回答ループ |
|---|---:|---|
| unset | 12000 | 回答を生成する |
| `12000` など数値化できる正数 | 数値 | `sent < TOK` の間、回答を生成する。`sent` は chunk ごとに 6 増えるが、条件判定は段落ごとなので、指定値を超えた後も段落末尾まで出力する |
| 空文字または空白だけ | 0 | 回答 delta は生成しない |
| `0` または負数 | 0 以下 | 回答 delta は生成しない |
| 数値化できない文字列 | `NaN` | 比較 `sent < TOK` が偽となり、回答 delta は生成しない |
| `Infinity` | 正の無限大 | 条件が終わらず回答ループが継続する |

値は実際のモデル token 数ではありません。合成文の文字列を 24 文字ずつ delta frame に分け、各 chunk に対して `sent` を 6 増やしてループ条件と `tokensOut` に使うシミュレーション上のカウンターです（`apps/host/scripts/chat-growth-proxy.mjs:4,18-20`).

## 有効になる条件

この変数が使われるのは `chat-growth-proxy.mjs` が起動しており、リクエストが `POST` で URL が `/api/chat/stream` から始まる場合だけです。この endpoint では upstream host に転送せず、合成 NDJSON 応答を返します。それ以外の method/path は upstream に転送されます（同:9-25）。

CLI 引数や Strata 本体の設定との優先順位はありません。`TOK` を上書きする別の環境変数もこのスクリプトにはありません。回答長とは別に、`REASON_TOKENS` が reasoning frame の長さを決め、`RATE` が delay 計算に使われます。これらは同じ行で別々に読み込まれ、`REPLY_TOKENS` の値を補正しません（同:4,16-19）。

## 実行時の詳細

値は proxy 起動時のモジュール評価で定数 `TOK` に保存されるため、そのプロセス内で後から環境変数を変更しても反映されません。未設定時の既定値は 12000 です。CLI 引数の読み取りはありません（同:3-4）。

該当 POST を受けると proxy は HTTP 200 と `application/x-ndjson` を設定し、`start` frame、`REASON_TOKENS` に応じた reasoning frame、続いて `TOK` に達するまで合成回答の `delta` frame を書きます。`TOK` が 0 以下または `NaN` の場合、回答 delta はなくても `stats` frame を出さずに `done` frame を送り、`tokensOut` は 0 になります。通常の回答ループでは段落ごとに `stats` frame を出し、最後の `done.tokensOut` は実際に増加した `sent` 値です（同:12-20）。

この proxy は listen 開始時に `proxy on`, port を console に出します。該当 POST の処理に `REPLY_TOKENS` の無効値を報告する警告・エラー・終了処理はありません。非該当リクエストの upstream 接続エラーは HTTP 502 になりますが、これは `REPLY_TOKENS` の処理経路ではありません（同:23-26）。

## 根拠

- `apps/host/scripts/chat-growth-proxy.mjs:1-4` — 用途コメント、環境変数の読み取りと既定値。
- `apps/host/scripts/chat-growth-proxy.mjs:9-21` — endpoint 条件、HTTP 応答、合成回答ループと `tokensOut`。
- `apps/host/scripts/chat-growth-proxy.mjs:23-26` — その他のリクエスト転送と upstream エラー処理。
- `apps/host/scripts/chat-growth.mjs:1` — 測定用 script が proxy を使う旨。
