# `DELAY_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/slow-proxy.mjs` を手動起動したとき、転送する `text/event-stream` 応答の各チャンクを遅らせます。コメントでは、テスト用にモデルサーバーを転送し、高速な engine から低速なコンピューターのような応答を作るスクリプトと説明されています。通常の Strata engine / host の設定として読む箇所は見つかりませんでした。

## 値と判定

スクリプトのモジュール評価時に `Number(process.env.DELAY_MS ?? 200)` で一度読み取ります。

| 環境値 | `delay` の結果 |
|---|---:|
| 未設定 | `200`（既定値） |
| 空文字 | `0`（環境値は nullish ではなく、`Number("")` の結果） |
| 数値として変換できる文字列 | `Number()` の数値。例: `200`, `1e3`, 前後に空白のある数値 |
| 数値でない文字列 | `NaN` |
| 数値の範囲外になる値 | JavaScript `Number` の結果（例: 大きすぎる値は `Infinity`） |

このスクリプト自身は、値の文字列検証、範囲制限、clamp、無効値の fallback を行わず、変換結果を `setTimeout` に渡します。したがって、負数・`NaN`・`Infinity` などに対する実際のタイマー待ち時間はこのソースだけでは規定されません。

## 有効になる条件

`DELAY_MS` は `node scripts/slow-proxy.mjs` でこのスクリプトを起動した場合に限って使われます。起動例はソースコメントにあり、同じ例で `TARGET` と `PORT` も指定しています。CLI 引数や別の環境変数で `DELAY_MS` を上書きする処理はありません。応答の `content-type` 文字列に `text/event-stream` が含まれる場合だけチャンクを遅らせ、それ以外の応答は直接 pipe します。

## 実行時の詳細

遅延値はプロセス起動時のモジュール評価で定数 `delay` に入り、各チャンクの transform で `setTimeout(() => done(null, chunk), delay)` に渡されます。起動時には待受ポートと遅延値を含む `slow model on ... (+... ms per streamed chunk) -> ...` を console に出します。上流リクエストが失敗し、応答ヘッダー未送信なら 502 を返し、レスポンス本文にエラーメッセージを出します。`DELAY_MS` 自体について、警告・明示的な終了・timeout を行う処理はありません。

## 根拠

- `apps/host/scripts/slow-proxy.mjs:1-4` — テスト用プロキシの説明、起動例、SSE のみを遅らせる旨。
- `apps/host/scripts/slow-proxy.mjs:9-11` — `TARGET`、`PORT`、`DELAY_MS` の読み取りと既定値。
- `apps/host/scripts/slow-proxy.mjs:13-23` — loopback での待受、SSE 判定、各チャンクへの timer 適用、上流エラー時の 502 と起動ログ。
- `apps/host/package.json:7-27` — host の npm script 一覧に `slow-proxy.mjs` の登録はありません。
