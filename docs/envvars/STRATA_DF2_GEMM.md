# `STRATA_DF2_GEMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 版 DFlash2 drafter の Q8 行列 GEMM で、行列の出力行数 `rows` に応じて選ぶ GEMM カーネル variant の既定方式を切り替える。未設定または `atoi` の結果が 0 以外ならサイズ別の選択、0 なら従来の「8 rows a warp」系 variant 1 / 2 を使う。Q4 行列側の分岐にはこの変数は使われない。読み取りと選択は `strata::kernels::df2_gemm` にある（`engine/src/kernels/cuda/dflash2.cu:1787-1795,1859-1861,1908-1941`）。

## 値と判定

Q8 側の分岐まで到達したとき、関数内 `static const int` 初期化子で `std::getenv` を一度呼び、未設定なら `1`、設定済みなら `std::atoi` の戻り値を保持する。文字列全体の検証はなく、`atoi` が先頭から変換できた整数だけを使う。したがって空文字や数字で始まらない文字列は 0、`0anything` も 0、`1anything` は 1、先頭空白や符号は `atoi` の変換規則に従う。`true` も 0 となる。0 以外の値に個別の意味や範囲検査はなく、負数を含めすべてサイズ別方式を選ぶ。

| 条件 | unset | 有効になる値（サイズ別選択） | 0 になる値（従来 variant） |
|---|---:|---|---|
| CUDA/HIP の DFlash2 Q8 GEMM がこの読み取り箇所まで到達 | `1` | 変換後の値が 0 以外。例: `1`, `-1`, `1abc` | 変換後の値が 0。例: `0`, `0anything`, 空文字, `true`, `abc` |

`atoi` の変換結果が 0 かどうかだけを `tune == 0` で判定する（`engine/src/kernels/cuda/dflash2.cu:1908-1914`）。

## 有効になる条件

- `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` の GPU engine がビルドされ、DFlash2 の `dflash2.cu` 実装を使うこと。Metal と SYCL の build には DFlash2 drafter が含まれない（`engine/cmake/strata_gpu_engine.cmake:6-13,97`）。
- DFlash2 drafter が `df2_gemm` を呼び、対象行列群が Q8 形式であること。重み tensor の型が `q4_0` なら `q4` フラグが立ち、Q4 分岐で戻るためこの変数は参照されない（`engine/src/core/dflash2.cpp:480-490`; `engine/src/kernels/cuda/dflash2.cu:1859-1908`）。
- 呼び出しが形状検査を通ること（`n` は 1〜3、`n_in` は 512 の倍数、`ncols >= 1`、各行列の `n_out` は 16 の倍数、同一 launch 内で weight format が一致）。不適合時は `std::invalid_argument` となり、環境変数の読み取りには到達しない（`engine/src/kernels/cuda/dflash2.cu:1787-1795`）。
- CUDA では、`STRATA_DF2_GEMM_TC` が有効で Tensor Core GEMM の条件（`ncols >= 2`, `rows >= 1024`, `rows` が 16 の倍数、compute capability major >= 8）を満たすと、Tensor Core kernel を実行して先に戻るため、この変数による variant 選択は行わない。HIP では当該 Tensor Core 分岐がコンパイル対象外（`engine/src/kernels/cuda/dflash2.cu:1836-1858`）。
- CUDA で `ncols > 8` のとき、compute capability major >= 8 かつ `rows` が 16 の倍数なら batch Tensor Core kernel が先に選択されて戻り、この変数を読まない。それ以外は列を最大 8 列ずつに分割して再帰呼び出しする（`engine/src/kernels/cuda/dflash2.cu:1801-1834`）。
- ベンチ用 API `df2_gemm_variant(v)` が 0 以外を設定している場合は、その `g_gemm_variant` が環境変数から計算した variant より優先する。通常の DFlash2 計算経路にはなく、ヘッダーでも bench 用 API として宣言されている（`engine/src/kernels/cuda/dflash2.cu:26,1762,1908-1914`; `engine/include/strata/kernels/dflash2.hpp:61-63`）。

## 実行時の詳細

通常の DFlash2 経路では `Dflash2Drafter::gemm` が pack 内 tensor の型を `Df2Mat::q4` に写し、kernel の `df2_gemm` を呼ぶ。Q8 の GEMM は DFlash2 の context 更新と drafter block 内の projection（例: fc、q/k/v、o、gate/up/down、selector projection）で使われる（`engine/src/core/dflash2.cpp:480-490,514-525,549-581,608-610`）。

環境値はプロセス起動時に必ず読むのではなく、プロセス内で最初に Q8 分岐がこの初期化行へ到達したときに読む。C++ の関数ローカル `static` に保存されるため、その後の環境変更はこの実行中のプロセスでは反映されない。Q4 専用実行、先行する Tensor Core 経路、または形状エラーだけで終わる場合は読み取りが起きない（`engine/src/kernels/cuda/dflash2.cu:1787-1909`）。

`tune == 0` の場合は `rows % 32 == 0` なら variant 1、それ以外は variant 2。0 以外の場合は `rows <= 1024` で variant 20、`1025..3072` で variant 13、`rows >= 15000` で variant 10、それらの間は 32 の倍数なら variant 1、そうでなければ variant 2 を選ぶ。いずれも `gemm_rows_kernel` の variant switch に渡される（`engine/src/kernels/cuda/dflash2.cu:1909-1940`）。

## ログと測定値

この変数の読み取り値や選択 variant を出すログはない。kernel launch が失敗すると `check("gemm8")` が stderr に `dflash2 kernel gemm8: <CUDA/HIP error text>` を出し、同じ内容の `std::runtime_error` を投げる（`engine/src/kernels/cuda/dflash2.cu:29-34,1941`）。性能値はこの文書では記載しない。

## 根拠

- `engine/src/kernels/cuda/dflash2.cu:1787-1795,1801-1834,1836-1861,1908-1941` — 入力形状・backend 条件・環境値の読み取り・variant 選択・kernel launch。
- `engine/src/core/dflash2.cpp:480-490,514-525,549-581,608-610` — DFlash2 drafter からの呼び出しと Q8/Q4 flag の設定。
- `engine/cmake/strata_gpu_engine.cmake:6-13,97` — DFlash2 実装を含む CUDA/HIP build 条件。
- `engine/include/strata/kernels/dflash2.hpp:61-68` — variant API と GEMM interface。
