# `STRATA_FIXTURE_FILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/tests/ui-fixture-host.mjs` を手動の CUA レビュー用 fixture サーバーとして起動するとき、入力 JSON ファイルのパスを指定します。ソース先頭の説明は、このサーバーを「Disposable API-edge fixtures for manual CUA review」とし、「Never used by the app host」と明記しています。したがって、通常の Strata アプリホストの設定ではなく、このテスト補助スクリプト専用です。

候補名のリポジトリ全体検索では、コメント上の使用例と `process.env.STRATA_FIXTURE_FILE` による読み取りがこのスクリプトにあるだけで、他の参照や別の helper 経由の読み取りは見つかりませんでした。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `file` が falsy になり、サーバー作成前に `Error('Provide a disposable fixture JSON path.')` を throw します。 |
| 空文字 | 同じく falsy なので起動を拒否し、同じ Error を throw します。 |
| 空でない文字列 | パスとしてそのまま保持し、ファイル内容を UTF-8 で読み、JSON として parse します。数値変換、空白除去、パスの事前検証はありません。 |
| ファイルが読めない、または JSON が不正 | リクエスト処理中の `read()` で例外になります。catch 節は、まだ応答ヘッダーがなければ HTTP 500 を返し、本文に `String(error)` を書きます。 |

## 有効になる条件

この変数を読むのは `apps/host/tests/ui-fixture-host.mjs` の Node.js プロセスだけです。コメントの使用例は `node tests/ui-fixture-host.mjs` で、同スクリプトは upstream demo host の API 応答を fixture に従って変換する補助サーバーとして、`127.0.0.1` のポート 8796（`STRATA_FIXTURE_PORT` で指定可能）に listen します。通常の app host での読み取り、OS/backend/build macro による分岐、CLI 引数との優先順位はありません。

## 実行時の詳細

`process.env.STRATA_FIXTURE_FILE` はモジュール評価時に一度 `file` 定数へ読み込まれます。その後の環境変更を再取得する処理や、パスを CLI 引数・他の環境変数で上書きする処理はありません。JSON データ自体は cache されず、`read()` が呼ばれるたびに `readFileSync(file, 'utf8')` と `JSON.parse` を実行します。`read()` は各リクエスト処理や応答変換から呼ばれます。

ファイル内の `scenario`、`responses`、`errors`、`readOnly` などは fixture サーバーの API 応答を制御します。これらの値は JSON ファイルから読み取られるものであり、`STRATA_FIXTURE_FILE` 自体がシナリオ名や真偽値として解釈されるわけではありません。リクエスト中にファイル読み込みや JSON parse が失敗した場合、スクリプトは例外文字列を HTTP 500 応答本文にします。unset / 空文字による起動時 throw について、スクリプト内に独自の catch、ログ、終了処理はありません。

## 根拠

- `apps/host/tests/ui-fixture-host.mjs:1-3` — 手動 CUA レビュー用であり、app host では使わないこと、起動例。
- `apps/host/tests/ui-fixture-host.mjs:7-11` — 起動時に環境からパスを取得、未設定・空文字を拒否、UTF-8 読み込みと JSON parse。
- `apps/host/tests/ui-fixture-host.mjs:13-27,29-39` — fixture データを読み、API 応答の変換・エラー応答・read-only 応答に使う。
- `apps/host/tests/ui-fixture-host.mjs:60-63` — JSON 応答の変換と、リクエスト中の例外を HTTP 500 本文へ返す処理。
