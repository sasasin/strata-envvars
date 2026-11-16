# `GG`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`GG` は実行時エンジンの設定ではなく、Linux の分割エンジン用ビルドスクリプトが参照するビルド時の上書きです。`packaging/build_split_cuda.sh` と `packaging/build_split_hip.sh` は、空でない値を CMake の `-DSTRATA_GGML_DIR=<値>` にして渡します。これにより Strata の CMake 設定は同梱 `third_party/strata-ggml` の代わりに指定 checkout の `ggml` を選びます（`packaging/build_split_cuda.sh:13-25`、`packaging/build_split_hip.sh:18-34`、`cmake/strata_ggml.cmake:6-14,56`）。

調査対象の Strata 所有コードでは、`GG` を読む箇所はこの 2 つのビルドスクリプトです。実行時エンジンが `GG` を読む箇所は見つかりませんでした。対象はこれらのスクリプトを通す CUDA/HIP 分割エンジンのビルドに限られます。

## 値と判定

両スクリプトとも `GG=${GG:-}` により未設定と空文字を空値にし、`[ -z "$GG" ]` で空かどうかだけを判定します。空なら CMake 引数を追加せず、CMake は同梱ツリーを選択します。非空なら内容を `STRATA_GGML_DIR` に渡します。`GG` 自体の数値・真偽値・checkout の妥当性検査、空白除去、大文字小文字変換はありません（`packaging/build_split_cuda.sh:16-17`、`packaging/build_split_hip.sh:22-23`）。

| ビルド経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux CUDA 分割エンジン | 空扱い。`STRATA_GGML_DIR` を渡さず同梱ツリーを選ぶ | 空でない任意の文字列。例: `/src/llama.cpp`、`0` | 空文字。`0` も空でないため有効扱い |
| Linux HIP 分割エンジン | 空扱い。`STRATA_GGML_DIR` を渡さず同梱ツリーを選ぶ | 空でない任意の文字列。例: `/src/llama.cpp`、`0` | 空文字。`0` も空でないため有効扱い |

非空値は引用符なしの `$ggml` 展開で CMake のコマンドに加えられるため、空白を含むパスは複数の引数に分割され得ます。パスを受け付けるための別の quoting や検査はスクリプトにありません（同上）。

## 有効になる条件

- `packaging/build_split_cuda.sh` または `packaging/build_split_hip.sh` を実行すること。通常のエンジン起動時には参照されません（各スクリプト `:6,12-25`、`:10,17-34`）。
- 非空の `GG` を指定した場合、値は CMake の `STRATA_GGML_DIR` に渡され、CMake 側ではその checkout の `ggml` サブディレクトリが選択されます。空なら同梱の `third_party/strata-ggml` に戻ります（`cmake/strata_ggml.cmake:6-14,56`）。
- 両スクリプトは `STRATA_NATIVE_EXPERTS=ON` を指定して CMake を呼ぶため、CMake の GGML 設定・追加は有効です（`packaging/build_split_cuda.sh:23-25`、`packaging/build_split_hip.sh:31-34`、`CMakeLists.txt:601-606`）。
- CUDA 経路では外部 checkout を指定した場合、MMQ scheduler の一部機能は確認済み scheduler に限定されます。これは `GG` の値判定ではなく、渡された `STRATA_GGML_DIR` に対する CMake の条件です（`cmake/backends/cuda.cmake:171-192`）。

## 実行時の詳細

シェルスクリプト開始時に環境から `GG` をシェル変数へ取り込み、その値を CMake configure の引数に反映します。スクリプト内で後から環境を再読する処理や、実行時に値を読む処理はありません（`packaging/build_split_cuda.sh:12-25`、`packaging/build_split_hip.sh:17-34`）。両スクリプトは configure 前に指定 build directory の `CMakeCache.txt` を削除するため、以前の CMake cache の `STRATA_GGML_DIR` は引き継ぎません（`packaging/build_split_cuda.sh:22-25`、`packaging/build_split_hip.sh:30-34`）。

`GG` と、別名の `STRATA_GGML_DIR` や CLI 引数との優先順位を決める処理はこれらのスクリプトにはありません。CMake に渡されるのは `GG` から生成した引数だけです。非空値の存在だけでは checkout の正当性は保証されず、スクリプト側の事前検査もありません。CMake は選択した root の `ggml` を追加します（`cmake/strata_ggml.cmake:6-14,56`）。

## ログと測定値

`GG` の値に応じた専用ログや測定値はありません。各ビルドスクリプトは最後に生成した実行ファイルのパスを標準出力へ出します（`packaging/build_split_cuda.sh:27-39`、`packaging/build_split_hip.sh:36-60`）。

## 根拠

- 環境変数の読取り、空値判定、CMake への引き渡し: `packaging/build_split_cuda.sh:12-25`、`packaging/build_split_hip.sh:17-34`
- CMake が外部 checkout または同梱ツリーを選ぶ箇所: `cmake/strata_ggml.cmake:6-14,56`
- split ビルドで native experts を有効化する指定: `packaging/build_split_cuda.sh:23-25`、`packaging/build_split_hip.sh:31-34`
- CUDA 外部 checkout での scheduler 条件: `cmake/backends/cuda.cmake:171-192`
