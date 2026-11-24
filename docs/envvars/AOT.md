# `AOT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`AOT` は SYCL 用ビルドスクリプトが CMake の `STRATA_SYCL_AOT` に渡すビルド時設定で、指定時は GPU device code を `spir64_gen` 向けにコンパイルする。未指定または空なら CMake は `-fsycl` のみを使う JIT 用構成にする。Strata のエンジン実行時に `AOT` を読む箇所はなく、ビルド成果物の構成を選ぶ変数である（`engine/sycl/tools/build.sh:38-44`、`tools/packaging/build_sycl_linux.sh:20-24,49-59`、`engine/sycl/CMakeLists.txt:50,98-105`）。

この値は次の二つの Strata 所有スクリプトで読まれる。開発用 `engine/sycl/tools/build.sh` は値を検証せず CMake に渡し、さらに `bmg` / `lnl` 始まりかを既知の `ocloc` 不具合の事前チェックに使う。Linux engine package 用 `tools/packaging/build_sycl_linux.sh` は Battlemage 用値だけを受け付ける。どちらも実行時の CLI 引数や環境変数による選択ではない。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `engine/sycl/tools/build.sh` | `${AOT:-}` は空文字。CMake に空の `STRATA_SYCL_AOT` を渡す | 任意の非空文字列を CMake に渡す（`0`、`1`、`true`、`false` もすべて非空）。`bmg-g31`、`lnl-*`、`pvc-*` はそれぞれ記載の CMake 分岐に一致 | スクリプト段階では無効値検査なし。空白や未知の文字列も転送され、CMake/toolchain の処理に委ねられる |
| `tools/packaging/build_sycl_linux.sh` | `${AOT:-}` が空文字。JIT package の経路 | `bmg-*` 1 件、または `bmg-*,bmg-*` の2件（例 `bmg-g21,bmg-g31`） | `0`、`1`、`true`、`false`、空白、Battlemage 以外の文字列など上記以外は stderr に `build_sycl_linux.sh: AOT is empty (the release package) or a Battlemage device list such as bmg-g21,bmg-g31` を出して status 2 で終了 |

いずれも空文字は未設定と同じ値として扱われる（開発用は `${AOT:-}`、package 用は代入後の `$aot` が空かを判定）。値を大文字小文字変換したり、数値として parse したりする処理はない。開発用の事前チェックは Bash の正規表現 `^(bmg|lnl)` なので、文字列全体ではなく先頭だけを照合する。package 用の `case` は大文字小文字を区別し、シェル glob による形状検査であり device 名の詳細までは検証しない（`engine/sycl/tools/build.sh:25`、`tools/packaging/build_sycl_linux.sh:20-24`）。

## 有効になる条件

- SYCL をビルドし、`engine/sycl/tools/build.sh` または `tools/packaging/build_sycl_linux.sh` のいずれかを使うこと。CUDA/HIP や既に作成済みのバイナリの実行時にはこの環境変数を読む経路がない（各スクリプトの CMake 呼び出し: `engine/sycl/tools/build.sh:40-41`、`tools/packaging/build_sycl_linux.sh:49-51`）。
- `engine/sycl/tools/build.sh` で `AOT` が非空なら、CMake は `-fsycl-targets=spir64_gen` と `-device ${STRATA_SYCL_AOT}` を含む linker option を構成する。空なら `spir64_gen` の AOT target は加えず、JIT 用の `spir64` オプションを使う（`engine/sycl/CMakeLists.txt:98-124`）。
- `bmg` または `lnl` で始まる値は `STRATA_XMX_SG16` を定義する。`pvc` で始まる値は `STRATA_NO_DG2_XMX` を定義する。これらは文字列の先頭一致で、先頭一致しない未知値でも AOT の CMake 分岐自体は非空判定で入る（`engine/sycl/CMakeLists.txt:72-76,98-105`）。
- `STRATA_SYCL_I8_ESIMD=AUTO` かつ AOT が非空で `bmg` / `lnl` 始まりでない場合、CMake は fused int8 ESIMD kernels を stub にする。`STRATA_SYCL_I8_ESIMD=OFF` なら AOT 値にかかわらず stub になる（`engine/sycl/CMakeLists.txt:78-97`）。
- `STRATA_SYCL_TLA_ATTN=ON` を指定する構成では `STRATA_SYCL_AOT` が厳密に `bmg-g31` でなければ configure が fatal error になる（`engine/sycl/CMakeLists.txt:313-323`）。
- `STRATA_SYCL_TLA_EXPERT_GU` の自動有効化条件には、AOT が空、または `bmg-g21` / `bmg-g31` だけからなるカンマ区切りリストであることが含まれる。Level Zero と必要なローカル header も必要（`engine/sycl/CMakeLists.txt:338-362`）。
- 開発用スクリプトでは `AOT` が `bmg` / `lnl` 始まり、`I8_ESIMD` が `OFF` でなく、`ALLOW_BAD_OCLOC` が `1` でない場合に `ocloc --version` を調べる。既知の版 `26.22.38646` または `26.22.38646.*` なら警告を stderr に出して configure/build 前に status 2 で終了する（`engine/sycl/tools/build.sh:15-35`）。
- package 用スクリプトでは AOT 値が非空なら `ocloc` が PATH 上に必要で、なければ `build_sycl_linux.sh: AOT needs ocloc (apt install intel-ocloc)` を stderr に出して status 2 で終了する。package 用スクリプトの許容値は Battlemage 形状に限定される（`tools/packaging/build_sycl_linux.sh:20-24,37`）。

## 実行時の詳細

`AOT` は各シェルスクリプトの起動時に参照され、その呼び出し中の値が CMake configure 引数に展開される。実行中に環境を書き換えて再評価する処理や、エンジンからの再読み取り・cache はない。開発用スクリプトは `$BUILD_DIR`（既定 `$repo/build-sycl`）に `build.ninja` が既にあるとき CMake configure を省くため、新しい `AOT` 値は既存 build directory の cache には反映されない。スクリプト自身も「既存 build folder keeps its cache」と記している（`engine/sycl/tools/build.sh:38-43`）。package 用スクリプトは毎回 `cmake -S engine/sycl -B "$build" ...` を実行し、非空値だけ `-DSTRATA_SYCL_AOT=$aot` を渡す（`tools/packaging/build_sycl_linux.sh:49-51`）。

`AOT` の値は子プロセス CMake にコマンドライン定義として渡され、コンパイル対象・SYCL flags・一部の compile definitions を決める。ビルド後の実行ファイルが `AOT` の環境値を参照するコードは、候補名の全参照検索では確認できなかった。package 用スクリプトは生成した `BUILD.json` に `AOT <値>` または `JIT from SPIR-V` を記録し、成果物を package 化する（`tools/packaging/build_sycl_linux.sh:57-59`）。

## ログと測定値

package 用スクリプトは許容外の値、`ocloc` 不在を上記の文言で stderr に報告して status 2 で終了する。開発用スクリプトは既知の `ocloc` 版を検出すると `build.sh: this image's ocloc is ... It is known to crash while it compiles the int8 ESIMD kernels for AOT=... (#3219).` を含む案内を stderr に出して status 2 で終了する。CMake 側では不適合な `STRATA_SYCL_TLA_ATTN` の組み合わせが fatal error になる。通常の AOT/JIT 選択だけを理由に Strata が出す実行時ログは見つからなかった（`engine/sycl/tools/build.sh:25-35`、`tools/packaging/build_sycl_linux.sh:20-24,37`、`engine/sycl/CMakeLists.txt:317-323`）。

`docs/INTEL.md` と `docs/INTEL_ARC.md` は空値を JIT、Battlemage target を AOT とする説明で、現行 CMake の選択と整合する（`docs/INTEL.md:69-87`、`docs/INTEL_ARC.md:75-76,109-110`）。これらの文書にある起動時間や性能の記述はここでは測定値として引用しない。調査はソースを読む範囲に限り、build・GPU 実行・性能測定・テストは行っていない。

## 根拠

- `engine/sycl/tools/build.sh:15-44` — 開発用スクリプトの値判定、警告・終了、CMake への転送、build directory cache。
- `tools/packaging/build_sycl_linux.sh:18-59` — package 用スクリプトの許容値、ocloc 確認、CMake 転送、build metadata。
- `engine/sycl/CMakeLists.txt:50-124` — AOT target 判定、compile definition、ESIMD 条件と SYCL flags。
- `engine/sycl/CMakeLists.txt:313-362` — AOT target に依存する TLA configure 条件。
