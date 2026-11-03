# `METAL_CPP_DIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

macOS 向け DeepSeek-V4.1 engine の package build script が、Apple の `metal-cpp` ヘッダーを置いたディレクトリを CMake に渡します。これは Strata の実行時環境変数ではなく、`packaging/mac/build_dsv41_engine.sh` のビルド時設定です。通常の Metal setup (`metal/setup_mac.py`) は環境変数を参照せず、`third_party/metal-cpp` にヘッダーを取得して CMake に渡します（`metal/setup_mac.py:82-97,126-143`）。

## 値と判定

| 環境値 | shell script が使う値 |
|---|---|
| 未設定 | `$HOME/strata-mac/metal-cpp` |
| 空文字 | `$HOME/strata-mac/metal-cpp` |
| 空でない値 | その値をそのまま使用 |

`METAL_CPP_DIR=${METAL_CPP_DIR:-$HOME/strata-mac/metal-cpp}` という Bash の `:-` 展開なので、数値変換、文字列比較、正規化、範囲検査はありません。相対パスを絶対化する処理もこの script にはありません。環境値は同名の CMake cache 変数 `-DMETAL_CPP_DIR=...` として渡されます（`packaging/mac/build_dsv41_engine.sh:36,43-45`）。この wrapper に `METAL_CPP_DIR` 用の CLI 引数はありません。

## 有効になる条件

- `packaging/mac/build_dsv41_engine.sh` を実行する場合にだけ、この shell 環境値が参照されます。同 script は macOS 上で実行することを前提にしています（`packaging/mac/build_dsv41_engine.sh:2,6-13`）。
- script が選んだ build directory 内の `strata_ds4` が実行可能なら CMake configure をスキップするため、変更した環境値は既存 build に反映されません。実行可能ファイルがない場合に限り CMake を起動します（既定 build directory は `$ROOT/build-metal`、`packaging/mac/build_dsv41_engine.sh:22,27-28,41-46`）。
- CMake は値の指す場所に `Metal/Metal.hpp` が存在するか確認します。存在しない場合（未設定相当の空 CMake cache 値や不正なパスを含む）は STATUS メッセージを出して `metal/CMakeLists.txt` の残りを return し、Metal device runtime と engine の target を定義しません（`metal/CMakeLists.txt:51-55`）。ヘッダーが存在する場合、ディレクトリは `strata_gpu_metal` と `ds4_rt_gpu` の include directory に設定されます（`metal/CMakeLists.txt:57-62,160-165`）。
- CMake を直接実行する場合、OS の `METAL_CPP_DIR` 環境変数を CMake はこのコードで読みません。CMake の `METAL_CPP_DIR` cache variable を `-D` などで設定する必要があります（`metal/CMakeLists.txt:11,51-55`）。

## 実行時の詳細

環境値の読み取りは wrapper の実行時に shell が assignment expansion を行う時点で起きます。wrapper が CMake configure を行う場合、その値を `-DMETAL_CPP_DIR=...` として渡し、CMake 側では `PATH` 型 cache variable として扱います。Strata の C++/Python 実行コードがこの名前を読む箇所はありません。

wrapper は CMake configure の失敗なら `exit 1` します（`packaging/mac/build_dsv41_engine.sh:43-45`）。一方、ヘッダーが見つからない場合の CMake `message(STATUS ...)` と `return()` は configure を即座に失敗扱いにはしません。その後 wrapper は `ninja ... strata_ds4` を実行し、失敗時に `exit 1` します（`packaging/mac/build_dsv41_engine.sh:47`）。CMake のメッセージは `strata metal: METAL_CPP_DIR is not set: the device runtime and the engine are not built` です（`metal/CMakeLists.txt:52-54`）。

同名の他の参照は CI workflow の CMake `-D` に固定パスを指定する箇所、CMake の cache 変数定義・検査・include 設定、および `setup_mac.py` がローカル変数 `mcpp` を `-D` に渡す箇所です（`.github/workflows/metal-build.yml:51`, `metal/CMakeLists.txt:11,51-55,60,163`, `metal/setup_mac.py:131-143`）。CI は環境変数を参照せず、`setup_mac.py` の `mcpp` は `third_party/metal-cpp` を準備する関数から得ます（`metal/setup_mac.py:82-97,131-143`）。これらは `METAL_CPP_DIR` 環境変数の読み取りではありません。

## 根拠

- `packaging/mac/build_dsv41_engine.sh:34-47` — wrapper の既定値、CMake 起動条件、CMake への値の転送、後続 build。
- `metal/CMakeLists.txt:51-62,160-165` — CMake cache 変数、ヘッダー検査と include directory の設定。
- `metal/setup_mac.py:82-97,126-149` — 標準 setup のヘッダー取得と CMake 呼び出し。環境変数ではなくローカルパスを渡す。
- `.github/workflows/metal-build.yml:51` — CI が固定パスを `-D` で指定。
