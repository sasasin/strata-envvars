# `CUDAHOSTCXX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`setup.py` がソースから CUDA エンジン、CUDA 対応の画像エンコーダー、または CUDA 画像生成エンジンを構成するとき、CUDA コンパイルで使う host C++ compiler を CMake の `CMAKE_CUDA_HOST_COMPILER` 定義として渡します。値が空でなく `CXX` も指定されている場合は `CUDAHOSTCXX` が優先されます。Strata の実行時エンジンがこの変数を読む箇所は見つかりませんでした。

## 値と判定

`host_compiler_defs()` は `os.environ.get("CUDAHOSTCXX", "").strip()` で値を取得します。環境変数が未設定なら空文字、明示的な空文字や空白だけの値も `strip()` 後に空文字となり、いずれも `CXX` に fallback します。`CXX` も同じく取得して前後の空白を除きます。

| `CUDAHOSTCXX` | `CXX` | CUDA 定義に渡す値 |
|---|---|---|
| 未設定、空文字、空白だけ | 空でない | `CXX` の値 |
| 未設定、空文字、空白だけ | 未設定または空 | `CMAKE_CUDA_HOST_COMPILER` 定義を出さない |
| 空白を除くと非空 | 任意 | `CUDAHOSTCXX` の値（`CXX` より優先） |

値は `strip()` 以外の parse、数値判定、実行ファイル存在確認、値域検証を Strata 側では行いません。値が不正で CMake の構成または後続のビルドに失敗した場合、setup は失敗したコマンドの終了コードを表示して停止します。受理される値の追加規則や CMake・nvcc 側の解釈は、この Strata コードからは定められません。

## 有効になる条件

- CUDA エンジンのソースビルドでは `build_engine()` が `host_compiler_defs(True)` を呼び、`STRATA_ENABLE_CUDA=ON` とともに定義を CMake に渡します。既成エンジンをそのまま使う場合、このコンパイラ定義は構成されません。`--build` は既成エンジンの代わりにビルドを選ぶ条件ですが、既存のローカルエンジンが現在のソース・アーキテクチャ等に対して有効と判定されると、`build_engine()` はそのまま返り、再構成しません。
- 画像エンコーダーをソースビルドする場合、`host_compiler_defs(vision == "gpu")` が呼ばれます。`vision == "gpu"` のときだけ CUDA host compiler 定義を出し、それ以外（CPU エンコーダー）では `CUDAHOSTCXX` を読み取っても CMake 定義には使いません。
- CUDA 画像生成エンジンのソースビルドでも `build_image_engine("cuda", ...)` が `host_compiler_defs(True)` を呼びます。既存ビルドの stamp が有効なら関数は先に返るため、この変数は再構成時だけ読み取られます。
- HIP エンジンのビルド経路は別の `build_engine_hip()` を通り、`CUDAHOSTCXX` を CMake に渡しません。HIP の GPU 画像エンコーダー経路も独自のビルド関数です。
- `setup.py` に `CUDAHOSTCXX` 専用の CLI オプションはありません。setup の `--build` や `--vision` などはビルド経路の選択に関与しますが、環境変数値の優先順位を変更する CLI 値は確認できません。

## 実行時の詳細

値は setup の Python プロセスで `host_compiler_defs()` が呼ばれた時に読み取られ、その場で `-DCMAKE_CUDA_HOST_COMPILER=<値>` の引数文字列にします。CUDA エンジン、CUDA 画像エンコーダーの GPU 版、および CUDA 画像生成エンジンでは、この helper の結果が `cmake_build()` の構成引数へ加わります。`cmake_build()` は `cmake -S ... -B ...` の configure を実行してから build を実行します。setup は実行前にコマンド行を表示します。configure が非ゼロで終了すると `[X] command failed (exit ...): ...` と `Setup stopped...` を表示して終了コード 1 で停止します。build が非ゼロで終了した場合は一度再試行し、再度失敗すると同じ停止経路になります。

環境変数は Strata 起動ごとにキャッシュされる設定ではありません。setup がビルド構成を実行するときに読みます。ただし、既存のローカルエンジンと画像エンコーダーが再ビルド不要と判定された場合は構成自体が省略され、環境変数を読み直して反映する呼び出しもありません。build フォルダーが以前と異なる CMake generator で構成済みの場合は、その cache を消して再構成しますが、単に `CUDAHOSTCXX` を変更したことだけを再構成条件にするコードは確認できませんでした。

## 根拠

- 実読み取り、空白除去、`CXX` fallback と CMake 定義の生成: `setup.py:5850-5861`。
- CUDA エンジンの構成で定義を渡す箇所: `setup.py:5931-5950`。既成エンジン選択と `--build` によるビルド経路: `setup.py:7779-7798`。
- CUDA 画像エンコーダーでのみ CUDA 定義を渡す箇所: `setup.py:5960-5968`。
- CUDA 画像生成エンジンでの読み取りと configure: `setup.py:5004-5055`。
- configure/build のコマンド表示、実行、失敗時の停止: `setup.py:5800-5824,959-978`。
- HIP エンジンは `CUDAHOSTCXX` 定義を組み立てずに HIP 用定義を渡す: `setup.py:4821-4827`。
- 関連資料は Linux の CUDA ソースビルドで `CXX=g++-14` を使う例と、`CC`・`CXX`・`CUDAHOSTCXX` を setup が CMake に渡す説明を掲載しています（`docs/TROUBLESHOOTING.md:211-218`）。これは setup の helper と整合します。
