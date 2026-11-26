# `STRATA_MAX_BODY_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の Python HTTP サーバーが、通常の POST リクエスト本文をメモリに読み込める上限を MiB 単位で変更します。既定値は 256 MiB で、正の整数を設定するとその整数 MiB が上限になります。Content-Length が上限を超える場合は本文を読み込む前に HTTP 413 を返し、chunked body はチャンクを読む前に累積サイズを検査して超過時に 413 を返します。[`terminal/serve/server.py:7002-7013`](../../../../Niko1221/Strata/terminal/serve/server.py#L7002-L7013) [`terminal/serve/server.py:7045-7077`](../../../../Niko1221/Strata/terminal/serve/server.py#L7045-L7077) [`terminal/serve/server.py:7088-7103`](../../../../Niko1221/Strata/terminal/serve/server.py#L7088-L7103)

## 値と判定

`body_limit()` はリクエスト本文を読むたび `os.environ.get("STRATA_MAX_BODY_MIB", "0")` を呼び、得た文字列全体を Python の `int()` で変換します。変換時に `ValueError` となる値は `0` 扱いです。変換結果が正なら `mib << 20` bytes、0 以下なら `256 << 20` bytes を返します。したがって空文字も既定値になり、正の範囲にコード上の上限はありません。[`terminal/serve/server.py:7002-7013`](../../../../Niko1221/Strata/terminal/serve/server.py#L7002-L7013)

| 条件 | 未設定 | 有効になる値（例） | 既定値になる値（例） |
|---|---|---|---|
| `body_limit()` を使うサーバー経路 | `"0"` と同じ扱いで 256 MiB | `"1"` → 1 MiB、`"256"` → 256 MiB、`"+2"` → 2 MiB | 空文字、`"0"`、`"-1"`、`"junk"`、`"1.5"`、`"1MiB"` → 256 MiB |

`int()` は文字列全体を整数として変換するため、数値の後ろに単位などが続く値は受け付けません。前後の空白や符号付き整数は変換可能です。正の値を変換できれば範囲 clamp はありません。Python 整数の実装上の変換エラーは `ValueError` のみ既定値へフォールバックし、それ以外の資源不足等はこの関数で処理していません。[`terminal/serve/server.py:7009-7013`](../../../../Niko1221/Strata/terminal/serve/server.py#L7009-L7013)

## 有効になる条件

- Strata の Python HTTP サーバーが `body_limit()` を通る本文処理を実行すること。`_body()` は通常の POST API 本文の Content-Length / chunked 読み取りに使われます。[`terminal/serve/server.py:7088-7103`](../../../../Niko1221/Strata/terminal/serve/server.py#L7088-L7103) [`terminal/serve/server.py:7725-7730`](../../../../Niko1221/Strata/terminal/serve/server.py#L7725-L7730)
- 認証失敗など、応答前に本文を消費していない経路の chunked body 破棄にも同じ上限が渡されます。Content-Length の破棄経路は最大 5 秒だけ読み捨て、環境変数上限を検査しません。[`terminal/serve/server.py:7024-7025`](../../../../Niko1221/Strata/terminal/serve/server.py#L7024-L7025) [`terminal/serve/server.py:7105-7136`](../../../../Niko1221/Strata/terminal/serve/server.py#L7105-L7136)
- `/load` と `/unload` の制御本文は `_control_body()` が独自に 64 KiB に制限するため、この環境変数の上限は適用されません。[`terminal/serve/server.py:7744`](../../../../Niko1221/Strata/terminal/serve/server.py#L7744) [`terminal/serve/server.py:8004-8037`](../../../../Niko1221/Strata/terminal/serve/server.py#L8004-L8037)
- CLI 引数、設定ファイル、他の環境変数との優先順位はありません。コード上この値を上書きする経路はなく、実行ファイルの build/backend 条件による分岐もありません。[`terminal/serve/server.py:7005-7013`](../../../../Niko1221/Strata/terminal/serve/server.py#L7005-L7013)

## 実行時の詳細

値はサーバープロセス起動時に cache されず、各 `_body()` 呼び出し時に読み直されます。未読本文を破棄する chunked 経路でも `body_limit()` が呼ばれます。したがって同じプロセスで環境値が変更された後の呼び出しは新しい値を読みますが、すでに開始した本文読取の上限はその読み取り時に得た値です。[`terminal/serve/server.py:7005-7013`](../../../../Niko1221/Strata/terminal/serve/server.py#L7005-L7013) [`terminal/serve/server.py:7088-7092`](../../../../Niko1221/Strata/terminal/serve/server.py#L7088-L7092) [`terminal/serve/server.py:7112-7118`](../../../../Niko1221/Strata/terminal/serve/server.py#L7112-L7118)

Content-Length は整数に変換され、負数や不正値は 400（`invalid Content-Length`）、上限超過は接続を閉じる設定をしたうえで 413 となり、本文を読みません。chunked body は各チャンクサイズを加算し、累積値が上限を超えると接続を閉じて 413 になります。通常 POST の `do_POST()` は `BadBody` の status とメッセージを JSON error にして返します。本文を先に読まずに応答した chunked 破棄処理では、不正 body または I/O エラー時に接続を閉じます。[`terminal/serve/server.py:7093-7103`](../../../../Niko1221/Strata/terminal/serve/server.py#L7093-L7103) [`terminal/serve/server.py:7073-7086`](../../../../Niko1221/Strata/terminal/serve/server.py#L7073-L7086) [`terminal/serve/server.py:7725-7730`](../../../../Niko1221/Strata/terminal/serve/server.py#L7725-L7730) [`terminal/serve/server.py:7112-7120`](../../../../Niko1221/Strata/terminal/serve/server.py#L7112-L7120)

## ログと測定値

Content-Length 超過のエラー本文は `the request body is larger than <N> MiB (STRATA_MAX_BODY_MIB raises the limit)`、chunked body 超過は `the request body is larger than <N> MiB` です。`N` は適用中の上限を MiB に戻した値です。`do_POST()` がこの文言を HTTP 413 の JSON error に格納します。変数設定自体を報告する起動ログはこの処理にありません。[`terminal/serve/server.py:7073-7077`](../../../../Niko1221/Strata/terminal/serve/server.py#L7073-L7077) [`terminal/serve/server.py:7099-7102`](../../../../Niko1221/Strata/terminal/serve/server.py#L7099-L7102) [`terminal/serve/server.py:7725-7730`](../../../../Niko1221/Strata/terminal/serve/server.py#L7725-L7730)

## 根拠

- `terminal/serve/server.py:7002-7013` — 既定上限、環境値の変換と fallback。
- `terminal/serve/server.py:7045-7086` — chunked body の累積上限、超過・不正時の応答経路。
- `terminal/serve/server.py:7088-7136` — Content-Length の検査、本文読取、および未読 body の破棄。
- `terminal/serve/server.py:7725-7730` — `BadBody` を HTTP status と JSON error にする処理。
- `terminal/serve/server.py:8004-8037` — `/load`・`/unload` の固定 64 KiB 制御本文処理。
