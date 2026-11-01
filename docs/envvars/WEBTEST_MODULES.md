# `WEBTEST_MODULES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata の開発用ブラウザテストと Web UI のスクリーンショット用 Node スクリプトが、リポジトリ外に置いた `puppeteer-core` を読み込む際の探索起点を指定します。アプリ、通常の Web サーバー、エンジンの実行時設定ではありません。

## 値と判定

| 値 | Strata の処理 |
|---|---|
| 未設定 | `process.cwd()` を探索起点にする |
| 空文字 | JavaScript の `||` により未設定と同じく `process.cwd()` を使う |
| 空でない文字列 | その文字列を `noop.js` の親ディレクトリとして `createRequire` に渡す。その起点から `puppeteer-core` を require する |

文字列の内容検証、数値変換、大小文字変換、範囲制限、CLI 引数による上書きはありません。通常は `node_modules` を含むディレクトリを指定します。相対パスを絶対パスへ変換する処理もありません。指定値でモジュールを解決できない場合に備えた Strata 独自の fallback やエラー処理はありません。

## 有効になる条件

この値を実際に使うのは `tools/webtest/lib.mjs` を読み込む Node スクリプトです。`browser_test.mjs` はブラウザテストを起動し、`shots.mjs` はスクリーンショットを取得します。どちらも共通ライブラリを import します。Chrome または Edge の実行ファイルは別の `CHROME_BIN` と候補パスから探されるため、`WEBTEST_MODULES` はブラウザ実行ファイルを指定しません。

Python の `serve/test_web_preview.py` と `serve/test_web_history.py` にもテスト用の起動条件があります。ここでは `os.environ.get("WEBTEST_MODULES")` が真で、かつ `node` が PATH 上にある場合だけブラウザテストのクラスを実行します。そのため空文字はこの Python 側の条件を満たしません。変数が非空でも Node が見つからなければクラスは skip されます。これらはテスト専用の参照で、通常のサーバー処理ではありません。

## 実行時の詳細

Node 共通ライブラリは import 時に `process.env.WEBTEST_MODULES` を読み、`createRequire(path.join(value または process.cwd(), "noop.js"))` を作ります。その後 `req("puppeteer-core")` をモジュール初期化時に実行します。したがって、このモジュールを import した後に環境変数を書き換えても、作成済みの require 起点は再評価されません。子プロセスを起動する場合、Node 自体は起動時の環境を受け取ります。Python テストからの `subprocess.run` は `env` を明示しておらず、Python プロセスの環境を継承します。

Strata のコードには、依存モジュールの読み込みを捕捉して独自メッセージを出す処理はありません。解決に失敗したときの詳細な例外・終了結果は Node のモジュール解決に委ねられます。ブラウザ実行ファイルが見つからない場合は別経路で `no Chrome or Edge found; set CHROME_BIN` という例外を投げます。

## 根拠

- `tools/webtest/lib.mjs:1-9` は用途をブラウザテストとスクリーンショットと説明し、環境値を読み、探索起点を組み立てて `puppeteer-core` を読み込みます。
- `tools/webtest/lib.mjs:11-19` は別変数 `CHROME_BIN` と固定候補によるブラウザ探索、およびブラウザ未発見時の例外を実装しています。
- `tools/webtest/browser_test.mjs:1-9,649` はブラウザテストから共通ライブラリを import し、末尾で mock server とブラウザを起動します。
- `tools/webtest/shots.mjs:1-9` はスクリーンショット用スクリプトでも同じ共通ライブラリを使います。
- `serve/test_web_preview.py:69-75` と `serve/test_web_history.py:107-115` は、非空の環境値と `node` の有無をテスト起動条件にし、Node 子プロセスを起動します。
- `docs/DETAILS.md:810-812` はブラウザテストとスクリーンショットスクリプトを開発用テストとして案内しています。コード上も `WEBTEST_MODULES` を読む箇所は `tools/webtest/lib.mjs` と上記テスト専用ゲートに限られ、アプリやサーバーの通常経路からの読み取りは確認できません。
