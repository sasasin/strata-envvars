# `STRATA_HIP_COMPAT_INCLUDE_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この名前は実行時の環境変数ではなく、HIP ビルド用 CMake 変数です。HIP の CUDA 互換ヘッダーが置かれるディレクトリを指し、HIP 用 interface target の include path と強制 include のパスに使われます。候補一覧にはありますが、Strata ソースにこの名前の環境変数を読む処理は見つかりませんでした。

## 値と判定

`cmake/hip_backend.cmake` が `STRATA_HIP_COMPAT_INCLUDE_DIR` を `${CMAKE_CURRENT_SOURCE_DIR}/include/strata/hip_compat` に設定します。環境変数の未設定・空文字・値の parse による分岐はありません。CMake の `set()` による通常変数として設定され、ここでは `option()` や `$ENV{...}` による環境からの読み取りを行いません。

## 有効になる条件

`STRATA_ENABLE_HIP` が有効なビルド経路で使われます。HIP backend では CMake が `strata_hip_runtime` interface library を作り、この変数のディレクトリを include path に追加します。CUDA backend では CMake の GPU include path は CUDA toolkit 側に設定され、この変数の参照箇所は HIP backend 用です。

## 実行時の詳細

CMake configure 時にソースツリー内の `include/strata/hip_compat` を値として設定します。HIP 用 target にこのパスと一般の `include` を include directory として登録し、同ディレクトリの `cuda_runtime.h` を C++ ソースへ強制 include します。`CMakeLists.txt` も HIP の GPU include directories と HIP 専用 prefill source の include path に参照します。実行ファイル起動後の処理や子プロセスへの環境継承には関与しません。

## 根拠

- `cmake/hip_backend.cmake:94-98` は CMake 変数をソースツリー内の固定ディレクトリに設定し、HIP runtime target に渡します。
- `cmake/hip_backend.cmake:109-118` は同変数から `cuda_runtime.h` のパスを作り、C++ の強制 include オプションを設定します。
- `CMakeLists.txt:224-228` は HIP backend の GPU include directories に同変数を設定します。
- `CMakeLists.txt:1932-1935` は HIP 用 prefill source の include directory として同変数を使います。
- 対象 commit の Strata ソースを名前で検索した結果、`$ENV{STRATA_HIP_COMPAT_INCLUDE_DIR}`、`getenv("STRATA_HIP_COMPAT_INCLUDE_DIR")`、Python の `os.environ` から読む箇所は見つかりませんでした。
