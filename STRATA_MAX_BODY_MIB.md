# `STRATA_MAX_BODY_MIB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

Strata Python API サーバーが、通常の POST リクエスト本文を読み込む際の最大サイズを MiB 単位で設定します。対象は `Content-Length` 付き本文と chunked 本文です。既定の上限は 256 MiB です。上限を超えた本文は、本文を読み込む前または超過 chunk を読む前に拒否されます。

## 値と判定

`body_limit()` が `os.environ.get("STRATA_MAX_BODY_MIB", "0")` の値全体を Python の `int()` で変換します。変換時の `ValueError` は捕捉され、`0` として扱われます。

| 環境変数の値 | 本文上限 | 判定 |
|---|---:|---|
| 未設定 | 256 MiB | 既定文字列 `"0"` を変換し、正数でないため既定上限 |
| 空文字、整数以外、変換エラー | 256 MiB | `ValueError` を捕捉して既定上限 |
| 0 または負数 | 256 MiB | `mib > 0` でないため既定上限 |
| 正の整数 `n` | `n MiB`（`n << 20` bytes） | 上限を `n` MiB に変更。最大値の clamp はない |

`int()` による全体変換なので、先頭文字だけの判定ではありません。符号や前後の空白を含む整数表記は受け付けます。小数表記や整数以外の文字を含む値は変換エラーとなり、既定値に戻ります。

## 有効になる条件

`body_limit()` を呼ぶリクエスト処理に適用されます。設定値はモジュール読み込み時に固定されず、本文を読む `_body()` ごとに取得されます。認証拒否などで本文を使わず、chunked 本文を破棄する `_drain_body()` の経路でも読み直します。そのため、同じプロセス内で環境値が変更されれば後続の呼び出しに反映されます。

`/load` と `/unload` の制御 POST は `_control_body()` を通り、環境変数とは別に 64 KiB の固定上限を使います。`/v1/load` と `/v1/unload` は通常の JSON 本文を `_body()` で読むため、この変数の上限対象です。

## 実行時の詳細

`Content-Length` が上限を超える場合、`_body()` は本文を読み込まず接続を閉じる設定にし、413 と `the request body is larger than N MiB (STRATA_MAX_BODY_MIB raises the limit)` を返します。chunked 本文では、読み込んだ chunk の累計サイズが上限を超えた時点で、超過 chunk のデータを読む前に接続を閉じ、413 と `the request body is larger than N MiB` を返します。`do_POST()` が `BadBody` を捕捉して JSON の `invalid_request_error` として応答します。

この判定は通常の `_body()` が本文をメモリに読み込む経路に効きます。先に応答したリクエストの本文を後から破棄する経路では、chunked 本文には同じ上限を使います。一方、`Content-Length` 本文の破棄はメモリに保持せず最大 5 秒間読み進める処理で、ここでは `body_limit()` によるサイズ判定をしていません。

専用の起動ログや警告はありません。上限超過時の HTTP 応答が観測可能な結果です。

## 文書との照合

`docs/DETAILS.md` を含む `docs/` に、この変数の説明は見つかりませんでした。既定値とエラー時の fallback は `serve/server.py` の実装 docstring と処理から確認しました。docstring にある「100万 token の会話に余裕を持たせる」という説明は実装コメントの意図であり、独立に測定した値としては扱っていません。

## 根拠

- `serve/server.py:4561-4572` — 256 MiB の既定値、環境変数の取得、`int()` 変換、fallback、正数の MiB 変換。
- `serve/server.py:4610-4649` — chunked 本文の累計サイズ確認、上限超過時の 413、chunk データを読む前の判定。
- `serve/server.py:4653-4668` — 通常本文の上限確認、超過本文を読まずに 413 とする処理。
- `serve/server.py:4670-4701` — 先に応答した後の本文破棄。chunked と `Content-Length` での処理差、5 秒の時間制限。
- `serve/server.py:4985-4989,5026-5028` — `BadBody` を JSON 413 応答にし、通常の JSON POST で `_body()` を呼ぶ経路。
- `serve/server.py:5003-5004,5165-5198` — `/load`・`/unload` 制御 POST が独立した 64 KiB 上限を使う経路。
- `serve/server.py:5034-5036` — `/v1/load`・`/v1/unload` が通常の JSON POST 処理を通る箇所。
