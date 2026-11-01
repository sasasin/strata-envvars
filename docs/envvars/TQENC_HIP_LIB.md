# `TQENC_HIP_LIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱の Trellis エンコーダ用 Python wrapper `tools/tqenc.py` が、HIP 版共有ライブラリ `libtqenc_hip.so` を読み込むときに最初に試す候補のパスを指定します。Strata の engine や server が読む設定ではありません。GPU encode を選ぶ開発・調査用ツールで使われ、CPU encode の経路では参照されません。

## 値と判定

値を真偽値や数値に変換せず、文字列全体をライブラリ候補として扱います。

| 状態 | 処理 |
|---|---|
| 未設定 | `os.environ.get(..., "")` が空文字を返し、環境変数由来の候補を飛ばす。 |
| 明示的な空文字 | 未設定と同じく候補を飛ばす。 |
| 空でない値 | その文字列を候補として `ctypes.CDLL` に渡す。空白や `0` も特別扱いしない。 |
| 環境変数の候補で `OSError` | 例外を記録し、リポジトリ内の `tools/build-tqenc/libtqenc_hip.so` を次に試す。 |
| 全候補で読み込みに失敗 | 最後に捕捉した `OSError` を含む `RuntimeError("libtqenc_hip.so not found: ...")` を送出する。 |

環境変数の候補が失敗して既定パスが成功した場合、警告や失敗ログは出しません。既定パス自体がない場合も、変数の値は形式検査されず、単にライブラリ候補として試されます。

## 有効になる条件

- `tools/tqenc.py` の `encode(..., gpu=True)` が呼ばれ、かつ `exact` が偽で `t != TQ2_T` の場合に HIP 経路へ進みます。`exact` が真、または `TQ2_T` では例外を送出して `hip_lib()` を呼ばないため、この変数も読みません。
- `tools/trellis/pilot.py` は `--gpu` 指定時に `gpu=True` を渡します。`tools/dsv41/tq_convert.py` は既定で GPU を選び、`--cpu` を指定すると CPU を選びます。
- GPU ロック待ちに失敗した場合は CPU encoder に切り替わり、`hip_lib()` を呼びません。HIP ライブラリ候補の読み込みに失敗した場合は CPU に切り替わらず、例外が伝播します。
- Strata の通常の CLI、アプリ、server、CUDA/SYCL/Metal の実行経路でこの名前を読む参照は見つかりませんでした。

## 実行時の詳細

読み取りは `hip_lib()` の初回呼び出し時に行われます。候補の順序は環境変数の値、続いて `tools/build-tqenc/libtqenc_hip.so` です。共有ライブラリの読み込みに成功すると `_hip` に保持し、C 関数 `tqh_encode` の戻り値型と引数型を設定します。以後は `_hip` を返すため、プロセス内で環境変数を変更しても読み込み済みライブラリは切り替わりません。全候補の読み込みに失敗した場合は `_hip` が未設定のままなので、後続の呼び出しは再度候補を試します。

`encode()` は GPU ロックが取れれば `hip_lib().tqh_encode(...)` を呼びます。GPU ロックが取れなければ CPU encoder を使いますが、HIP 読み込み時の `RuntimeError` を捕捉する分岐はありません。呼び出し元では通常の Python 例外として伝播し、上位で別途捕捉しない実行では traceback とともに処理が失敗します。既定パスやローダーの内部仕様については、この文書では Strata の挙動として扱いません。

## 根拠

- `tools/tqenc.py:113-134` — `TQENC_HIP_LIB` の読み取り、候補順、空候補の除外、`OSError` 時の継続、全候補失敗時の `RuntimeError`、成功した `_hip` の再利用。
- `tools/tqenc.py:137-165` — GPU encode の条件、HIP 関数呼び出し、ロック失敗時の CPU encoder 経路。
- `tools/trellis/pilot.py:150-154,197-215` — `--gpu` オプションと `tqenc.encode(..., gpu=a.gpu)` の呼び出し。
- `tools/dsv41/tq_convert.py:65-78,138-140` — `--cpu` オプション、および既定で GPU を選ぶ encode 呼び出し。
- `tools/trellis/build.sh:13-21` — HIP 版ライブラリを `build-tqenc/libtqenc_hip.so` に作るビルド経路。
