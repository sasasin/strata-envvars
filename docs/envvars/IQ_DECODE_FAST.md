# `IQ_DECODE_FAST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

これは Strata 実行時の環境変数ではなく、SYCL エンジンを構成する二つのビルド用シェルスクリプトが読む環境変数である。値は CMake の `STRATA_SYCL_IQ_DECODE_FAST` に渡され、ON の場合は Q2 の packed decode、IQ4 lookup、IQ3_S sign 処理に使う six compile definitions を有効にする。OFF ではそれらの定義を追加せず、各ソースにある従来 helper の分岐が残る（`engine/sycl/tools/build.sh:38-44`、`tools/packaging/build_sycl_linux.sh:48-51`、`engine/sycl/CMakeLists.txt:51-58`）。

Strata の実行ファイルがこの名前を読んだり、起動時・リクエストごとに切り替えたりする実装は見つからなかった。実行時にこの変数を設定しても、すでに作られたバイナリの処理は変わらない。影響範囲は `engine/sycl` の SYCL build に限られ、CUDA/HIP/Metal や CLI・サーバー設定のスイッチではない（候補名の全参照を確認。実装箇所は上記二つの build script と CMake 設定のみ）。

## 値と判定

| 読み取り経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/sycl/tools/build.sh` | unset または空文字は `${IQ_DECODE_FAST:-ON}` により `ON` | `ON`、`1`、`true` など CMake が真と判定する値 | `OFF`、`0`、`false` など CMake が偽と判定する値 |
| `tools/packaging/build_sycl_linux.sh` | unset または空文字は `${IQ_DECODE_FAST:-ON}` により `ON` | 同上 | 同上 |
| `cmake -S engine/sycl` を直接実行 | `STRATA_SYCL_IQ_DECODE_FAST` の CMake option 既定値は `ON` | `-DSTRATA_SYCL_IQ_DECODE_FAST=<値>` が真なら有効 | 同値が偽なら無効 |

シェル側は未設定と空文字を区別せず `ON` に置き換える。非空値は文字列比較・数値 parse せず `-DSTRATA_SYCL_IQ_DECODE_FAST=<値>` として渡すため、`0anything` も Strata スクリプトが無効値として弾くことはない。その値を真偽として解釈するのは CMake の `option` / `if` であり、Strata 独自の入力検証、警告、fallback はない（`engine/sycl/tools/build.sh:40-41`、`tools/packaging/build_sycl_linux.sh:49-50`、`engine/sycl/CMakeLists.txt:54-58`）。

## 有効になる条件

- `engine/sycl` の CMake build に限る。SYCL 以外の engine build にはこの option の定義がない（`engine/sycl/CMakeLists.txt:1-11, 50-58`）。
- option が真で configure されると six macros が追加される。CMake のこの分岐には GPU 世代、AOT/JIT、モデル形式、サーバーモードによる条件分けはない（`engine/sycl/CMakeLists.txt:51-58`）。
- `engine/sycl/tools/build.sh` は `$b/build.ninja` がない場合にだけ、この変数を含む初回 configure を行う。既存の `build.ninja` がある build directory では、このスクリプトは `IQ_DECODE_FAST` を再 configure しないため、後から環境値を変えてもその build directory の設定は切り替わらない（同 `:38-44`）。
- Linux package script は毎回 CMake configure にこの値を渡す（`tools/packaging/build_sycl_linux.sh:18-19, 40-51`）。`STRATA_CMAKE_EXTRA` も同じ configure に渡されるため、同じ CMake option を追加指定した場合の最終値は CMake の引数・cache の解決に従う（同 `:46-50`）。
- `--` などの CLI 引数、別の実行時環境変数、モデルのロード状態による優先順位・上書きはない。SYCL CMake option を直接指定した場合は、候補環境変数の値ではなく CMake option の値が compile definitions を決める（`engine/sycl/CMakeLists.txt:54-58`）。

## 実行時の詳細

読み取りは build script 実行中のシェル展開時であり、実行ファイルの起動時ではない。`engine/sycl/tools/build.sh` では新規 configure 時に限り、option の真偽が compile definition へ変換される。ON のとき `STRATA_Q2_WORD_FAST`、`STRATA_IQ4NL_LUT_SWAR`、`STRATA_IQ4XS_LUT_SWAR`、`STRATA_IQ4_LUT_SWAR`、`STRATA_IQ3S_SIGN_FAST`、`STRATA_IQ3S_SIGN_APPLY_FAST` を定義する（`engine/sycl/CMakeLists.txt:54-58`）。

これらはコンパイル時の分岐で使われる。たとえば `STRATA_Q2_WORD_FAST` は `q2_decode8` の packed integer arithmetic と従来の `dpct::byte_level_permute` 実装を選び分け（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:135-153`）、IQ3_S sign helper は fast macro の有無で処理を選ぶ（同 `:199-219`）。IQ4_NL の lookup も SWAR helper と従来 lookup の分岐を持つ（同 `:444-464`）。OFF で従来側が選ばれる例は同 `:135-153, 444-464, 520-540` と `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1785-1805` にある。

したがって、実行プロセスでの再読込・static cache・子プロセスへの転送は該当しない。値を変更して効かせるには、対象の SYCL build を再 configure / rebuild する必要がある。特に前述の `build.sh` の既存 Ninja build directory は、この変数だけでは再 configure されない。

## ログと測定値

変数値に応じた Strata 固有の起動ログ、警告、終了コード分岐は見つからなかった。build script は通常の CMake/build 出力を扱い、`engine/sycl/tools/build.sh` は `BUILD EXIT <rc>` など一般的な build 結果を出す（同 `:44-50`）。

`docs/INTEL.md:584-590` は、2 枚の Arc Pro B65、Qwen3.8-Flash-Next GSQ-RCO IQ3_S（全 experts resident、layer split、`--spec 2 --pipeline-windows 2`、int8 KV、AOT `bmg-g31`）で、build option と14個の decode control の組合せが decode を4K prompt で +9.7%、free-form answer で +11.1% と記載し、この build option 単独の寄与を +5.9% としている。これは同資料に記載された測定値であり、本調査で再測定した値ではない。

## 根拠

- `engine/sycl/tools/build.sh:3-4, 38-44` — 変数の説明、unset/empty の既定値、初回 configure 条件。
- `tools/packaging/build_sycl_linux.sh:18-19, 40-51` — Linux package build における値の展開と CMake configure。
- `engine/sycl/CMakeLists.txt:50-58` — option の既定値、compile definitions。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:135-153, 199-219, 444-464, 520-540`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1785-1805` — compile-time 分岐の実装。
- `docs/INTEL.md:582-590` — 測定条件と資料記載値。
