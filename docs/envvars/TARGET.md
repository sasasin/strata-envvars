# `TARGET`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`TARGET` は、ホストアプリ配下のテスト用 slow proxy が転送先モデルサーバーを選ぶための URL です。Strata engine や通常の host server が読む設定ではありません。`apps/host/scripts/slow-proxy.mjs` を直接起動するときだけ使われる開発・テスト用スクリプトで、利用例は同ファイル冒頭のコメントにあります（`apps/host/scripts/slow-proxy.mjs:1-4`）。

## 値と判定

| 環境値 | 判定・結果 |
|---|---|
| 未設定 | `http://127.0.0.1:18797` を使う。 |
| 空文字 | 既定値には置き換わらない。空文字を `new URL()` に渡すため、URL 生成時に例外となる。 |
| 設定あり | 値を trim や別形式への変換をせず `new URL(value)` に渡す。URL として解釈できない値は例外となり、server 作成・listen より前に起動処理が止まる。 |

値の読み取りと URL 生成はモジュール評価時に一度だけ行われます。CLI 引数、設定ファイル、他の環境変数による上書き経路はこのスクリプトにはありません（`apps/host/scripts/slow-proxy.mjs:9-12`）。

## 有効になる条件

この変数が使われるのは `apps/host/scripts/slow-proxy.mjs` を Node.js で直接実行した場合です。host の通常起動や Strata engine の起動経路からこの環境変数を読む参照はありません。リポジトリ内の同ファイル参照は環境読み取りと起動例だけです。

## 実行時の詳細

各受信リクエストは `http.request()` で `TARGET` の `hostname` と `port` へ転送されます。転送先 URL の pathname や query はリクエスト先に使われず、受信リクエストの `req.url` が path になります。`target.host` は転送リクエストの `Host` header に設定されます。応答の `Content-Type` に `text/event-stream` が含まれるときだけ各 chunk の返送を `DELAY_MS`（未設定時 200 ms）だけ遅らせ、それ以外はそのまま返します。起動時には listen した port、delay、`target.origin` を標準出力に表示します（`apps/host/scripts/slow-proxy.mjs:9-18,23`）。

転送接続でエラーが起き、応答 header がまだ送られていない場合は proxy が HTTP 502 を返し、エラー message を response body にします（`apps/host/scripts/slow-proxy.mjs:20`）。このスクリプトは `http.request()` を使っており、`TARGET` の protocol による HTTPS 用 request への切り替えはありません（同 `:14`）。

## 根拠

- `apps/host/scripts/slow-proxy.mjs:1-4` — テスト用 slow model proxy であることと手動起動例。
- `apps/host/scripts/slow-proxy.mjs:9-12` — `TARGET` の読み取り、未設定時 URL、module 評価時の初期化。
- `apps/host/scripts/slow-proxy.mjs:13-23` — 転送先への接続、イベントストリームの遅延、502 エラー処理、起動ログ。
- `apps/desktop/scripts/fetch-node.sh:40-53` — 同名の `TARGET` は `target "$@"` の結果を受けるシェル変数で、環境変数の読み取りではない。
