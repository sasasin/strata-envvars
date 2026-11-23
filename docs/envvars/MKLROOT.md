# `MKLROOT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`MKLROOT` は実行中の Strata が読む設定ではなく、Hy4-Flash および Inkling-2 の SYCL 版をビルドするときに oneMKL のヘッダ位置を示すビルド環境変数である。指定した root の `include/oneapi/mkl/blas.hpp` が見つかると、ビルドに oneMKL 用のコンパイル定義・include path・リンク設定を加える。実行ファイルに機能を組み込むかを決めるもので、実行時に `MKLROOT` を変えても既に作られた実行ファイルの経路は変わらない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-50`, `engine/src/inkling2/sycl/build_inkling_sycl.sh:88-94`, `engine/src/inkling2/sycl/CMakeLists.txt:28-40`）。

## 値と判定

文字列の値域を parse する処理はない。root 文字列が空かどうかと、その下に特定のヘッダファイルがあるかを調べる。

| ビルド経路 | `MKLROOT` 未設定・空文字 | oneMKL を有効にする条件 | 無効・使われない例 |
|---|---|---|---|
| Hy4 SYCL の `build_hy4_sycl.sh` | `MKL_FLAGS` と `MKL_LIBS` は空のまま | 非空で、`$MKLROOT/include/oneapi/mkl/blas.hpp` が通常ファイルとして存在する | 未設定、空文字、ヘッダがない root。`0` や `false` も特別扱いせずパス文字列として扱い、その場所にヘッダがなければ使わない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-50`）。 |
| Inkling SYCL の `build_inkling_sycl.sh` | 同スクリプトでは flags と libs は空のまま | 非空で、`${MKLROOT}/include/oneapi/mkl/blas.hpp` が通常ファイルとして存在する | 未設定、空文字、ヘッダがない root。`0`・`false` もパスとして扱う（`engine/src/inkling2/sycl/build_inkling_sycl.sh:88-94`）。 |
| Inkling SYCL の CMake 構成 | `$ENV{MKLROOT}` が空なら `/opt/intel/oneapi/mkl/latest` を候補にする | 選ばれた root が非空で、その下に `include/oneapi/mkl/blas.hpp` が存在する | 空の環境変数でも固定パスにヘッダがあれば有効。非空だが無効な root を指定した場合は固定パスへ fallback せず、oneMKL を構成しない（`engine/src/inkling2/sycl/CMakeLists.txt:28-41`）。 |

Hy4 の shell 判定は `-n` と `-f`、Inkling の shell 判定も同じく `-n` と `-f` を使う。CMake は空かどうかと `EXISTS` を使う。大文字小文字の比較、数値変換、空白の trim、CLI 引数や設定ファイルとの優先順位はない。Hy4 shell スクリプトは flags を一つの文字列に組み立てて未クォートで展開するため、空白を含む root は引数分割される。Inkling shell は配列を使って値を引用し、CMake も引用した引数として渡す。CMake の `MKLROOT` が空の場合のみ、固定パス候補を確認する。Inkling shell スクリプトにはその fallback はない（上記位置）。

## 有効になる条件

- Hy4 経路では `engine/src/hy4flash/sycl/build_hy4_sycl.sh` を実行し、`icpx` が利用可能で、root のヘッダが見つかること。成功時は `HY4S_USE_ONEMKL` と include path を compile に渡し、リンク時に root の `lib` と oneMKL のライブラリ名を渡す（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:16-24,45-68`）。
- Inkling の shell 経路では `engine/src/inkling2/sycl/build_inkling_sycl.sh` を実行し、ヘッダが見つかること。成功時は `INK_SYCL_USE_ONEMKL=1` と include / link flags をコンパイラに渡す（`engine/src/inkling2/sycl/build_inkling_sycl.sh:88-107`）。
- Inkling の CMake 経路では `STRATA_ENABLE_SYCL` が有効で、Inkling の CMake が SYCL サブディレクトリを追加することが前提。oneMKL のヘッダが見つかると `INK_SYCL_USE_ONEMKL=1` と include path を設定し、非 Windows では link path とライブラリも設定する（`engine/src/inkling2/CMakeLists.txt:203-208`, `engine/src/inkling2/sycl/CMakeLists.txt:28-45`）。
- ビルド済み Hy4 の oneMKL 経路は別の実行時変数 `HY4S_ONEMKL` が先頭文字 `0` のとき無効になる。さらに `M >= 32`、`N` が 64 の倍数、`K` が 256 の倍数、`HY4S_XMX_I8` の変換値が 0、対応する重み形式と scratch 容量が必要。条件を満たさない oneMKL 呼び出しは通常の XMX または線形処理へ進む（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-865,868-907,943-985`）。
- ビルド済み Inkling では別の実行時変数 `INK_SYCL_NO_XMX` が先頭文字 `1` の場合 XMX を無効にする。oneMKL を含まないビルドでも無効。個別経路には行数・次元・scratch などの追加条件がある（`engine/src/inkling2/sycl/ink_sy_xmx.h:14-33,422-455,469-494`）。

## 実行時の詳細

Hy4 と Inkling の shell スクリプトはビルドのたびに `MKLROOT` を参照する。Inkling CMake は configure 時に `$ENV{MKLROOT}` を CMake 変数へ読み込み、oneMKL 用設定を target に付与する。どちらも実行時 cache ではない。ビルド後は `MKLROOT` ではなく compile define の有無が実装を含めるかを決める（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-68`, `engine/src/inkling2/sycl/CMakeLists.txt:28-45`）。

Hy4 では `HY4S_USE_ONEMKL` が定義されたビルドに限り oneMKL 呼び出しがコンパイルされる。実行時の `HY4S_ONEMKL` 判定が有効で、形式・形状・scratch 条件を満たす場合、Strata は量子化重みを FP16 に変換して oneMKL GEMM を呼び出す。該当しない場合は既存 XMX または線形 fallback に進む（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:868-907,943-985`）。

Inkling では `INK_SYCL_USE_ONEMKL` が定義されたビルドに限って oneMKL XMX 関数をコンパイルする。`xmx_enabled()` と各演算条件を通る経路で oneMKL GEMM が呼ばれる。`MKLROOT` 自体はモデル・リクエストごとの分岐や子プロセスへの転送には使われない（`engine/src/inkling2/sycl/ink_sy_xmx.h:14-33,422-455`）。

## ログと測定値

Hy4 のビルドスクリプトは `onemkl=1` または `onemkl=0` を含む `== Building strata-hy4-sycl (...) ==` を出力する（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68`）。Inkling の shell ビルドはヘッダが見つかった場合に `[build_inkling_sycl] Enabling Intel oneMKL XMX GEMM (${MKLROOT})` を出力する。見つからない場合はこの有効化メッセージを出さず、無効理由も出さない（`engine/src/inkling2/sycl/build_inkling_sycl.sh:88-94`）。Inkling CMake も有効化時に `Inkling SYCL: enabling Intel oneMKL XMX GEMM (...)` の STATUS メッセージを出す（`engine/src/inkling2/sycl/CMakeLists.txt:33-40`）。これらはビルド時の出力であり、実行時の利用を示すログではない。`MKLROOT` による測定値は記載できるソース根拠がない。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:557`
- Hy4 SYCL ビルド: `engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-68`
- Hy4 oneMKL 実行経路: `engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-907,943-985`
- Inkling shell ビルド: `engine/src/inkling2/sycl/build_inkling_sycl.sh:88-107`
- Inkling CMake ビルド: `engine/src/inkling2/sycl/CMakeLists.txt:28-45`
- Inkling SYCL のビルド条件と runtime gate: `engine/src/inkling2/CMakeLists.txt:203-208`, `engine/src/inkling2/sycl/ink_sy_xmx.h:14-33,422-455`
- SYCL backend の構成条件: `engine/CMakeLists.txt:23-33`
