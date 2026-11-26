# `STRATA_VISION_READY_S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`terminal/serve/server.py` が起動する画像エンコーダーの開始時に、標準出力から `READY` または `ERR` の応答を待つ秒数を指定する。期限内に応答がない場合は encoder を終了させて起動失敗として扱う。既定は 300 秒、0 以下なら期限を設けない。これは画像 encoder の起動応答待ちの設定であり、通常の engine の `READY` 待ちや encoder の画像 encode 応答待ちには適用されない（`ENGINE_READY_S`、`VISION_ENCODE_S` は別設定）。`terminal/serve/server.py` のモジュール読み込み時に値を取り込み、`VISION_READY_S` として使う（`terminal/serve/server.py:460`, `terminal/serve/server.py:3224`, `terminal/serve/server.py:439-462`）。

## 値と判定

`terminal/serve/server_parts/base.py` の `_timeout_env` は `float(os.environ.get(name, default))` で変換し、変換時の `ValueError` では既定値に戻す。その後 `v <= 0` なら `None`（無期限）、それ以外は秒数の float を返す（`terminal/serve/server_parts/base.py:272-277`）。

| 条件 | unset | 有効になる値（例） | 無効値・境界の例 |
|---|---|---|---|
| `terminal/serve/server.py` のサーバー実装 | 300 秒 | `1`、`0.5`、`1e2` は秒数として受理。`float()` が受理する数値文字列を変換する | 空文字 `""`、`true`、数値でない文字列は `ValueError` となり既定の 300 秒。`0`、`-1` は無期限。空白だけの文字列も変換失敗で既定値 |

数値文字列全体を Python の `float()` で変換し、先頭文字だけの判定ではない。大文字小文字を区別する真偽値文字列の判定もなく、`true` / `false` は数値として無効。負の有限値と `-0.0` は 0 以下として無期限になる。`float()` の結果に有限値チェックがないため `inf` / `nan` も変換自体は通り、`inf` は実質期限なし、`nan` は期限比較を満たさずタイムアウトしない値になる。`nan` / `inf` の利用は推奨値としてコードに記載されてはいない（`terminal/serve/server_parts/base.py:272-277`; deadline 判定は `terminal/serve/server.py:3277-3289`）。

## 有効になる条件

- `terminal/serve/server.py` の画像 encoder 起動経路で有効。画像機能を持たない server や、画像 encoder を起動しない経路では待ち時間は発生しない。別プロセスで起動する encoder が対象で、`Vision.__init__` は `lazy` でなく `elastic` でもない場合に初期化中に起動し、lazy / elastic の場合は後の起動経路で開始する（`terminal/serve/server.py:3059-3090`, `terminal/serve/server.py:4684-4699`）。
- GPU encoder の起動が失敗し CPU fallback が構成されている場合、timeout も失敗理由として GPU reader の失敗処理に入り、CPU reader を開始する。fallback がない場合は起動失敗が上位へ伝播する（`terminal/serve/server.py:3142-3157`）。
- Python サーバープロセスの環境から読み取る。CLI 引数や config の同名キーによる上書きはこの読み取り箇所にはない。値はモジュール定数に保存されるため、サーバープロセス起動後に環境を変更しても反映されない（`terminal/serve/server.py:460`, `terminal/serve/server.py:3224`）。
- `vision.env` 等で子 encoder に渡す環境を作る処理は別にあるが、この変数の待ち秒数を再読込するものではない（`terminal/serve/server.py:4134-4156`）。

## 実行時の詳細

`Vision._start_reader()` は encoder を起動した後、`_await_ready(VISION_READY_S, strays)` を呼ぶ。`_await_ready` は stdout を読む daemon thread と期限を設定し、`READY` または `ERR` で始まる行を応答として返す。その他の stdout 行は stray として保持・ログ出力し、そのまま同じ期限まで待つ。期限が来ると encoder に `kill()` を試みて `RuntimeError` を送出する。既定の 300 秒は encoder が何も言わない場合の上限であり、0 以下の設定では deadline を作らず待ち続ける（`terminal/serve/server.py:3214-3229`, `terminal/serve/server.py:3256-3305`）。

timeout の例外は encoder を停止状態にしてから処理される。有限の正数設定では `vision_start_error` に待ち秒数を渡して起動エラーにし、0 以下では無期限待ちなのでこの timeout 経路自体は起きない。受信行が `READY` で始まらない場合は encoder を kill し、応答内容や終了コード、stderr の末尾などを含む起動エラーにする。GPU reader に CPU fallback があれば `_start()` がそのエラーを捕捉して CPU reader を開始する（`terminal/serve/server.py:3224-3243`, `terminal/serve/server.py:3142-3157`）。

この値はモジュール読み込み時に一度評価され `VISION_READY_S` に保持される。各 encoder の起動時に定数が `_await_ready` へ渡されるが、環境変数自体は再読込されない。複数回の起動があれば各起動でその待ち時間が適用される（`terminal/serve/server.py:460`, `terminal/serve/server.py:3224`）。

## ログと測定値

timeout では `_await_ready` 内で `the vision encoder did not start: it said nothing for N s` という例外文を作る（`N` は秒数を整数表示）。有限 timeout の上位エラー文は `vision_start_error` が `the vision encoder did not start: it said nothing for N s (it never reported READY)` の形に整える。GPU reader に CPU fallback がある場合、さらに `[strata] the GPU picture reader did not start (...); pictures are read on the CPU`（elastic の場合は `until it is idle` を含む）を stdout に出して CPU reader に切り替える（`terminal/serve/server.py:3282-3288`, `terminal/serve/server_parts/engines.py:618-665`, `terminal/serve/server.py:3152-3157`）。

この変数に関する性能測定値は、対象ソースと参照した `docs/DETAILS.md` に記載を確認できなかった。

## 根拠

- `terminal/serve/server_parts/base.py:272-277` — 環境変数の変換、既定値への fallback、0 以下を無期限にする処理。
- `terminal/serve/server.py:439-462` — timeout 群の既定値と `VISION_READY_S` のモジュール定数化。
- `terminal/serve/server.py:3059-3090` — Vision 初期化と eager 起動条件。
- `terminal/serve/server.py:3142-3157` — GPU 起動失敗時の CPU fallback とログ。
- `terminal/serve/server.py:3214-3248` — encoder 起動、READY 判定、起動エラー処理。
- `terminal/serve/server.py:3256-3305` — READY 待ち、deadline、timeout 時の kill、stray 行処理。
- `terminal/serve/server.py:4134-4156` — encoder 子プロセス向け環境構築。
- `terminal/serve/server_parts/engines.py:618-665` — 起動失敗メッセージの組み立て。
