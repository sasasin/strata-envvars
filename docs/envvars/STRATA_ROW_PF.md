# `STRATA_ROW_PF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU の native expert 行計算で、計算中の行より何バイト先の重み行をソフトウェア prefetch 要求するかを指定する。gate/up と down の汎用行ループが対象で、読み取りデータや計算結果を変える制御ではない。設定値は `native_expert.cpp` の `row_pf_setting()` で読み、`row_prefetch_range()` による要求距離に使う（`engine/src/kernels/cpu/native_expert.cpp:247-253,741-748,768-786,866-890`、`engine/include/strata/kernels/cpu/row_prefetch.hpp:26-49`）。

## 値と判定

未設定または空文字列なら `0`。それ以外は `std::atoi` で整数に変換し、変換結果が正の場合だけ先読みを行う。文字列全体の妥当性検査はなく、`atoi` が読める先頭の整数部分を使うため、たとえば `64junk` は `64`、`0anything`、`true`、空白だけの文字列は `0` となる。先頭空白と符号は `atoi` の変換規則に従う。変換値が `0` または負なら無効。明示的な上限・clamp はない（`engine/src/kernels/cpu/native_expert.cpp:247-253,742,866`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CPU native expert の汎用行ループ | `0`（無効） | `1` 以上に変換される整数。例: `1`, `64`, `64junk` | `0` 以下に変換される値。例: `0`, `-1`, `0anything`, `true`。空文字も unset と同じ `0` |

`atoi` が `int` で表せない値に対する安全な範囲検査は実装されていないため、その場合の値はここでは規定できない（`engine/src/kernels/cpu/native_expert.cpp:248-251`）。

## 有効になる条件

- `native_expert.cpp` を含む Strata CPU expert pool の経路であること。通常の engine CMake は CPU native expert ソースを `strata_kernels_cpu` に加え、SYCL と Metal の構成にも同じ CPU ソースが含まれる（`engine/cmake/backends/cpu.cmake:299-308`、`engine/sycl/CMakeLists.txt:228-234`、`engine/metal/CMakeLists.txt:140-146`）。CUDA/HIP の GPU expert 行カーネル自体をこの変数が制御する箇所は見つからなかった。
- gate/up または down の `native_*_rows_impl` が、専用の trellis、KQ、IQ、NVFP4 等の経路で早期 return せず、汎用 `dot.dot` 行ループへ到達すること。専用経路で処理される行にはこの先読み要求は適用されない（`engine/src/kernels/cpu/native_expert.cpp:653-708,719-739,741-789,794-865,866-892`）。
- `STRATA_ROW_PF` が正の整数に変換されること。値が有効でも行範囲の末尾では、距離先の行が範囲内にないとき逐次 prefetch は行わない（`engine/src/kernels/cpu/native_expert.cpp:771-774,886`）。
- `STRATA_ROW_PF_PRO` が未設定または空なら既定値 `1`、設定時は `atoi` の結果が非 `0` なら prologue prefetch を有効にする。`0` や `0junk` なら prologue 分は省くが、行ループ中の距離先 prefetch は引き続き行う。これは別の変数による併用条件（`engine/src/kernels/cpu/native_expert.cpp:254-260,744-748,868-870`）。

## 実行時の詳細

`row_pf_setting()` 内の関数ローカル `static const int` として初回呼び出し時に一度だけ取得・キャッシュする。呼び出しは汎用 gate/up または down 行ループに到達した後なので、プロセス起動直後ではなく、その経路が初めて使われる時点の環境値が採用される。以後の環境変更は反映されない（`engine/src/kernels/cpu/native_expert.cpp:247-253,741-743,866-867`）。CLI 引数や設定ファイルによる上書きはこの読み取り経路にはない。

距離はバイト数を行サイズで切り上げて行数に換算する。たとえば設定値が 1〜1 行サイズなら 1 行先、行サイズを超え 2 行サイズ以下なら 2 行先が対象になる。gate/up では gate と up の両方、down では down の各行について、prologue で先頭側の行を要求し、通常ループでは `r + pf_rows < r1` の範囲条件を満たすとき距離先の行を要求する（`engine/src/kernels/cpu/native_expert.cpp:741-748,768-774,866-870,884-890`）。

各行は `row_prefetch_range()` から 64 バイト刻みで要求される。x86 では `_mm_prefetch`、それ以外の GCC 系では `__builtin_prefetch`、それ以外では no-op の実装である（`engine/include/strata/kernels/cpu/row_prefetch.hpp:15-22,31-49`）。

## ログと測定値

この変数の読み取り、分岐、prefetch 要求に伴う Strata 独自のログ、警告、エラー、終了経路は見つからなかった。調査対象の `docs/DETAILS.md` にこの変数の測定値や条件の記載も見つからなかった。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:247-253` — unset / 空文字の扱い、`atoi`、static cache。
- `engine/src/kernels/cpu/native_expert.cpp:741-748,768-774,866-890` — 距離の行数換算、gate/up と down での使用、末尾ガード。
- `engine/include/strata/kernels/cpu/row_prefetch.hpp:15-49` — CPU architecture ごとの実装と 64-byte stride。
- `engine/cmake/backends/cpu.cmake:299-308`、`engine/sycl/CMakeLists.txt:228-234`、`engine/metal/CMakeLists.txt:140-146` — CPU native expert ソースの組み込み。
