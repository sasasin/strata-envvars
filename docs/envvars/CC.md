# `CC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`CC` は、Strata のセットアップがローカル build を行うときに C コンパイラを選ぶために使われる。`terminal/setup.py` の `host_compiler_defs()` が値を `-DCMAKE_C_COMPILER=...` として CMake に渡す。エンジン本体の CUDA build、CUDA 画像 encoder build、NVIDIA 用画像生成 engine build が対象で、Strata の通常のモデル起動や ready-made engine の取得には関与しない（`terminal/setup.py:6847-6858`, `6902-6946`, `6957-6965`, `5922-5932`, `9614-9625`）。

同じ名前は、独立した SYCL build script `engine/src/inkling2/sycl/build_inkling_sycl.sh` でも zstd の C ソースをコンパイルする compiler として読まれる。またテスト用 `engine/tests/quant/make_golden.sh` は GCC 13 の確認に使う。これらはセットアップの `host_compiler_defs()` とは別の処理である（`engine/src/inkling2/sycl/build_inkling_sycl.sh:14-15,34-39`, `engine/tests/quant/make_golden.sh:14-21`）。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 設定時に使われる値 | 無効値・失敗時 |
|---|---|---|---|
| Terminal の CUDA build helper | `os.environ.get("CC", "")` は空文字になり、空白除去後も空なら明示的な `-DCMAKE_C_COMPILER` を渡さない。子プロセスには元の環境が引き継がれる | 値の前後を Python の `.strip()` で除いた文字列全体を `-DCMAKE_C_COMPILER=<値>` にする。`gcc` や `/path/to/cc` など。文字列の真偽だけを判定し、数値・実行可能性・大文字小文字は setup 側で検証しない | 非空の任意文字列は CMake に渡る。setup 側に無効値の fallback はなく、configure/build の失敗が `run()` の非ゼロ終了処理へ進む |
| SYCL 個別 build script | unset または空文字なら `${CC:-icx}` により `icx` | 指定文字列をそのまま C compiler として使い、引用して実行する | fallback や値検査はなく、起動できなければ `set -e` の script が失敗する |
| 量子化 golden 生成 script | unset または空文字なら `${CC:-gcc}` により `gcc` | 指定値を compiler command として使い、`-dumpfullversion` の結果が `13.*` か確認する | GCC 13.x 以外・起動失敗時は説明を stdout に出して exit 2 |

Terminal setup の判定は `terminal/setup.py:6853-6858`、SYCL script は `engine/src/inkling2/sycl/build_inkling_sycl.sh:14-15,38`、golden script は `engine/tests/quant/make_golden.sh:14-17` にある。setup では前後の空白は除かれるが内部空白の正規化やパス解決は行わない。SYCL/golden script は `.strip()` 相当の処理をしない。たとえば setup の `CC="   "` は明示的な `-D` 定義を作らず、`CC="gcc "` は定義値を `gcc` にする。どちらも `run()` は元の `os.environ` を子プロセスに引き継ぐため、`-D` を作らない場合の CMake 側の環境変数解釈はここでは規定しない。SYCL script の `CC="   "` は空ではないのでそのまま実行対象となり、golden script では空白だけの値も compiler 名として検査に進む。

## 有効になる条件

- Terminal setup が実際に source build の configure を呼ぶこと。ready-made engine が選ばれて更新不要なら、CC は build 定義に使われない（`terminal/setup.py:9614-9625`, `6902-6929`）。
- `host_compiler_defs()` は CUDA engine build と NVIDIA image encoder / CUDA image generator の build で呼ばれる。CUDA engine build は `build_engine()` 経路、image generator は `backend == "cuda"` の経路に限られる（`terminal/setup.py:6941-6946`, `6957-6965`, `5900-5932`）。
- HIP engine build は `host_compiler_defs()` を呼ばず、CMake に `CMAKE_HIP_COMPILER` を指定する。この経路で CC は Strata setup から適用されない（`terminal/setup.py:5678-5701`）。HIP image encoder と CPU image encoder の build も同 helper を呼ばない（`terminal/setup.py:5770-5794`）。
- CPU 画像 encoder など `host_compiler_defs(False)` の呼び出しでは CC と CXX の定義は作られるが、CUDA host compiler 定義は作られない。CUDA を含む build だけ `CMAKE_CUDA_HOST_COMPILER` も設定する（`terminal/setup.py:6853-6858`, `6957-6965`）。
- 既存の local build がすでに有効と判定されると `build_engine()` はコンパイルを省略するため、CC の変更だけで rebuild にはならない（`terminal/setup.py:6925-6929`）。再 build に進んだ場合は既存 build folder にも CMake の `-D` 定義を渡す（`terminal/setup.py:6793-6802`, `6848-6852`）。

## 実行時の詳細

Terminal setup は `host_compiler_defs()` の呼び出し時に環境を読み、値を CMake の configure 引数へ変換する。setup 起動時に別途保存する cache はなく、この helper が呼ばれるたびに `os.environ` を参照する。CMake configure の後に同じ build folder で `cmake --build` を実行する。CC は engine の stamp や `engine_ok` 判定には含まれないので、既存 local build が有効なら新しい値を読む build 経路自体が省略される（`terminal/setup.py:6847-6858`, `6793-6802`, `6913-6929`）。

`cmake_build()` は setup の `run()` を通じて元の環境も子プロセスへ渡すが、Strata が明示的に設定する compiler 定義は次のとおり。この helper は `CXX` と `CUDAHOSTCXX` も読み取る。`CXX` は `CMAKE_CXX_COMPILER` に渡される。`CUDAHOSTCXX` は前後空白を除いた値があればそれを使い、空なら `CXX` の値を `CMAKE_CUDA_HOST_COMPILER` に渡す。これらの変数が別々に設定されていても CC 自体の値は上書きしない（`terminal/setup.py:6853-6858`）。setup に CC 用 CLI option はなく、この helper 内に別の compiler 優先順位や CC の fallback はない。

SYCL script と golden script は各スクリプト実行時に shell parameter expansion で CC を評価する。SYCL script は指定 compiler を zstd の `.c` ファイルに使い、後続 C++ / SYCL ソースは `ICPX`（既定 `icpx`）でコンパイルする。golden script は指定 compiler のバージョン確認後、`run_oracle.sh` から CMake に CC を渡すのではなく、単にこの環境を継承して oracle build を実行する。`run_oracle.sh` 自体には CC の値を読み取る記述はない（`engine/src/inkling2/sycl/build_inkling_sycl.sh:14-15,34-43`, `engine/tests/quant/make_golden.sh:14-21`, `engine/tests/quant/run_oracle.sh:12-35`）。

## ログと測定値

Terminal setup の `cmake_build()` は実行する configure コマンドを `  > ` 付きで表示し、失敗した command の非ゼロ終了は `run()` のエラー処理へ進む。CC 専用の警告文や値の検査ログはない（`terminal/setup.py:1131-1155`, `6793-6820`）。SYCL script は開始時に `ICPX` を含む build 情報を表示するが CC の値は表示しない。golden script は GCC 13.x 条件を満たさない場合、`make_golden.sh: needs GCC 13.x (CC=...)` を表示して exit 2 する（`engine/src/inkling2/sycl/build_inkling_sycl.sh:14-17`, `engine/tests/quant/make_golden.sh:15-17`）。測定値は該当しない。

## 根拠

- Terminal setup の読み取りと CMake 定義: `terminal/setup.py:6847-6858`
- CMake configure/build と非ゼロ終了時の再試行: `terminal/setup.py:6793-6820`, `1131-1155`
- CUDA engine の build 判定・定義適用: `terminal/setup.py:6902-6946`
- 画像 encoder と image generator の適用経路: `terminal/setup.py:5922-5932`, `6957-6965`
- ready-made engine / HIP の除外経路: `terminal/setup.py:5678-5701`, `9614-9625`
- SYCL script と golden 生成 script: `engine/src/inkling2/sycl/build_inkling_sycl.sh:14-43`, `engine/tests/quant/make_golden.sh:14-21`
