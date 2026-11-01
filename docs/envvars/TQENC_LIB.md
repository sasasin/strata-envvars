# `TQENC_LIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱ツール `tools/tqenc.py` が、CPU trellis encoder/decoder の共有ライブラリ `libtqenc.so` をロードするとき、最初に試すパスを指定します。Strata の推論エンジンやサーバーが読む設定ではありません。`tools/trellis` の encoder 調査・変換スクリプトや `tools/dsv41/tq_convert.py` など、Python wrapper を使うツールに適用されます（`tools/trellis/README.md:14-24`, `tools/dsv41/tq_convert.py:2-5,29-30,138-140`）。

## 値と判定

値を真偽値や数値には変換せず、ライブラリ候補のパス文字列として使います。空でない値は先頭の候補になります。

| `TQENC_LIB` | 処理 |
|---|---|
| 未設定 | 環境変数由来の候補を加えず、既定候補を順に試す |
| 空文字 | 空候補を読み飛ばし、未設定と同じ候補順になる |
| 空でない文字列 | その文字列を最初に `ctypes.CDLL` に渡す。ロード時に `OSError` となれば次の候補へ進む |

候補順は、環境変数の値、`tools/tqenc.py` の位置から組み立てる `build-tqenc/libtqenc.so`、文字列 `libtqenc.so` です。成功した候補で探索を止めます。パス文字列の妥当性検査、文字列比較、数値変換、範囲制限はありません。すべて失敗すると、最後に捕捉した `OSError` の内容を含めて `RuntimeError("libtqenc.so not found ...")` を送出します（`tools/tqenc.py:38-61`）。

## 有効になる条件

- `tools/tqenc.py` の `encode()` または `decode()` から CPU ライブラリ `lib()` が呼ばれる場合に使われます。`TQENC_LIB` は import 時ではなく、最初に `lib()` が呼ばれたときに参照されます（`tools/tqenc.py:35-61,137-165,168-177`）。
- `encode(..., gpu=True)` で GPU ロック取得が成功した経路は、CPU ライブラリではなく `hip_lib()` を使い、別変数 `TQENC_HIP_LIB` と `build-tqenc/libtqenc_hip.so` を探索します。GPU ロック取得が timeout して CPU encode にフォールバックする場合は `TQENC_CPU_THREADS` を読んだ後、`lib()` 経由で `TQENC_LIB` が適用されます。CPU encode の通常経路と `decode()` も `TQENC_LIB` を使います（`tools/tqenc.py:64-65,113-134,137-177`）。
- このパス選択に CLI 引数による上書きはありません。別の環境変数が候補順を変更する実装もありません。GPU encode のライブラリ選択は前述の `TQENC_GPU_LOCK` によるロック経路で分かれます。

## 実行時の詳細

モジュール変数 `_lib` が `None` の間に `lib()` が候補を順に試します。成功した `ctypes.CDLL` オブジェクトを `_lib` に保存し、続けて `tqe_encode` / `tqe_decode` の戻り値型と引数型を設定します。以降の `encode()` / `decode()` はキャッシュされたライブラリを使い、環境変数を再評価しません。したがって、最初のロード成功後にプロセス環境を変えても切り替わりません。すべての候補が失敗して `_lib` が `None` のままなら、後続の呼び出しでも探索を再試行します（`tools/tqenc.py:35-61`）。

失敗時は wrapper が `RuntimeError` を出します。`TQENC_LIB` の候補だけが失敗して既定候補のいずれかが成功した場合、wrapper は警告を出さず成功候補を使います。ロード候補がすべて失敗した場合、エラー文字列に最後の `OSError` が含まれます（`tools/tqenc.py:44-54`）。

## 根拠

- `tools/tqenc.py:35-61` — `_lib` キャッシュ、候補の順序、`OSError` 時の継続、全候補失敗時の `RuntimeError`、C API 宣言。
- `tools/tqenc.py:137-177` — encode/decode からの読み取り到達経路、GPU/HIP 経路と CPU 経路の分岐。
- `tools/tqenc.py:67-110,113-134,154-164` — GPU ロック、HIP ライブラリ探索、ロック timeout 時の CPU fallback と関連変数。
- `tools/trellis/README.md:14-24`, `tools/dsv41/tq_convert.py:2-5,29-30,138-140` — wrapper が同梱ツールから使われること。
