# `STRATA_KEY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata 同梱の `tools/strata_bench.py` と `tools/serve_load.py` が、接続先サーバーへ送る API キーを得るための環境変数です。どちらもクライアント側の Bearer 認証ヘッダーに使います。Strata サーバー自身の API キー設定用環境変数ではありません。サーバー側は別名の `STRATA_API_KEY`、設定ファイルの `api_key`、または `--api-key` を扱います（`serve/server.py:6160-6161`）。

## 値と判定

| 呼び出し元 | 未設定 | 設定値 | CLI・設定ファイルとの優先順位 |
|---|---|---|---|
| `tools/strata_bench.py` | 空文字 | 文字列をそのまま取得。空文字かどうかだけを後段で判定し、数値化・形式検査・trim はしない | `--api-key` の既定値は環境変数。最終的には truthy な `--api-key`（既定値を含む）が優先し、空ならモデル設定 JSON の `api_key`、それも空なら空文字 |
| `tools/serve_load.py` | 空文字 | 文字列をそのまま取得。形式検査・trim はしない | `--key` が環境変数を既定値として受け取り、指定された CLI 値が優先。config fallback はない |

空文字（設定済みの場合も含む）はキーなしと同じ扱いになり、認証ヘッダーを付けません。空白だけの文字列は truthy なので、trim されず `Bearer <空白>` として送られます。`strata_bench.py` では `--api-key ""` も falsey となり、設定 JSON の `api_key` へ fallback します（URL 接続で設定 JSON を読んでいない場合は空になります）。

## 有効になる条件

- `tools/strata_bench.py` または `tools/serve_load.py` を実行する場合に限り、クライアント送信時の認証に使われます。環境変数は各スクリプトの `main()` が引数を解析するときに読み取られます。値を読み取った後の変更は、その実行中には再読込されません。
- `strata_bench.py` は、キー文字列が空でない場合に `/health`、サーバー情報取得、chat completion などのリクエストへ `Authorization: Bearer <key>` を付加します。空ならヘッダーを付加しません。HTTP サーバーがそのキーを受理するかどうかは接続先の設定によります。
- `serve_load.py` は `--key`（既定値 `STRATA_KEY`）を並列リクエスト関数に渡し、空でなければ同じ Bearer ヘッダーを付加します。
- `strata_bench.py` がモデル設定 JSON からサーバーを起動する場合、起動関数へ渡すのは設定ファイル、ポート、GPU です。`STRATA_KEY` は起動サーバーへ渡されず、ベンチマーククライアント側でのみ使われます。既存サーバーへの `--url` 接続でも同様に、クライアント側のキーです。

## 実行時の詳細

`strata_bench.py` は `main()` 内で `--api-key` の既定値を `os.environ.get("STRATA_KEY", "")` から取得し、設定ファイル読込後に `a.api_key or cfg.api_key or ""` で実際のキーを決めます。そのキーを readiness 確認、情報 API、ベンチマーク suite に渡します。HTTP helper と chat helper はキーが truthy のときだけ Authorization ヘッダーを作ります。レポートのサニタイザーにも同じキーを渡し、結果・ログに含まれるキー文字列の置換に使います。

`serve_load.py` は引数解析時に同じ環境変数を既定値として取得します。`one()` が各 `/v1/chat/completions` リクエストを作る際、キーが truthy ならヘッダーを追加します。

この名前は他に `tools/early_close_test.py` と `tools/stop_resend_test.py` にもありますが、いずれもサーバーの挙動を検査するテスト専用スクリプトです。ここでは実行アプリの設定根拠として扱っていません。

## 根拠

- `tools/strata_bench.py:832-849` は `--api-key` の環境変数既定値を定義し、`tools/strata_bench.py:858-881` は設定読込後の fallback とレポート用サニタイザーへのキー設定を行います。
- `tools/strata_bench.py:115-139, 566-570, 616-634` は HTTP/ chat リクエストへの Bearer ヘッダー付加と、そのキーを使う接続確認・情報取得を示します。`tools/strata_bench.py:893-897` はサーバー起動と readiness 確認の呼び出しを示します。
- `tools/serve_load.py:34-44` は各リクエストの Authorization ヘッダー条件、`tools/serve_load.py:83-98` は `--key` の環境変数既定値を示します。
- サーバー側の別変数は `serve/server.py:6160-6161`、`STRATA_KEY` を使うテスト専用スクリプトは `tools/early_close_test.py:4-9` と `tools/stop_resend_test.py:10-26` にあります。
