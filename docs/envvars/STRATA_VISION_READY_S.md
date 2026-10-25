# `STRATA_VISION_READY_S`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Python サーバーが画像エンコーダープロセスを起動した後、最初の応答行を待つ秒数を指定します。画像エンコーダーの起動時に無応答のままサーバーの処理が止まることを防ぐための timeout です。画像の個別エンコード中の待ち時間は別の `STRATA_VISION_ENCODE_S` で制御され、この変数の対象外です。

## 値と判定

サーバーモジュールの読み込み時に `float(os.environ.get(...))` で変換します。

| 環境変数の値 | `VISION_READY_S` に設定される値 |
|---|---|
| 未設定 | `300.0` 秒 |
| 空文字、または `float()` が `ValueError` となる文字列 | 既定値の `300.0` 秒 |
| 数値として変換でき、`v <= 0` が偽になる値 | その浮動小数値を待ち処理へ渡す。通常の正値のほか、`NaN` もこの分岐になる。上限への clamp はない |
| `v <= 0` が真になる値（0、負値、負の無限大など） | `None`。起動応答行の待ち時間を無制限にする |

変換は Python の `float()` によるもので、整数に限定されません。`float()` が受け付ける特殊な値も個別検査や有限値チェックを通らず、`v <= 0` が偽になる値（`NaN`、正の無限大を含む）はそのまま待ち処理へ渡されます。CLI 引数や設定ファイルによる上書きはこのコードにはありません。

## 有効になる条件

`serve/server.py` の Python サーバーを実行し、画像エンコーダーを起動する場合に適用されます。エンコーダーは eager 起動（lazy でなく、かつ elastic でない場合）または後続の `_start()` 呼び出しで起動されます。C++エンジン側や画像エンコーダー自身の待ち時間設定ではありません。

## 実行時の詳細

`VISION_READY_S` はモジュール読み込み時に一度だけ評価され、`Vision._start_reader()` がエンコーダーを起動した後、最初の行を `_readline()` で待つときに使います。サーバー起動後にプロセス環境を変更しても、このモジュール変数は再評価されません。

待ち時間を過ぎても行が返らない場合、サーバーはエンコーダープロセスを kill し、`RuntimeError`（`the vision encoder did not start: it said nothing for ... s`）を発生させます。起動時の `_start()` は GPU reader に CPU fallback が設定されていれば理由を `[strata] the GPU picture reader did not start (...); pictures are read on the CPU` として出し、CPU reader を起動します。fallback がなければ例外を呼び出し元へ返します。READY 以外の行が返るケースは timeout ではなく、別途エラー行として扱われます。

値が `None` の場合、`queue.Queue.get(timeout=None)` となり、無応答でもこの待機自体では timeout しません。起動後の各画像エンコード応答行には `STRATA_VISION_ENCODE_S` が使われます。

## 根拠

- `serve/server.py:295-300` — 環境変数取得、`float()` 変換、無効文字列の既定値 fallback、0以下を `None` にする処理。
- `serve/server.py:328` — 既定値300秒でのモジュール読み込み時評価。
- `serve/server.py:2554-2561` — Vision reader の eager 起動条件。
- `serve/server.py:2584-2619` — reader 起動、READY 行待ち、GPU 起動失敗時の CPU fallback、および READY 不一致の処理。
- `serve/server.py:2622-2642` — 応答行を待ち、timeout 時に子プロセスを kill して `RuntimeError` を出す処理。
- `serve/server.py:2774` — エンコード応答待ちには別変数 `VISION_ENCODE_S` を使う箇所。
