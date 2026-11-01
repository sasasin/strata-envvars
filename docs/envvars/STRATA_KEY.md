# `STRATA_KEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はなかった。

## 役割

`STRATA_KEY` は Strata の HTTP 負荷・ベンチマーク用クライアントが、既に起動している Strata サーバーへのリクエストに使う API キーの入力元です。`tools/serve_load.py` は `--key`、`tools/par_load.py` は `--key`、`tools/strata_bench.py` は `--api-key` の既定値として読みます。キーが空でなければ、これらのツールは HTTP `Authorization: Bearer <key>` ヘッダーを付けます。空ならヘッダーを付けません。

これは Strata サーバー本体の起動設定ではありません。サーバーは `STRATA_API_KEY` を読み、CLI `--api-key` や設定ファイルの `api_key` と組み合わせてサーバー側の認証キーを決めます（`serve/server.py:9013-9018, 9128-9142`）。`STRATA_KEY` を設定してもサーバー側のキーは変更されません。

## 値と判定

| ツール | 未設定・空文字 | 設定値と CLI の優先順位 | 利用方法 |
|---|---|---|---|
| `serve_load.py` | `os.environ.get(..., "")` により空文字相当。`--key` 未指定なら認証ヘッダーなし | `--key` を明示すると環境変数の値より優先。文字列をそのまま使う | `key` が truthy なら Bearer ヘッダーを付ける |
| `par_load.py` | 同じく空文字相当。`--key` 未指定なら認証ヘッダーなし | `--key` を明示すると環境変数の値より優先。文字列をそのまま使う | 各 chat request に、キーが truthy の場合 Bearer ヘッダーを付ける |
| `strata_bench.py` | `--api-key` の既定値は空文字。続いて設定ファイルの `api_key` を fallback として使う | 非空の `--api-key`（既定値は `STRATA_KEY`）が設定ファイルより優先。空文字の場合は設定ファイルの値へ fallback | サーバー確認・ready 待ち・HTTP API 呼び出しの Bearer 認証に使う |

環境変数は全体を parse せず、文字列として取得します。空白除去、形式検査、長さ制限はこれらの読み取り箇所にはありません。`serve_load.py` と `par_load.py` では環境変数が空文字の場合と未設定の場合は同じです。明示した `--key ""` も空のためヘッダーを付けません。`strata_bench.py` は `a.api_key or cfg.api_key or ""` の truthiness 判定なので、環境変数または `--api-key` が空文字なら設定ファイルの `api_key` に fallback します。設定ファイルが読み込まれていない場合は空文字です。

## 有効になる条件

- 対象は上記 Python クライアントツールを実行した場合です。サーバー本体の推論設定、OS、GPU backend、build macro、モデル状態には `STRATA_KEY` による分岐はありません。
- キーが空でなければツールが Bearer ヘッダーを送ります。キーが空なら認証なしで送信します。サーバーが認証を要求しているか、そのキーを受け付けるかはサーバー側の設定次第です。
- `strata_bench.py` がサーバーを起動する場合も、この値は起動したサーバーのキーを設定せず、ベンチマーククライアントの認証に使われます。サーバー側の起動キーには `STRATA_API_KEY`、CLI、設定ファイルが関係します（`serve/server.py:9013-9018, 9134-9139`）。

## 実行時の詳細

3 ツールとも `argparse` の引数 default を作る時点で `os.environ.get("STRATA_KEY", "")` を評価します。以後は引数オブジェクト上の値をリクエスト処理に渡すため、実行中にプロセス環境を変更しても再読込されません。`strata_bench.py` が `subprocess.Popen` でサーバーを起動するとき `env` を指定していないため、子プロセスには通常のプロセス環境が継承されますが、サーバーコードが認証キーとして読むのは `STRATA_API_KEY` です（`tools/strata_bench.py:771-788`; `serve/server.py:9013-9018`）。

`serve_load.py` は各リクエストで `key` が真なら Bearer ヘッダーを設定します。HTTP/接続エラーはワーカースレッド内で捕捉され、各ラウンドの `ERRORS` 表示と集計の `errors` に現れます（`tools/serve_load.py:34-72, 110-123, 138-151`）。このツールの終了コードは比較結果の差分に基づき、認証エラーだけでは失敗コードにしません（同 `:154-160`）。

`par_load.py` は同じ条件で各リクエストに Bearer ヘッダーを設定します。非 200 応答はエラーとして記録され、ledger の `errors` に数えられます。最終的に要求エラーがある場合は終了コード 1 です（`tools/par_load.py:131-149, 530-540`）。

`strata_bench.py` は決定したキーを readiness 確認、サーバー識別、API リクエストに渡します。`--url` で既存サーバーを指定して応答が Strata と認識されない場合は `No Strata server answers at ...` を stderr に出して 2 で終了します。ローカル起動時も別途起動したサーバーが設定したキーとの一致が必要です（`tools/strata_bench.py:116-141, 1020-1027, 1061-1087`）。

## 根拠

- `tools/serve_load.py:84-99` — `STRATA_KEY` の取得と `--key` 引数。`:34-43` は Bearer ヘッダー条件、`:70-72, 138-160` はエラー集計と終了処理。
- `tools/par_load.py:471-505` — `STRATA_KEY` の取得と `--key` 引数。`:121-149` は Bearer ヘッダーと HTTP エラー処理、`:530-540` は ledger と終了コード。
- `tools/strata_bench.py:1020-1027` — `STRATA_KEY` の取得と `--api-key` 引数。`:1061-1087` は設定ファイル fallback、キーの利用、接続失敗時の出力・終了経路。`:116-141` は HTTP Bearer ヘッダー。
- `serve/server.py:9013-9018, 9128-9142` — サーバー起動時に読むのは別の `STRATA_API_KEY` であり、CLI / 設定ファイルとの選択・検証もサーバー側で行う。

候補名の全参照検索では、`tools/early_close_test.py` と `tools/stop_resend_test.py` にも読み取りが見つかりましたが、どちらもテスト専用スクリプトのため本番動作の根拠には含めていません。`bench/results/` の過去測定スクリプト・記録、文書中の例示も同様に実装根拠から除外しました。Docker の `STRATA_KEY_FILE` は別名の環境変数です。
