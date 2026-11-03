# `GG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`GG` は、Strata の CUDA / HIP 用 packaging スクリプトで、ローカルの llama.cpp checkout を指定するビルド時環境変数です。各スクリプトは値を CMake の `STRATA_GGML_DIR` に渡します。エンジン起動後に読む環境変数ではありません。

## 値と判定

3 本のスクリプトはいずれも `set -eu` の後に `GG=${GG:?GG=<llama.cpp checkout at the pinned commit>}` を評価します。

| `GG` の状態 | スクリプトでの扱い |
|---|---|
| 未設定 | 必須パラメーター展開が失敗し、スクリプトはそこで停止する |
| 空文字 | `:?` の null 判定により失敗し、スクリプトはそこで停止する |
| 空でない値 | 文字列を追加変換せず、引用して `-DSTRATA_GGML_DIR="$GG"` として CMake に渡す |

値が実在するディレクトリか、指定 checkout が期待する commit かを、この変数の展開箇所では検証しません。後続の CMake 処理がパスを使います。

## 有効になる条件

`GG` は次の packaging スクリプトを実行するときに使われます。

- NVIDIA CUDA の DSV41 エンジン: `packaging/build_dsv41_cuda.sh`
- NVIDIA CUDA の split エンジン: `packaging/build_split_cuda.sh`
- AMD HIP の split エンジン: `packaging/build_split_hip.sh`

これらのスクリプトは CMake に `STRATA_NATIVE_EXPERTS=ON` を指定します。CMake は `STRATA_GGML_DIR` が空でなければ、そのディレクトリ配下の `ggml` を `add_subdirectory` で取り込みます。空の場合は pinned commit を FetchContent で取得する経路がありますが、上記スクリプトでは `GG` が必須なので、その既定経路には進みません。通常の実行ファイルやサーバーの実行時設定としての参照は見つかりませんでした。

## 実行時の詳細

値はスクリプト開始時に一度シェル変数へ展開され、その後 CMake の configure 引数として渡されます。各スクリプトは `set -e` を有効にしているため、必須値が欠けるとその場で停止します。空でない値でも checkout の構造が合わない場合は、CMake が `STRATA_GGML_DIR` 配下を使う configure 処理で失敗し得ます。Strata の実行時ログや推論動作を `GG` が直接変える処理はありません。

## 根拠

- `packaging/build_dsv41_cuda.sh:13-18,28-31`: 必須値の取得と CUDA DSV41 用 CMake への転送。
- `packaging/build_split_cuda.sh:12-18,22-25`: 必須値の取得と CUDA split 用 CMake への転送。
- `packaging/build_split_hip.sh:17-25,30-34`: 必須値の取得と HIP split 用 CMake への転送。
- `CMakeLists.txt:2047-2050,2104-2110`: `STRATA_GGML_DIR` の説明、空でない場合のローカル ggml 取り込み、および空の場合の pinned checkout 取得。
- `CMakeLists.txt:2284-2293,2526-2540`: CUDA / HIP の MMQ 構成でも指定 checkout 配下の ggml ソースを参照する箇所。
