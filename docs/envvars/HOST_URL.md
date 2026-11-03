# `HOST_URL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/load-pictures-e2e.mjs` が操作対象にする、起動済み Strata Host の URL です。この変数を読むのは、Models ページ上でモデルの Load 操作を行う実 Chrome E2E スクリプトだけです。Strata の通常の CLI やサーバー設定が読む変数ではありません（`apps/host/scripts/load-pictures-e2e.mjs:3-12,19-20`）。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `HOST` は `undefined` となり、標準エラーに `HOST_URL is required` を出して終了コード 2 で終了します。 |
| 空文字 | `!HOST` に該当し、未設定と同じエラー・終了になります。 |
| その他の文字列 | そのまま URL の接頭部として使われます。URL の形式、scheme、host、末尾の `/` は検証・正規化されません。 |

値は `process.env.HOST_URL` からモジュール評価時に一度読み、`const HOST` に保持されます。CLI 引数や別の設定値による上書き経路はありません（`apps/host/scripts/load-pictures-e2e.mjs:19-20`）。

## 有効になる条件

この変数の読み取りは、Node.js で `apps/host/scripts/load-pictures-e2e.mjs` を実行した場合に限られます。E2E スクリプト内で Chrome を起動し、DevTools 経由で `${HOST}/#/models` に移動します。リポジトリ内では、このスクリプト以外に `HOST_URL` を環境から読む箇所は見つかりませんでした（`apps/host/scripts/load-pictures-e2e.mjs:19-20,29-30,48-50`）。

## 実行時の詳細

`HOST_URL` の値は起動時に固定され、後からプロセス環境を変更しても再読込されません。値を `Page.navigate` に渡す際、スクリプトは文字列 `${HOST}/#/models` を組み立てます。そのページの Load ボタンが有効になるのを待って操作し、処理が終わると記録を出力します（`apps/host/scripts/load-pictures-e2e.mjs:19,40,48-55,59-83`）。

未設定または空文字なら起動時に標準エラーへ必須エラーを出して終了コード 2 になります。その他の値でも Chrome の起動失敗、DevTools 接続失敗、ページやボタンの問題などで例外が発生し得ます。例外経路ではエラーメッセージを標準エラーに出し、`OUT/error.txt` に stack またはエラー文字列を書き、終了コード 2 で終了します。ボタンが現れない場合はスクリーンショット `never-ready.png` を保存して例外経路に入ります（`apps/host/scripts/load-pictures-e2e.mjs:33-45,54-55,84-87`）。不正な URL 文字列を個別に判定する処理はありません。

## 根拠

- `apps/host/scripts/load-pictures-e2e.mjs:3-12` — E2E 用途と `HOST_URL` を必須とする説明。
- `apps/host/scripts/load-pictures-e2e.mjs:19-20` — 環境からの読取、空値を含む必須判定、エラーと終了コード。
- `apps/host/scripts/load-pictures-e2e.mjs:29-30,33-45,48-55,59-87` — Chrome / DevTools 操作、URL の組み立て、観測可能な失敗経路。
