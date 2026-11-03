# `DF2B_HOSTALLOC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench gemm` 実行時に、ベンチマーク開始前の host memory allocation を追加します。値 `1` は Strata の `host_malloc_polled()`、値 `2` は `sycl::malloc_host()` を 4096 byte 分呼びます。返されたポインターは保存・使用されず、この変数は Strata の通常の `strata` エンジン実行を制御しません。`dflash2_bench` は `STRATA_SYCL_PARITY` が有効な場合にだけビルド定義されます（既定値は ON）。（`sycl/src/kernels/dflash2_bench.cpp:614-616,894-901`; `sycl/CMakeLists.txt:288-291,437-438`）

## 値と判定

共通 helper `envi()` は `getenv()` を呼び、未設定または空文字なら既定値を返し、それ以外は `atoi()` の結果を返します。対象箇所の既定値は `0` です。判定は変換後の整数との完全一致です。（`sycl/src/kernels/dflash2_bench.cpp:56,615-616`）

| 値 | 処理 |
|---|---|
| 未設定、空文字 | `0`。追加 allocation なし |
| `1` に変換される文字列 | `strata::host_malloc_polled(4096, *Q)` を呼ぶ |
| `2` に変換される文字列 | `sycl::malloc_host(4096, *Q)` を呼ぶ |
| その他 | 追加 allocation なし |

`atoi()` のため、数値の後ろに文字があっても整数部分が変換されます（例: `1tail` は 1、`2tail` は 2）。先頭の空白や符号も `atoi()` の規則で処理され、数値として始まらない非空文字列は 0 になり、追加 allocation は起きません。`-1` や `3` など 1・2 以外の値も分岐に一致しません。文字列全体の検査や明示的な範囲制限はありません。（`sycl/src/kernels/dflash2_bench.cpp:56,615-616`）

## 有効になる条件

- ビルドで `STRATA_SYCL_PARITY` が有効であり、`dflash2_bench` が生成されていること。CMake option の既定値は ON です。（`sycl/CMakeLists.txt:288-291,437-438`）
- プログラムを `dflash2_bench gemm` として起動し、`run_gemm_bench()` に入ること。他のモード（`test`、既定の `bench`、`attn` など）ではこの変数を参照する処理に入りません。（`sycl/src/kernels/dflash2_bench.cpp:614-616,894-901`）
- 値 `1` の helper 呼び出しで uncached host allocation を試すかは、コンパイル時の `STRATA_HAVE_ZE`、queue の backend、および別変数 `STRATA_HOST_UNCACHED` にも依存します。値 `2` はこの helper を通らず、直接 `sycl::malloc_host()` を呼びます。（`sycl/include/strata/sycl_queue.hpp:48-77`）

## 実行時の詳細

`envi()` は値をキャッシュせず、`run_gemm_bench()` の 2 つの `if` 条件でそれぞれ環境を読み直します。通常の実行では呼び出し間で環境が変わらないため、値 1 なら最初の分岐だけ、値 2 なら次の分岐だけが allocation を行います。（`sycl/src/kernels/dflash2_bench.cpp:56,614-616`）

値 1 の `host_malloc_polled()` は、Level Zero header が利用可能なビルドで `STRATA_HAVE_ZE` が定義され、`STRATA_HOST_UNCACHED` の先頭文字が `0` でなく、queue backend が Level Zero の場合に `zeMemAllocHost()` を試みます。成功しない場合、または条件に合わない場合は `sycl::malloc_host()` に fallback します。`STRATA_HOST_UNCACHED` は helper 内で初回呼び出し時に `static const bool` として一度評価され、未設定・空文字では有効、先頭文字 `0` では無効です。（`sycl/include/strata/sycl_queue.hpp:48-77`）

この allocation の返り値は破棄され、呼び出し元で使われず、対応する free もありません。分岐に固有のログや返り値チェックはありません。失敗時の詳細な挙動は allocator 側の SYCL/Level Zero 実装に依存するため、ここでは Strata の動作として断定しません。（`sycl/src/kernels/dflash2_bench.cpp:615-616`）

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — 環境変数読み取り helper と `atoi()` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:614-620` — `gemm` ベンチ開始時の allocation とその後の処理。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — CLI mode と `run_gemm_bench()` の対応。
- `sycl/CMakeLists.txt:288-291,437-438` — parity build option と `dflash2_bench` target。
- `sycl/include/strata/sycl_queue.hpp:48-77` — `host_malloc_polled()` のビルド条件、環境変数判定、Level Zero 試行と SYCL fallback。
