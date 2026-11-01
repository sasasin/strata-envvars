# `CHROME_BIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱のブラウザテストと Web ページのスクリーンショット用スクリプトが、Puppeteer 起動時に使用する Chrome / Edge の実行ファイルパスを指定します。Strata サーバーやモデル推論の実行設定ではありません。読み取り箇所は `tools/webtest/lib.mjs` だけです。同ファイルは `tools/webtest/browser_test.mjs` と `tools/webtest/shots.mjs` から読み込まれます。

## 値と判定

環境変数を文字列として読み、数値や真偽値には変換しません。設定値は候補リストの先頭に加えられますが、空文字列は `.filter(Boolean)` で取り除かれます。`fs.existsSync()` が true となる最初の候補が実行ファイルパスとして選択されます。

| `CHROME_BIN` の状態 | 判定と結果 |
|---|---|
| 未設定 | 環境変数由来の候補はなく、ハードコードされたパスを順に探す |
| 空文字列 | falsy 値として候補リストから除かれ、未設定と同じく既定候補を探す |
| 空でない値、そのパスが存在する | そのパスが既定候補より先に選ばれる |
| 空でない値、そのパスが存在しない | その候補は選ばれず、後続の既定候補を探す |
| いずれの候補も存在しない | `Error("no Chrome or Edge found; set CHROME_BIN")` を throw する |

文字列全体の形式、実行権限、ファイル形式、ブラウザであることは事前検証しません。空白だけの値も空文字ではないため候補に残りますが、そのパスが存在しなければ無視されます。`existsSync` による存在確認だけで選ぶため、存在するが実行できないパスや Puppeteer が起動できないファイルを指定すると、そこで選択が止まり `puppeteer.launch()` の失敗になります。相対パスは Node プロセスの作業ディレクトリを基準に `existsSync()` で確認されます。

既定候補は次の固定パスです（OS ごとの分岐ではなく、同じ配列を順番に検査します）。

1. `C:/Program Files/Google/Chrome/Application/chrome.exe`
2. `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`
3. `/usr/bin/google-chrome`
4. `/usr/bin/chromium`
5. `/usr/bin/chromium-browser`
6. `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`

PATH 検索や別の環境変数との優先順位処理はありません。指定値のパスが存在すれば固定候補すべてより優先され、存在しなければ既定候補へフォールバックします。

## 有効になる条件

`tools/webtest/browser_test.mjs` または `tools/webtest/shots.mjs` を Node.js で実行し、共通ヘルパーが import される経路でのみ関係します。これらはモックサーバーを使うブラウザテストとスクリーンショット用で、モデルや GPU を必要としません。実行手順は `docs/DETAILS.md:810-812` に記載されています。

ブラウザテストを Python のテストラッパー経由で実行する場合、ラッパーは Node スクリプトを `subprocess.run()` で起動します。別途環境を置き換えるコードはなく、プロセス環境は通常どおり子プロセスへ継承されます。Python 側では `WEBTEST_MODULES` の設定と `node` の有無を見てブラウザテストを skip するか決めますが、`CHROME_BIN` 自体は Node の共通ヘルパーが読みます（`serve/test_web_history.py:107-115`, `serve/test_web_preview.py:69-75`）。

## 実行時の詳細

`tools/webtest/lib.mjs` のモジュール評価時に `process.env.CHROME_BIN` を一度読み、候補配列を作ります。したがって、その Node プロセスでモジュールを import した後に環境を書き換えても、候補配列は更新されません。`chrome()` は `launch()` の呼び出し時に候補の存在を確認します。`browser_test.mjs` はモックサーバーを起動してからブラウザを起動し、`shots.mjs` も同じ共通 `launch()` を使います（`tools/webtest/browser_test.mjs:649-650`, `tools/webtest/shots.mjs:8-9`）。

全候補が見つからない場合は上記の Error が投げられます。候補パスの存在確認や `puppeteer.launch()` を捕捉する処理は呼び出し側にないため、スクリプトのトップレベルで起きた場合は未捕捉例外として Node 実行が失敗します。存在するパスを選んだ後の起動成否は Puppeteer 起動に委ねられます。起動オプションは `headless: true`、`--no-sandbox`、`--disable-gpu` です（`tools/webtest/lib.mjs:14-19`）。Strata 自身がこれらのフラグの Chrome 内部動作を制御・検証するものではありません。

## 根拠

- `tools/webtest/lib.mjs:11-19` — 環境値の読み取り、候補順、空値除外、存在確認、候補なしの例外、Puppeteer の起動。
- `tools/webtest/browser_test.mjs:1-4,649-650` — モック相手のブラウザテスト用途と起動順。
- `tools/webtest/shots.mjs:1-9` — スクリーンショット用途と共通ブラウザ起動。
- `serve/test_web_history.py:107-115`, `serve/test_web_preview.py:69-75` — Python ラッパーによる Node ブラウザテスト起動。skip 条件は `WEBTEST_MODULES` と Node の有無。
- `docs/DETAILS.md:810-812` — ブラウザテストとスクリーンショットの案内。
