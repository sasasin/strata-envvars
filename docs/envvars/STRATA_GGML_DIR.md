# `STRATA_GGML_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

この名前は Strata のエンジンが実行時に読む設定ではありません。Strata の一部ビルド用シェル／バッチスクリプトが環境変数から llama.cpp の checkout のパスを取り、CMake の `-DSTRATA_GGML_DIR=...` に転送します。CMake 側で定義されているのは環境変数ではなく `PATH` 型の cache 変数です。CMake を直接実行するときは環境に設定するだけでは足りず、`-DSTRATA_GGML_DIR=<checkout>` を指定する必要があります。

指定した tree は、ビルド対象の ggml ソースとして使われます。主 CMake では `STRATA_NATIVE_EXPERTS` が有効なとき、空なら commit `3cf03257f219afbe7334045ff7c6a06ac68c627d` の llama.cpp を FetchContent し、非空なら `<path>/ggml` を `add_subdirectory` します。CUDA の MMQ trellis instance の有無など、一部ソース選択にも指定 tree のファイルが使われます。SYCL でも `STRATA_NATIVE_EXPERTS` が有効なら同じ cache path を使います。Metal 専用 CMake はエンジンをビルドする場合に checkout を必須とします（`CMakeLists.txt:1898-1901,1908-1910,1955-1967,2099-2124,2135-2145`; `sycl/CMakeLists.txt:178-199`; `metal/CMakeLists.txt:71-89`）。

## 値と判定

値は真偽値や数値に変換されず、パス文字列として転送されます。空文字・未設定の扱いはラッパーごとに異なります。

| 読み取り経路 | 未設定／空文字 | 非空文字列 | 追加の扱い |
|---|---|---|---|
| `spark/build_engine.sh` | どちらも `$repo/third_party/llama.cpp` を使用 | 指定したパスを使う | `${VAR:-default}` のため空も既定値。`<path>/ggml/CMakeLists.txt` がなければ setup.py の `get_llama_cpp()` を呼び、それでも同じパスに見つからない場合は stderr に `build_engine.sh: no llama.cpp tree at ...` を出して終了コード 2（`spark/build_engine.sh:25,44-47`）。 |
| `packaging/mac/build_dsv41_engine.sh` | どちらも `$HOME/strata-mac/llamacpp` を使用 | 指定したパスを使う | `${VAR:-default}` のため空も既定値（`packaging/mac/build_dsv41_engine.sh:37,42-45`）。 |
| `tools/dsv41/build_hip_linux.sh` | 未設定・空なら CMake に渡さない | `-DSTRATA_GGML_DIR=<値>` として渡す | 空判定は `[ -n ... ]`。パスの存在確認はこのスクリプトではしない（`tools/dsv41/build_hip_linux.sh:9,16,19-25`）。 |
| `tools/dsv41/win/build_hip_win.bat`, `tools/hip/build_windows.bat` | 未定義なら CMake への `-D` 指定を省略 | `-D` に渡す。vision 用 llama path にも利用 | Windows の `\` を `/` に置換。HIP ビルド用 `build.ninja` がすでにあると CMake の再構成を省略する（`tools/dsv41/win/build_hip_win.bat:32-41`; `tools/hip/build_windows.bat:69-80,87-105`）。 |
| `packaging/build_vision_windows.bat` | 未定義なら `%SRC%\third_party\llama.cpp` を設定 | 指定したパスを使う | 空は未定義と同様。`\` を `/` に置換し、`tools/mtmd` がなければメッセージを出して終了コード 1。CMake へは `STRATA_GGML_DIR` でなく vision 用 `LLAMA_DIR` として渡す（`packaging/build_vision_windows.bat:16,37-40`）。 |
| `packaging/build_dsv41_windows.bat` | 未定義または空なら `set STRATA_GGML_DIR to the llama.cpp checkout` を表示して終了コード 2 | CMake の `-DSTRATA_GGML_DIR` に渡す | 事前のディレクトリ検証はこのスクリプトにない（`packaging/build_dsv41_windows.bat:5,11-20`）。 |

これらのスクリプトはパスの trim、存在しないパスの共通 fallback、または共通の優先順位を定義していません。空値の扱いを全経路に一般化できません。Windows 系ではパス区切りだけを置換します。

## 有効になる条件

- **主 CUDA/HIP ビルド**: CMake が `STRATA_NATIVE_EXPERTS` 有効の分岐に入った場合、指定した tree の `ggml` をビルドに加えます。未指定なら pinned commit の取得に進みます。値が不正、または `<path>/ggml` がない場合、CMake の configure で `add_subdirectory` が失敗します（`CMakeLists.txt:1908-1910,1955-1967`）。
- **CUDA の追加 MMQ ソース**: 指定 tree に `ggml/src/ggml-cuda/template-instances/mmq-instance-tqk6.cu` があるか、さらに `mmq-instance-tqp5.cu` があるかで trellis 型の選択が変わります。`STRATA_MMQ_TQ_OVERLAY` 経路では指定 tree または FetchContent tree が overlay の入力になります。これらは CUDA 分岐の configure 時判定です（`CMakeLists.txt:2099-2124,2135-2145`）。
- **SYCL**: `STRATA_NATIVE_EXPERTS` 有効時に指定 tree を使います。未指定時は CMake が pinned commit を FetchContent します（`sycl/CMakeLists.txt:178-199`）。
- **Metal**: `STRATA_METAL_ENGINE=OFF` ならその時点で CMake が return し、ggml path を検証しません。有効時は `<path>/ggml/CMakeLists.txt` が存在しないと `STRATA_GGML_DIR='<値>' is not a llama.cpp checkout` の fatal error になります（`metal/CMakeLists.txt:73-89`）。
- **ビルド用ラッパーに限る**: 上表の各 OS／スクリプトを使う場合のみ環境変数の値を取り込みます。直接の CMake 呼び出し、通常の Strata CLI、サーバー、モデル読み込み処理がこの環境変数を読む実装は見つかりませんでした。

## 実行時の詳細

値の読み取りは各ビルドスクリプトの実行中に行われ、設定した場合は configure 時に CMake cache へ渡されます。生成バイナリにこの環境変数の値を埋め込んで、エンジン実行時に再評価する処理はありません。ビルドディレクトリの再利用条件にも注意が必要です。`spark/build_engine.sh` は選択したパスを毎回 CMake に渡しますが、HIP の Linux/Windows helper は `build.ninja` があると初回 configure を省略します。Mac の DSV41 helper は実行ファイルがないときだけ configure します。したがってこれらの既存ビルドでは、環境値を変えただけで既存 CMake cache の設定が更新されるとは限りません（`spark/build_engine.sh:58-63`; `tools/dsv41/build_hip_linux.sh:19-25`; `tools/dsv41/win/build_hip_win.bat:32-43`; `tools/hip/build_windows.bat:69-80`; `packaging/mac/build_dsv41_engine.sh:41-47`）。

Strata の実行時ログ、警告、終了、timeout をこの変数が引き起こす経路はありません。観測される失敗はビルド側です。Windows の vision helper は `tools/mtmd` の不足を表示して終了し、Metal CMake は不正な checkout で fatal error、主 CMake は選択された `<path>/ggml` を configure に追加できないと configure が失敗します。Spark helper は上記の独自エラーを出します。外部 llama.cpp/ggml のビルド内部の挙動はここでは扱いません。

候補名の全参照を `rg` で確認しました。`CMakeLists.txt`、`sycl/CMakeLists.txt`、`metal/CMakeLists.txt` と setup.py / Metal setup の `-D` 引き渡しは CMake cache 変数の利用であり、環境から値を読む処理ではありません。setup.py と Metal setup は内部で得た `llama` path を渡しています（`setup.py:4821-4827,5944-5949`; `metal/setup_mac.py:126-142`）。`packaging/build_sycl_linux.sh` は別名の `LLAMA_CPP` を受け取り、`packaging/build_hip_linux.sh` は `LLAMA` を受け取ります。これらを `STRATA_GGML_DIR` の読み取りとは数えていません（`packaging/build_sycl_linux.sh:39-45`; `packaging/build_hip_linux.sh:21-25,58-62`）。
