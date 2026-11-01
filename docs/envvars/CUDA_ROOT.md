# `CUDA_ROOT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`CUDA_ROOT` は、Windows 用の `packaging/build_dsv41_windows.bat` が DeepSeek V4.1 エンジン `strata-dsv41.exe` を構成・ビルドするときに使う CUDA Toolkit のルートパスです。バッチはこの値から `nvcc.exe` のパスと CMake の `CUDAToolkit_ROOT` を組み立てます。Strata の通常の実行ファイルやサーバーが実行時に読む箇所はありません。

## 値と判定

| 環境の値 | バッチ内の扱い |
|---|---|
| 未設定 | `C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0` を `CUDA_ROOT` に設定 |
| 空文字 | 未設定と同じ既定パスを設定 |
| 空でない値 | 値をそのままルートとして使用。バッチ内で存在確認、数値変換、正規化はしない |

判定は `if "%CUDA_ROOT%"==""` です。`CUDA_ROOT` を指定する CLI 引数はなく、バッチの位置引数はビルド先と任意のソースディレクトリです。したがって、空でない環境値が既定値より優先されます。値は CMake に `-DCMAKE_CUDA_COMPILER=<値>/bin/nvcc.exe` と `-DCUDAToolkit_ROOT=<値>` として渡されます。

## 有効になる条件

この読み取りは Windows の `packaging/build_dsv41_windows.bat` を実行した場合だけ起きます。対象スクリプトは `STRATA_BUILD_DSV41=ON` と `STRATA_ENABLE_CUDA=ON` を付けて構成し、`strata-dsv41` ターゲットをビルドします。資料でも Windows での DeepSeek V4.1 エンジンのビルド手段としてこのバッチが案内されています（`CMakeLists.txt:906-920`, `docs/DEEPSEEK41.md:167-180`）。

バッチ引数のビルド先が空なら使用法を表示して終了コード 2 で終了します。また、`STRATA_GGML_DIR` が空なら llama.cpp checkout を設定するよう表示して終了コード 2 で終了します。どちらも CMake 起動前のため、この経路では `CUDA_ROOT` の値は使われません。`<source dir>\CMakeLists.txt` がある場合に限って CMake 構成を実行します。

## 実行時の詳細

バッチ開始時の `setlocal` により、既定値の設定はバッチのローカル環境内です。CMake 構成を毎回実行し、CUDA コンパイラと Toolkit ルートを上記の引数へ展開します。CMake が失敗するとバッチは終了コード 1 で終了します。スクリプト独自の `CUDA_ROOT` 警告や値の検証はありません。Toolkit のパスが不正な場合にどう失敗するかは CMake 側の処理であり、Strata の挙動としてはここでは断定しません。

構成が成功した後、バッチは既存の `strata-dsv41.exe` を削除してビルドを開始します。ビルド失敗も終了コード 1 です。正常に生成されない場合や、`--version` 出力に build ID がなく `ALLOW_UNKNOWN_BUILD_ID` が `1` でない場合にも終了コード 1 になります。これらの後続処理は `CUDA_ROOT` を再読込・変更しません。

## 根拠

- `packaging/build_dsv41_windows.bat:5-7` — 対象、既定値についての説明、位置引数。
- `packaging/build_dsv41_windows.bat:8-16` — ローカル環境、ビルド先とソース先の設定、空値への既定パス設定、`STRATA_GGML_DIR` の必須判定。
- `packaging/build_dsv41_windows.bat:18-21` — CMake 構成時のコンパイラパスと Toolkit ルートの指定、構成失敗時の終了。
- `packaging/build_dsv41_windows.bat:23-31` — ビルド、出力確認、build ID 判定と終了経路。
- `CMakeLists.txt:906-920` — `STRATA_BUILD_DSV41` オプションと `strata-dsv41` ターゲット。
- `docs/DEEPSEEK41.md:167-180` — DeepSeek V4.1 エンジンのビルド要件と Windows バッチの案内。
