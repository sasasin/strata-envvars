# `STRATA_VISION_ENCODE_S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Terminal のサーバーモードで、別プロセスの画像 encoder に `ENC` コマンドを送った後、その応答行を待つ上限時間を秒単位で指定する。未設定時は 300 秒。上限に達するとサーバーは encoder を kill し、画像読み取りのエラーとして要求側へ返す。モデルの推論時間や encoder の起動時 `READY` 待ちには使われない（後者は別の `STRATA_VISION_READY_S`）。読み取り元は `terminal/serve/server_parts/base.py` の `_timeout_env`、利用箇所は `terminal/serve/server.py` の `Vision.encode`（同ファイル:272-277, 460-462, 3476-3512）。

## 値と判定

`_timeout_env` は `os.environ.get(name, default)` の結果を Python `float()` に渡す。未設定時と `float()` が `ValueError` を出す文字列は既定値に戻る。変換後の値が `<= 0` なら `None` にし、`Vision._readline` の待ち時間として渡す。正の値は秒数としてそのまま使い、範囲制限や丸めはしない（`terminal/serve/server_parts/base.py:272-277`）。

| 条件 | unset | 有効になる値の例 | 無効値・特殊値の例 |
|---|---|---|---|
| Terminal サーバーの別プロセス画像 encoder | 300 秒 | `0.5`、`1e2`、前後に空白のある ` 2 ` はそれぞれ float 変換後の正の秒数 | 空文字、`abc`、`1s`、`0anything` は変換失敗で 300 秒。`0`、`-1`、`-0.0` は無期限待ち（`None`） |

空文字は「設定済み」扱いで有効になるのではなく、`float("")` が失敗するため既定値になります。`float()` 後に有限値かどうかは検査しないため、`nan` や `inf` も `<= 0` 判定を通り、値のまま待ち関数へ渡されます。これらの特殊値に対する実行結果は Strata 側で別途規定・処理していません（同:272-277、`terminal/serve/server.py:3307-3327`）。

## 有効になる条件

- `terminal/serve` のサーバープロセスで、設定に別プロセスの `vision` encoder があり、画像が未キャッシュで encode されるときに適用される。`Vision.encode` は `ENC` を送って応答を待つ（`terminal/serve/server.py:3032-3036, 3481-3496`）。
- 設定に画像 encoder がない場合、画像がすでに画像ハッシュの cache にある場合、または Hy4-Flash / Inkling-2-Mini が engine 内で画像を処理する場合、この変数による encoder 応答待ちは発生しない（同:4606-4611, 3485-3487, 5554-5569）。
- `--lazy` や vision の `elastic` 設定は encoder の起動時期を変えるが、この待ち時間の既定値や値の判定は変えない（同:3059-3089）。
- この値を上書きする CLI 引数、設定ファイル項目、別環境変数は、調査対象ソースの該当経路にはない。サーバー起動時に環境から読み込んだ値を `VISION_ENCODE_S` 定数として使う。

## 実行時の詳細

`server.py` の import 時に `_timeout_env("STRATA_VISION_ENCODE_S", 300.0)` が一度評価され、`VISION_ENCODE_S` に保持される。そのためプロセス起動後に環境変数を変更しても、定数の値は再読込されない（`terminal/serve/server.py:460-462`）。encoder を起動し直しても同じ定数が使われる。

`Vision.encode` は画像を正規化して SHA-256 のキーを作り、cache にあれば encoder を呼ばずに既存結果を返す。cache にない画像は `.img` を作り、encoder の stdin に `ENC <画像名> <出力名>` を書いて flush した後、`_readline(VISION_ENCODE_S, ...)` で 1 行を待つ。encoder が `ERR cannot read the image` を返し、正規化の再試行が必要な場合は、再送した 2 回目の応答待ちにも同じ timeout を個別に適用する（`terminal/serve/server.py:3481-3503`）。

待ちが期限切れになると `_readline` は encoder プロセスを kill し、`the image could not be read: it said nothing for N s` という `RuntimeError` を作る。`Vision.encode` は encoder を stopped 扱いにし、同じメッセージの `ValueError` に変換する。画像を含む通常要求ではこの例外が要求処理へ伝わる。ツールが返した画像の事前確認経路では例外を捕捉し、画像を prompt から省いたことを `[strata] a picture a tool returned was left out of the prompt: ...` と出力して、その画像をテキスト注記に置き換える。タイムアウト自体を報告する専用ログはなく、ツール画像経路の上記警告は出る（同:3307-3327, 3503-3511, 5481-5516）。

## 根拠

- `terminal/serve/server_parts/base.py:272-277` — 変数名を受け取る helper の変換、fallback、ゼロ以下の扱い。
- `terminal/serve/server.py:439-462` — timeout の説明コメントと import 時の定数設定。
- `terminal/serve/server.py:3032-3036, 3059-3089` — encoder が別プロセスであること、起動条件。
- `terminal/serve/server.py:3307-3327` — 応答待ち、kill、timeout 時の例外。
- `terminal/serve/server.py:3481-3512` — cache、`ENC` 送信、応答待ちとエラー変換。
- `terminal/serve/server.py:4606-4611, 5554-5599` — 画像処理経路と in-process vision の区別。
- `terminal/serve/server.py:5481-5516` — ツール画像経路の警告と画像の置換。
