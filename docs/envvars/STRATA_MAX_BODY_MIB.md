# `STRATA_MAX_BODY_MIB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリや driver 自身が読む環境変数の動作は対象外。

## 役割

`serve/server.py` の HTTP handler がメモリに読み込むリクエスト本文の上限を MiB 単位で変更します。既定上限は 256 MiB です。`Content-Length` で長さを示す本文と chunked transfer の本文の両方に適用し、上限超過時は本文を読み込まず HTTP 413 を返します。

## 値と判定

`body_limit()` が呼ばれるたびに `os.environ.get("STRATA_MAX_BODY_MIB", "0")` を Python の `int()` で変換します。基数指定のない整数文字列として変換できる値が対象です。前後の空白、符号、整数リテラル内のアンダースコアは Python の `int()` が受理しますが、小数、空文字、整数以外の末尾文字を含む値は `ValueError` となり既定値に戻ります。

| 環境値 | 結果 |
|---|---|
| 未設定、`0`、または負の整数 | 既定の 256 MiB |
| 正の整数 `N` | `N` MiB（`N << 20` bytes） |
| 空文字、整数として読めない文字列 | 既定の 256 MiB |

正の値に上限 clamp はありません。設定値は文字列全体を整数として解釈し、先頭文字だけを見る判定ではありません。

根拠: `serve/server.py:6078-6089`。

## 有効になる条件

この変数を読むのは Strata の Python HTTP server です。`body_limit()` は本文を読む `_body()` のたびに評価されるため、起動後の環境変更も後続の本文読み込みに反映されます。設定のキャッシュはありません。

`_body()` を使う POST の JSON 経路（推論 API、`/config`、`/settings` など）が対象です。`/load` と `/unload` は別の `_control_body()` 経路を使い、本文上限を固定 64 KiB として検査するため、この変数による上書きはありません (`serve/server.py:6733,6962-6995`)。ハンドラが本文を読まず応答した後の drain 処理では、chunked 本文には `body_limit()` が使われますが、`Content-Length` 本文は 5 秒の時間制限付きで最大 1 MiB ずつ読み捨てられ、同じサイズ上限では判定されません (`serve/server.py:6188-6219`)。

## 実行時の詳細

- `Content-Length` が上限より大きい場合、handler は本文を読まず接続を閉じる設定にし、413 と `the request body is larger than N MiB (STRATA_MAX_BODY_MIB raises the limit)` を返します。`N` は実際に適用された上限です。
- chunked 本文では、次の chunk の宣言サイズを累積量に加えた時点で上限超過を判定します。超過 chunk のデータを読む前に接続を閉じ、413 と `the request body is larger than N MiB` を返します。各 chunk は上限内なら最大 1 MiB ごとに読みます。
- `_body()` での本文エラーは `do_POST()` が `BadBody` を捕捉し、JSON の `invalid_request_error` として該当 status を返します。通常の POST 経路で本文が読み込まれる前に認証や admission 制御が応答した場合は、後処理で未読本文を drain します。chunked の drain が上限を超えた場合は接続を閉じます。

根拠: `serve/server.py:6128-6169,6171-6186,6188-6219,6714-6718`。

## 根拠

- 既定上限と環境値の parse: `serve/server.py:6078-6089`。
- chunked の累積サイズ検査、413 応答: `serve/server.py:6128-6169`。
- Content-Length の検査、本文読み込み前の 413: `serve/server.py:6171-6186`。
- 未読本文の drain と固定時間: `serve/server.py:6188-6219`。
- POST の `BadBody` 応答: `serve/server.py:6714-6718`。
- 固定 64 KiB の control body 経路: `serve/server.py:6962-6995`。

`docs/DETAILS.md` にこの変数の説明や条件付き測定値は見つかりませんでした。性能値は記載していません。
