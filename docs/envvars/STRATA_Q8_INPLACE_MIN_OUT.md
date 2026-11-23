# `STRATA_Q8_INPLACE_MIN_OUT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_Q8_INPLACE=1` による dense `Q8_0` 行列の in-place packed 格納を許可する出力行数 `n_out` の下限を指定する。値を大きくすると、より行数の多い行列だけが対象になる。対象変数だけを設定しても in-place packing は有効にならない。実装は CUDA カーネルの `q8_inplace_min_out()` と `native_q8_0_inplace_eligible()`、呼び出し元は `NativeDense::load()` である。`STRATA_Q8_SM60` による出力 head や MTP draft head の packing は別経路で、この閾値を使わない。

## 値と判定

`std::getenv` で値を取得し、設定されていれば `std::atoi` で整数化する。変換結果が 1 以上ならその整数を閾値にし、それ以外は 640 にする。文字列全体の検証はしない。`atoi` のため先頭空白と符号は数値変換に含まれ、数字の後ろにある文字は無視される。大文字小文字は関係しない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA 実装で閾値を評価 | 既定値 640 | `1`, `640`, `+12`, ` 12`, `12tail` はそれぞれ 1, 640, 12, 12, 12 | 空文字、`0`, `0anything`, `-1`, `true`, `tail12` は 640 に fallback |

`atoi` の結果が 1 以上であることが唯一の値条件で、上限 clamp はない（ただし変換先は C++ `int`）。無効値の警告は出さない。読み取りと fallback は `engine/src/kernels/cuda/native_mmvq.cu:2651-2658`。

## 有効になる条件

- `STRATA_Q8_INPLACE` が文字列全体でちょうど `1` であること。空文字や `01`、`1tail` は有効化しない。これは別の `q8_inplace_on()` 判定である（`engine/src/kernels/cuda/native_mmvq.cu:2638-2649`）。
- CUDA 経路であること。HIP (`__HIPCC__`) では in-place 機能の有効判定と適格判定がともに `false` を返す（`engine/src/kernels/cuda/native_mmvq.cu:2638-2641`, `2997-3012`）。
- この適格性判定に OS 固有の分岐はない。
- `NativeDense::load()` が扱う、対応済みの量子化済み 2 次元 `Q8_0` tensor であること。`blk.1.ple_key.weight` は対象外（`engine/src/core/native_dense.cpp:459-471`）。
- 行列の `n_in` が 128 以上かつ 32 の倍数で、`n_out >=` この閾値であること。さらに `q8sm60::smem_bytes(MAX_COLS, n_in)` がその device の上限以下であること（`engine/src/kernels/cuda/native_mmvq.cu:3005-3012`, `engine/src/kernels/cuda/q8_sm60.cuh:26-50`）。
- `STRATA_Q8_SM60` だけを有効にしたときの packing はこの変数を条件にしない。`native_q8_0_packed_eligible()` はその場合に形状条件だけで早期 return する（`engine/src/kernels/cuda/native_mmvq.cu:2991-2995`）。

## 実行時の詳細

`NativeDense::load()` は各候補 tensor について、型が `Q8_0`、tensor 名が PLE key 以外、in-place 機能が有効、かつ `native_q8_0_inplace_eligible()` が true のとき `do_inplace` を選ぶ。その場合、GGUF の Q8_0 blocks を host 側で同じ byte 数の split `qs` / fp16 scale planes に並べ替え、その格納を native dense の tensor allocation にアップロードする。別の packed allocation は作らず、その tensor を packed registry に登録する。したがってこの変数は量子化方式や出力次元を変えるものではなく、この格納への切替対象となる行数の境界を変える（`engine/src/core/native_dense.cpp:467-482`, `521`, `635-640`）。

閾値は関数内 `static const int` に保存され、初回評価時に一度だけ読み取られる。実行中に環境を変更しても、閾値が再評価されない。値の評価は適格性判定時で、in-place opt-in が無効なら通常の `NativeDense::load()` 経路では閾値判定に進まない（`engine/src/kernels/cuda/native_mmvq.cu:2651-2658`, `2991-3012`; `engine/src/core/native_dense.cpp:469-471`）。CLI 引数や設定ファイルによる上書きはこのコードにはない。

登録済みの行列が decode MMVQ に渡ると、in-place opt-in 時は `q8sm60::launch()` を使う。kernel の積和順序は exact kernel と異なり、ソースコメントは浮動小数点丸め差があり bitwise 一致しないと記す。kernel が in-place tensor を処理できない場合は `stderr` に `strata q8 inplace: q8sm60 declined in-place tensor (...)` を出して `abort()` し、元の GGUF-layout kernel へ fallback しない（`engine/src/kernels/cuda/native_mmvq.cu:2767-2796`; `engine/src/kernels/cuda/q8_sm60.cuh:17-18`）。

## ログと測定値

適格な dense Q8_0 行列が一つ以上 in-place packed された場合、`NativeDense::load()` は stderr に `native dense: STRATA_Q8_INPLACE=1 packed %zu Q8_0 matrices in-place (%.1f MiB, +0.0 MiB VRAM)` を出す。対象行列がない場合や packing が選ばれない場合、この成功ログは出ない。値の未設定・無効値に対する専用ログはない。decode 時に in-place tensor の launch が decline された場合の stderr と終了経路は上記のとおり（`engine/src/core/native_dense.cpp:654-656`; `engine/src/kernels/cuda/native_mmvq.cu:2789-2793`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:2651-2658` — 閾値の読み取り、`atoi`、fallback、cache。
- `engine/src/kernels/cuda/native_mmvq.cu:2638-2649`, `2991-3012` — opt-in 条件と backend / 形状 / device shared memory の適格判定。
- `engine/src/core/native_dense.cpp:459-482`, `498-521`, `628-656` — dense tensor の選別、格納、registry 登録、ログ。
- `engine/src/kernels/cuda/native_mmvq.cu:2767-2796` — decode MMVQ の packed dispatch、decline 時の abort。
- `engine/src/kernels/cuda/q8_sm60.cuh:26-50`, `108-110` — shared-memory 制限と device 上限の取得。
- `docs/SETTINGS.md:282-284`, `docs/NVIDIA_V100.md:65-68` — 既存資料では NVIDIA と AMD 向けと記載し、既定閾値を 640 としている。既定値 640 は実装と一致するが、HIP では実装が `false` を返すため、AMD でも有効という一覧の分類はコードと一致しない。
