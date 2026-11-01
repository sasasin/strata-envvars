# `NODE_ENV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のデスクトップアプリが App Host 用 Node プロセスを起動するとき、子プロセス環境に `NODE_ENV=production` を設定します。Strata 所有の本番コードに `NODE_ENV` を環境から読み取る箇所は見つかりませんでした。このため Strata 内の分岐を利用者が `NODE_ENV` で切り替える設定ではなく、起動する子プロセスへ固定値を渡す処理です。

## 値と判定

| 場面 | 設定内容 | 未設定・空文字・他の値 |
|---|---|---|
| デスクトップ App Host の起動 | 親プロセスの値にかかわらず、子プロセスの `NODE_ENV` を文字列 `production` に設定 | 親環境の値を読み取って判定・継承するコードはない。子プロセスには固定値が設定される |
| デスクトップ E2E スクリプト | 各テストが起動する Host に `production` を設定 | スクリプト内の固定設定であり、製品コードの値判定ではない |

文字列の parse、大小文字変換、許容値検査、無効値時の fallback は Strata 側にありません。Strata プロセス自身の環境値が未設定・空文字・別の値でも、製品コードの起動処理はその値を参照しません。

## 有効になる条件

`host_command()` は App Host の Node 実行ファイルと `server/index.mjs` を使うコマンドを組み立て、`NODE_ENV=production` を設定します。このコマンドを使う `start_host()` は `#[cfg(not(target_os = "linux"))]` で定義されているため、確認できた製品コード上の適用経路は Windows と macOS のデスクトップ起動です。Linux ではこの `start_host()` 経路はコンパイル対象になりません。

## 実行時の詳細

`host_command()` がコマンドを組み立てる際に設定し、`start_host()` がその後にコマンドを spawn します。したがって値は子プロセスの起動前に設定され、起動中に Strata が再読込・cache する処理はありません。Strata コードがこの値を読む、またはこの値に応じてログ、終了コード、失敗経路を変える箇所は確認できません。Node ランタイムや Host 側コードがこの値をどう扱うかは、本調査対象の Strata 所有コードからは説明しません。

候補一覧の名前を含む参照は、製品コードの上記設定に加えて `apps/desktop/scripts/vision-e2e.mjs:35`、`pics-e2e.mjs:37`、`installed-flow.mjs:115,130`、`cards-e2e.mjs:31`、`local-gguf-e2e.mjs:33` にあります。これらはテスト用スクリプトが E2E の Host に値を設定する箇所で、Strata の製品コードによる読み取りではありません。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:444-492`: Host 起動コマンドを作り、`NODE_ENV` を固定値 `production` に設定。呼び出し元環境の値を調べる処理はなく、`STRATA_SERVER_URL` のような別変数を明示的に転送する処理とも異なる。
- `apps/desktop/src-tauri/src/main.rs:495-515`: Windows/macOS 用 `start_host()` がコマンドを取得して spawn。
- `apps/desktop/scripts/vision-e2e.mjs:35`、`pics-e2e.mjs:37`、`installed-flow.mjs:115,130`、`cards-e2e.mjs:31`、`local-gguf-e2e.mjs:33`: テストスクリプトによる E2E Host 起動時の設定。
