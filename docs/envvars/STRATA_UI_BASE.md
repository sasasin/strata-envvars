# `STRATA_UI_BASE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の Strata 作業ツリーは `main...origin/main` で変更なし。環境変数文書リポジトリには既存の未コミット変更があるため、この文書だけを新規作成した。

## 役割

`apps/host/scripts/ui-drive.mjs` を使う Playwright UI スクリプトが接続するテスト用 Strata host のベース URL を指定します。Strata アプリ本体の設定ではなく、同梱の UI 駆動スクリプト用です。直接の利用スクリプトとして確認できたのは `apps/host/scripts/pictures-ui.mjs` です。同スクリプトはコメントで throwaway host を前提にしています。

## 値と判定

| 環境変数の状態 | `BASE` の値 |
|---|---|
| 未設定（`process.env.STRATA_UI_BASE` が `undefined`） | `http://127.0.0.1:18791` |
| 設定あり（空文字を含む） | 設定された文字列をそのまま採用 |

`??` による既定値選択で、空文字を未設定として扱う検査や URL の parse・検証、trim、末尾 `/` の除去はありません。`BASE` は ES module の評価時に一度定まり、export された定数として使われます。したがって、モジュール評価後にプロセス環境を変更しても、この `BASE` には反映されません。CLI 引数や別の環境変数による上書きはありません。

## 有効になる条件

`ui-drive.mjs` を import するスクリプトを Node.js で実行する場合に使われます。確認できた利用元 `pictures-ui.mjs` は `ensureMock()` と `open()` を呼び、さらに `ui-drive.mjs` の `api()` と `open()` が `BASE` を参照します。アプリの通常起動、サーバー側の設定、GPU/backend の選択には使われていません。

## 実行時の詳細

`api(path, ...)` は `BASE + path` を `fetch` に渡し、`open()` は `BASE + '/'` を Playwright の `page.goto()` に渡します。`pictures-ui.mjs` では API 操作が `/api/model-providers` に、ブラウザー遷移が `/` に向かいます。値は文字列連結されるため、設定値には接続先のベース URL が必要です。たとえば空文字なら渡される URL 文字列は `/api/model-providers` または `/` です。末尾スラッシュを含む値はそのまま使われ、連結後に二重スラッシュになり得ます。

この名前について Strata のソースにログ、警告、明示的な終了処理、fallback はありません。API 呼び出しやページ遷移に失敗した場合、それらの呼び出しはこのスクリプト内で捕捉されず、失敗は呼び出し元へ伝播します。具体的なエラー文言やプロセス終了コードは Node.js / Playwright 側に依存するため、Strata の挙動としては断定しません。

## 根拠

- 候補一覧には名前があります（`docs/envvars/000_envvers.md:1602`）。
- 実際の読み取りと既定値: `apps/host/scripts/ui-drive.mjs:4`。
- 値を使う API とブラウザー遷移: `apps/host/scripts/ui-drive.mjs:6-8,16-21`。
- 確認できた利用元と throwaway host の前提: `apps/host/scripts/pictures-ui.mjs:1,5,23-24`。
- 候補名の他の直接参照は `apps/host/scripts/pictures-ui.mjs:1` の説明コメントです。ソース全体を候補名で検索した結果、環境から読み取る実装は `ui-drive.mjs:4` のみでした。
