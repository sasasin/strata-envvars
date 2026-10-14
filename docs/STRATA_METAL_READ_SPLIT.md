# `STRATA_METAL_READ_SPLIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

macOS の Metal エンジンで expert を SSD からストリーミングする際、expert 1個のファイル読み取りを何分割して I/O worker に渡すかを指定します。分割した各部分は別々の `pread` タスクとしてキューに入り、I/O worker が並行して処理します。実装コメントでは、SSD 全体の転送量だけでなく、layer が待つ個々の読み取り遅延を減らす狙いとされています。性能向上の保証や、この変数単独の測定値はソース・関連資料にありません。

この変数は Metal エンジンの `ExpertStream` にだけ実装されています。通常の Metal 経路で expert streaming が使われない場合には読み取られず、CUDA/HIP/SYCL の経路には適用されません。

## 値と判定

`ExpertStream::open()` が共通 helper `env_int()` で整数変換し、結果を 1〜8 に clamp します。

| 環境変数の値 | `atoi` の結果 | 適用値 |
|---|---:|---:|
| 未設定 | 既定値 1 | 1 |
| 空文字 | 既定値 1 | 1 |
| `1`〜`8` | 1〜8 | その値 |
| `0`、負数 | 0 以下 | 1 |
| `9` 以上 | 9 以上 | 8 |
| 数字で始まらない文字列 | `atoi` が 0 | 1 |
| 数字の後に文字が続く文字列（例: `4x`） | 数字部分を変換 | 4 |

文字列全体の妥当性検査はしません。`atoi` の規則に従い、先頭の空白や符号は数値変換時に扱われます。変換結果は `std::max(1, std::min(8, ...))` で制限されます。

## 有効になる条件

- `metal/src/engine/window.cpp` で `ExpertStream::wanted()` が true となり、`ExpertStream::open()` が呼ばれる場合にだけ値を読みます。
- `STRATA_METAL_STREAM=1` は streaming を強制し、`=0` は無効化します。それ以外（未設定を含む）はモデルの expert サイズと GPU working set などから自動判定します。自動判定の詳細は `metal/src/engine/stream.cpp:33-48` を参照してください。
- streaming が有効な場合でも、読み取り元が `<GGUF>.experts` の検証済み contiguous copy か元の GGUF かで、分割対象の単位が異なります。前者では expert 全体を分割し、後者では gate/up/down の各領域をそれぞれ分割します。
- 既定値の `1` では分割しません。I/O worker 数は別の `STRATA_METAL_IO_THREADS` で設定され、既定6です。split 数が worker 数を超える場合も、作成される全タスクが worker 数に応じて並行処理されます。

## 実行時の詳細

`open()` の中で値を一度読み、`split_` メンバーに保存します。したがって同じ `ExpertStream` が開かれた後に環境変数を変更しても、そのインスタンスには反映されません。モデルを開き直して新しいストリームを作ると、その `open()` 時点の環境値が使われます。

streaming の arena 作成時に `nio_` 個の worker thread が起動します。欠けている expert の読み取りを `submit()` が enqueue し、contiguous copy 使用時は `split_` 個、GGUF から gate/up/down を読む場合は `3 * split_` 個の job を作ります。各部分の開始・終了位置は 4096 byte 境界にそろえ、末尾の部分は領域の残りを読みます。全 job が終わるまで expert の slot は完了扱いにならず、現在の layer がその expert を必要とする場合は待機します。

この変数専用のログやエラー出力はありません。ファイル読み取りそのものに失敗した場合は `strata metal stream: reading expert <expert番号> of layer <layer番号> failed` を stderr に出して終了コード 6 で終了します。これは分割数の範囲チェックログではありません。

## 根拠

- `metal/src/engine/stream.cpp:27-30,149-150`: `env_int()` の空値・未設定時の既定値、`atoi`、1〜8 の clamp。
- `metal/src/engine/stream.cpp:269-302,332-343`: expert の読み取りを分割する方法と、contiguous copy の有無による job 数の違い。
- `metal/src/engine/stream.cpp:304-329,478`: worker が job を処理し、全部分完了後に slot を完了状態へ進める流れと worker 起動。
- `metal/src/engine/window.cpp:425-435`: streaming 判定後にのみ `ExpertStream::open()` を呼ぶ経路。
- `metal/src/engine/stream.cpp:33-48`、`docs/MAC.md:179-181,194-198`: Metal streaming の自動判定と適用範囲。`docs/MAC.md` に `STRATA_METAL_READ_SPLIT` 固有の説明や測定値はありません。
