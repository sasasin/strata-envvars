# `CHROME_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`CHROME_PATH` は `apps/host/scripts/pictures-ui.mjs` の UI 補助スクリプトが使うブラウザー実行ファイルのパスです。ホスト UI の本体サーバーや Strata エンジンの設定としては参照されていません。スクリプトは `ui-drive.mjs` の `open()` を呼び、そこでこの値を Playwright の `launch()` オプション `executablePath` に渡します（`apps/host/scripts/pictures-ui.mjs:1,5,23-24`; `apps/host/scripts/ui-drive.mjs:1-5,16-18`）。

## 値と判定

| 環境値 | `CHROME` に使われる値 |
|---|---|
| 未設定 | `C:/Program Files/Google/Chrome/Application/chrome.exe` |
| 空文字 | 空文字のまま |
| その他の文字列 | その文字列のまま |

実装は `process.env.CHROME_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'` です。nullish coalescing による未設定時の既定値だけで、空文字判定、パスの存在確認、正規化、文字列変換、範囲判定、無効値時の再試行や別パスへの fallback はありません（`apps/host/scripts/ui-drive.mjs:5`）。既定値は Windows 形式の固定パスで、OS に応じて選び直す分岐もありません。

## 有効になる条件

`apps/host/scripts/pictures-ui.mjs` を実行し、`open()` が呼ばれる経路で使われます。同ファイルの先頭コメントは使い捨てホストとテスト用 scripted worker を前提としており、そこで UI の画像添付フローを操作します（`apps/host/scripts/pictures-ui.mjs:1,23-24`）。共有 helper の `ui-drive.mjs` はリポジトリ内でこのスクリプトから import されています。

`apps/host/package.json` には `playwright-core` が開発依存として記載されていますが、`pictures-ui.mjs` 用の package script はありません（`apps/host/package.json:7-27,37-45`）。通常のアプリサーバー起動や CLI 引数による上書きのコードは見つかりませんでした。`STRATA_UI_BASE` は同じ helper 内でホスト URL を指定する別設定で、`CHROME_PATH` の値や優先順位には関与しません（`apps/host/scripts/ui-drive.mjs:4-5`）。

## 実行時の詳細

値は `ui-drive.mjs` の ES module 評価時に `CHROME` 定数へ一度取り込まれます。そのモジュールの読み込み後に環境値を変更しても、この定数は再評価されません。`open()` はその定数を `browserType.launch({ executablePath: CHROME, headless: true })` に渡します（`apps/host/scripts/ui-drive.mjs:3-5,16-18`）。Strata 側にパスの検査や `launch()` のエラーを捕捉する処理はこの helper にはありません。起動失敗時の具体的な表示・終了動作は呼び出し先ライブラリと Node.js に委ねられており、本調査では Strata 固有のログや fallback として確認できるものはありません。

## 根拠

候補名の全参照を Strata リポジトリ全体で `rg -n --hidden --glob '!.git/**' 'CHROME_PATH'` により確認しました。コード上の参照は `apps/host/scripts/ui-drive.mjs:1,5` のみで、1 行目は用途のコメント、5 行目は実際の環境読み取りです。読み取り値の渡し先と唯一の import 元も追跡しました（`apps/host/scripts/ui-drive.mjs:16-18`; `apps/host/scripts/pictures-ui.mjs:5,23-24`）。
