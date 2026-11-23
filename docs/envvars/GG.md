# `GG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`GG` は通常の Strata 実行時設定ではなく、CUDA/HIP の split engine 用ビルドスクリプトが任意の llama.cpp checkout を ggml ソースとして CMake に渡すための環境変数です。読み取るのは `tools/packaging/build_split_cuda.sh` と `tools/packaging/build_split_hip.sh` だけです。どちらも空でない値を `-DSTRATA_GGML_DIR=<値>` として渡します（`tools/packaging/build_split_cuda.sh:16-17,23-25`、`tools/packaging/build_split_hip.sh:22-23,31-33`）。

ただし、これらのスクリプトが指定する `STRATA_BUILD_TESTS=OFF` と `STRATA_NATIVE_EXPERTS=ON` の組み合わせでは、既定の `STRATA_OWN_CPU_QUANT=ON` により ggml のソースツリーをビルドへ追加しません。そのため現行のスクリプト経路では、`GG` の値は CMake cache に渡されても split engine のビルド内容を変えません。CMake は ggml を追加するのをテスト有効時または `STRATA_OWN_CPU_QUANT=OFF` の場合に限り、それ以外は `Strata: no ggml in this build (own CPU pool, no MMQ, tests off)` を表示します（`engine/CMakeLists.txt:178-184,641-650`、`engine/cmake/strata_ggml.cmake:11-16,59-60`）。

## 値と判定

両スクリプトは `GG=${GG:-}` で値を取り込みます。シェルの parameter expansion により、未設定と空文字はどちらも空文字になり、同じ扱いです。空なら `ggml` 引数を空のままにし、非空なら `-DSTRATA_GGML_DIR=$GG` を組み立てます。文字列の内容、大小文字、数値としての妥当性は検査しません（`tools/packaging/build_split_cuda.sh:16-17`、`tools/packaging/build_split_hip.sh:22-23`）。

| ビルド経路 | unset / 空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA split (`build_split_cuda.sh`) | `STRATA_GGML_DIR` をコマンドラインに渡さず、CMake 側の空の既定値を使う | 任意の非空文字列を `-DSTRATA_GGML_DIR=...` として渡す。値自体の形式検査はない | 空文字は未設定と同じ。`0`、`false`、空白だけの文字列も「非空」として渡そうとする |
| HIP split (`build_split_hip.sh`) | `STRATA_GGML_DIR` をコマンドラインに渡さず、CMake 側の空の既定値を使う | 任意の非空文字列を `-DSTRATA_GGML_DIR=...` として渡す。値自体の形式検査はない | 空文字は未設定と同じ。`0`、`false`、空白だけの文字列も「非空」として渡そうとする |

`$ggml` は CMake 呼び出しで引用符なしに展開されるため、値に空白や glob 文字が含まれる場合はシェルの単語分割・pathname expansion の対象になります（`tools/packaging/build_split_cuda.sh:23-25`、`tools/packaging/build_split_hip.sh:31-33`）。このパスを渡す現行 split 経路では前述の条件により ggml を追加しないので、checkout の存在や構成を検査する処理もありません。一般の CMake 経路では `STRATA_GGML_DIR` が空でなければそのディレクトリを選び、空なら vendored `engine/third_party/strata-ggml` を選びます（`engine/cmake/strata_ggml.cmake:11-16`）。

## 有効になる条件

- `GG` を読むには CUDA または HIP split engine のビルドスクリプトを実行する必要があります。CUDA スクリプトは `STRATA_ENABLE_CUDA=ON`、HIP スクリプトは `STRATA_ENABLE_HIP=ON` として CMake を呼び出します（`tools/packaging/build_split_cuda.sh:23-25`、`tools/packaging/build_split_hip.sh:31-34`）。
- そのスクリプト経路は `STRATA_BUILD_TESTS=OFF` を指定し、`STRATA_NATIVE_EXPERTS=ON` を指定します。`STRATA_OWN_CPU_QUANT` は CMake の既定値 `ON` で、スクリプトはこれを上書きしません。その結果、ggml の `add_subdirectory` は実行されず、非空の `GG` も checkout 選択に使われません（`engine/CMakeLists.txt:178-184,641-650`、`engine/cmake/strata_ggml.cmake:59-60`）。
- 一般の CMake 構成で値を実際に使う条件は、`STRATA_NATIVE_EXPERTS=ON` かつ `STRATA_BUILD_TESTS=ON`、または `STRATA_NATIVE_EXPERTS=ON` かつ `STRATA_OWN_CPU_QUANT=OFF` です。前者または後者で ggml が追加されるときに限り `STRATA_GGML_DIR` の非空値が vendored tree に優先します（`engine/CMakeLists.txt:641-647`、`engine/cmake/strata_ggml.cmake:11-16,59-60`）。ただし、これらは `GG` を読まない別経路であり、CMake へ環境変数 `GG` 自体が自動で渡る根拠はありません。

## 実行時の詳細

両スクリプトは実行時に一度 `GG` をシェル変数へ代入し、その同じ実行内の CMake configure 呼び出しにだけ反映します。実行中に親環境の値を変えて再評価する仕組みや、エンジン実行時の読み取り・cache はありません。両スクリプトは configure の直前に build directory の `CMakeCache.txt` を削除するため、前回の `STRATA_GGML_DIR` cache 値を引き継ぎません（`tools/packaging/build_split_cuda.sh:16-25`、`tools/packaging/build_split_hip.sh:22-35`）。

スクリプトは非空値を CMake に渡しますが、既定の split build では CMake が ggml を追加せず、その値に基づくソース選択もパス検証も起きません。実際に ggml を追加する別の CMake 構成で無効な checkout を指定した場合、`add_subdirectory(<checkout>/ggml ...)` が構成失敗の経路になります（`engine/cmake/strata_ggml.cmake:12-16,59-60`）。

## ログと測定値

既定の split build で ggml を追加しない場合、CMake は `Strata: no ggml in this build (own CPU pool, no MMQ, tests off)` を status メッセージとして出します。これは `GG` の有無にかかわらず同じ条件で表示されます（`engine/CMakeLists.txt:646-650`）。`GG` 固有の成功・警告ログや、変数に関する測定値はありません。CMake 構成や後続の `ninja` が別の理由で失敗する場合はスクリプトが `set -e` により停止しますが、`GG` の値に対応する独自エラー文言は実装されていません（`tools/packaging/build_split_cuda.sh:12,23-30`、`tools/packaging/build_split_hip.sh:17,31-38`）。

## 根拠

- `tools/packaging/build_split_cuda.sh:12-30` — `GG` の読取り、空値判定、CMake への引渡し、cache の削除。
- `tools/packaging/build_split_hip.sh:17-38` — HIP 側の同じ処理。
- `engine/CMakeLists.txt:178-184,641-650` — `STRATA_OWN_CPU_QUANT` の既定値、ggml 追加条件、未追加時の status。
- `engine/cmake/strata_ggml.cmake:11-16,59-60` — override / vendored tree の選択と ggml サブディレクトリ追加。
