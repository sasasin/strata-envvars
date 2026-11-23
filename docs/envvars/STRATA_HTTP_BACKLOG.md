# `STRATA_HTTP_BACKLOG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata の HTTP サーバー実装 `serve.server_parts.http_api.Server` が持つ `request_queue_size` クラス属性を設定する。クラスは `http.server.ThreadingHTTPServer` を継承し、Strata はこの属性を未設定時 256、設定時は整数変換後の最低 5 にする。これは Strata がサーバーのクラス属性へ与える値の説明であり、Python 標準ライブラリや OS がその値をどう扱うかの詳細はここでは扱わない（`terminal/serve/server_parts/http_api.py:37-44`）。

通常の Strata サーバー起動時にこの `Server` が作られる（`terminal/serve/server.py:8263-8269, 9182`）。HTTP サーバーの待受キュー設定に関する値であり、モデル設定や生成処理を直接変更するコードは確認できない。

## 値と判定

式は `max(5, int(os.environ.get("STRATA_HTTP_BACKLOG") or 256))`。環境変数が未設定の場合 `get()` は `None`、空文字の場合も `or 256` により 256 となる。空文字以外は Python の `int()` で文字列全体を変換し、その結果を最低 5 に clamp する（`terminal/serve/server_parts/http_api.py:44`）。

| 条件 | 未設定 | 有効になる値・例 | 無効になる値・例 |
|---|---:|---|---|
| HTTP サーバーモジュールの import | `None` から 256 | 整数に変換できる文字列。`1`、`5`、`256` はそれぞれ 5、5、256。`0` や `-3` も変換できるが結果は 5 | 空文字は無効化ではなく既定値 256。`true`、`0anything`、空白だけの文字列など `int()` が変換できない値は無効で、`ValueError` になる |

`int()` は数値の範囲を個別に検証しない。前後の空白や符号を含む整数表記は変換でき、変換後の値が 5 未満なら 5 になる。小数表記や整数の後ろに余分な文字が付いた表記は変換できない。大文字小文字の比較は行わない（`terminal/serve/server_parts/http_api.py:44`）。

## 有効になる条件

- `serve.server_parts.http_api` が import されて `Server` クラスが定義される実行経路で評価される。`serve.server` はこのクラスを import し、CLI のサーバー起動経路で `serve()` が `Server` を生成する（`terminal/serve/server.py:250-263, 8263-8269, 9182`）。
- CLI 引数や設定ファイルによる同じ値の上書きは見つからない。環境値が変換可能であれば `request_queue_size` はクラス定義で決まり、5 未満の値は 5 になる（`terminal/serve/server_parts/http_api.py:44`）。
- OS / GPU backend / build macro / モデル状態による分岐はこの読み取り箇所にはない（`terminal/serve/server_parts/http_api.py:37-49`）。

## 実行時の詳細

`os.environ.get()` は `Server` クラス本体の評価時に一度呼ばれ、その結果はクラス属性 `request_queue_size` に保存される。`serve()` がそのクラスを使って HTTP サーバーを生成する。リクエストごとの読み直しや、プロセス起動後の環境変更を反映するコードはない（`terminal/serve/server_parts/http_api.py:37-49`; `terminal/serve/server.py:8263-8269`）。

不正な非空文字列は `int()` の `ValueError` を発生させる。`server.py` は `http_api` から `Server` を import するため、この場合はサーバー起動処理が `Server` を作る段階より前、モジュール import 時に失敗する（`terminal/serve/server.py:250-263`; `terminal/serve/server_parts/http_api.py:44`）。

## ログと測定値

この変数の値を表示する専用ログや、変換失敗を捕捉して出す警告は実装されていない。無効な整数表記は `ValueError` として import 呼び出し元へ伝播する（`terminal/serve/server_parts/http_api.py:44`; `terminal/serve/server.py:250-263`）。

実装コメントは、既定の listen backlog 5 では 30〜40 クライアントの同時接続時に接続リセットが起きた経験（4 枚の R9700、1 リクエストずつの場合にも発生）と、既定値を 256 にする意図を記している。これはコメントに記録された背景であり、この調査で再測定した値ではない（`terminal/serve/server_parts/http_api.py:41-44`）。

## 根拠

- 読み取り・変換・既定値・下限・クラス属性: `terminal/serve/server_parts/http_api.py:37-49`
- `Server` の import: `terminal/serve/server.py:250-263`
- サーバー生成と起動: `terminal/serve/server.py:8263-8269, 9182`
