# `TQENC_GPU_WAIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`tools/tqenc.py` の trellis encoder Python wrapper が GPU 用ロックを待つ時間を秒単位で指定します。待ち時間を超えてロックを取得できなかったとき、GPU encode を諦めて同じ encode 呼び出しを CPU encoder に切り替えます。Strata の通常の推論 engine ではなく、同梱の encoder ツール経路で使われる設定です（`tools/tqenc.py:1-3,137-165`）。

## 値と判定

`_gpu_lock.__enter__()` が `float(os.environ.get("TQENC_GPU_WAIT", "1e9"))` で Python の `float` に変換します。文字列全体を `float()` が受理できる必要があり、`atoi` のように数値以降を無視する処理ではありません（`tools/tqenc.py:76-88`）。

| 値 | 結果 |
|---|---|
| 未設定 | `1e9` 秒を使用する。コード上は有限の既定値で、docstring の「wait for ever」とは一致しない。 |
| 空文字 | `float("")` が `ValueError`。CPU fallback には進まず例外になる。 |
| 数値文字列 | `float()` が受理する浮動小数点値を秒として使用する。整数・小数・指数表記が使える。 |
| 不正な文字列 | `ValueError`。例外を捕捉する fallback はこの箇所にはない。 |
| `nan` / `inf` など | Python `float()` が受理する。値域の検査や有限値チェックはない。比較では `nan` に対する `経過時間 > wait` が偽になるため、待ちループの条件が続く限り timeout しない。 |
| 0 または負数 | 範囲検査・clamp はない。timeout 判定はロック待ち中にだけ行われるため、待ちが発生せずロックを取得できれば、この値でも GPU 経路は通る。待ちが発生すると `経過時間 > wait` で timeout する。 |

timeout 判定は `>`（厳密な大なり）です。GPU ロックが競合しない場合、取得前に経過時間を確認する処理はありません（`tools/tqenc.py:84-103`）。

## 有効になる条件

次の条件を満たす場合だけ `TQENC_GPU_WAIT` が読み取られます。

- 呼び出し元が `tqenc.encode(..., gpu=True)` を指定する。
- `exact` が偽で、型が `TQ2_T` ではない（これらは環境読み取りより前に `ValueError` になる）。
- 環境に `TQENC_GPU_LOCK` が存在する。空文字でも「未設定」ではないためロック処理に入る。`TQENC_GPU_LOCK` 自体が未設定なら `_gpu_lock` は即時に戻り、`TQENC_GPU_WAIT` は読まれない。

GPU要求時は `_gpu_lock` を通った後、ロックを取れた場合に HIP encoder `tqh_encode` を呼びます。timeout した場合は `TQENC_CPU_THREADS` を `int()` に変換し、未設定なら `threads` 引数の truthy 値、さらにそれもなければ 24 を使って CPU encoder `tqe_encode` を呼びます。CLI 引数等による `TQENC_GPU_WAIT` の上書きはこの wrapper にはありません（`tools/tqenc.py:137-165`）。

## 実行時の詳細

値は `_gpu_lock` の各 `__enter__()` 呼び出しで読み直され、module-level cache には保存されません。したがって Python プロセス内で環境を変更してから次の encode を呼べば、その呼び出しでは新しい値が参照されます。ただし、`TQENC_GPU_LOCK` が未設定なら値の取得自体がありません（`tools/tqenc.py:72-88`）。

待機開始時刻には `time.time()` を使います。`~/locks/EXCL_WAIT` が存在する間は 2 秒ごとに確認し、経過時間が設定値を超えると `gl.ok=False` として戻ります。続いて `/data/gpu.lock` の shared lock、`~/locks/gpu<カード番号>.lock` の exclusive lock を non-blocking で順に取得します。flock が競合した場合は 0.2 秒間隔で再試行し、同じ経過時間判定で timeout します。2 個目のロックで timeout した場合、開いていた fd を閉じ、先に取得したロックも解放します（`tools/tqenc.py:84-110`）。

timeout はログを出さず、プロセスを終了させず、CPU encode へ分岐するだけです。これは戻り値の `gl.ok` を確認する呼び出し元の処理です（`tools/tqenc.py:157-165`）。一方、空文字や不正な数値文字列の `ValueError`、ファイル操作や `flock` の別の例外については、この wrapper 内で捕捉・変換されません。

## 根拠

- `tools/tqenc.py:67-82` — ロック helper と `TQENC_GPU_WAIT` の実際の既定値・変換。
- `tools/tqenc.py:84-110` — writer marker と2段階 flock の待機、timeout 判定、fd 解放。
- `tools/tqenc.py:137-165` — GPU encode の前提、HIP 呼び出し、timeout 後の CPU fallback。
- `tools/dsv41/tq_convert.py:1-5,123-147` — GPU ロックを使う trellis conversion ツールから wrapper を呼ぶ例。
