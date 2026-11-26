# `SHAPE`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点）。

## 役割

エンジンのビルド・パッケージ用シェルスクリプトが読む、コンパイル対象のモデル形状（geometry）名。`shape_setup` が値の有無と綴りを見て、configure 引数 `-DSTRATA_GEOMETRY=<SHAPE>` と `package_engine.py --shape <SHAPE>` を組み立てる（`tools/packaging/shape_build.sh:12-30`）。

未設定・空文字なら両方とも空のままで、configure もパッケージも従来どおり（既定 geometry `flash_next`、component `strata-engine`）。設定すると `engine/include/strata/core/geometries/<SHAPE>.hpp` の形状でカーネルがコンパイルされ、成果物は component `strata-<shape>` のパッケージになる（`tools/packaging/package_engine.py:213-219`）。

エンジン本体、Control、setup.py は `SHAPE` を環境から読まない（`engine/src` と `terminal/**/*.py` に該当する読み取りは無い）。形状の識別子はコンパイル時の `kGeometryName` として焼き込まれ、`strata --geometry` が出力する（`engine/src/program/generate.cpp:3716-3721`）。

## 値と判定

`shape_setup` は `${SHAPE:-}` を展開するため、空文字は未設定と同じ「何もしない」経路に入る。判定はシェルの `case` 2 回（先頭が `[a-z]` か、残りに `[a-z0-9_]` 以外が無いか）と、パッケージ時の `shape_engine.valid()` の 2 段である（`tools/packaging/shape_build.sh:15-22`、`terminal/strata_control/shape_engine.py:33-35,84-86`）。シェル側は長さ・`__`・予約名を見ない。

| 入力 | `shape_build.sh`（シェル） | `package_engine.py --shape` |
|---|---|---|
| 未設定 / `SHAPE=` | 何も追加しない（`return 0`） | `--shape` なし。`strata-engine` |
| `q4_lite` / `flash_next` | 有効（ヘッダあり） | 有効。`strata-q4-lite` / `strata-flash-next` |
| `Q4_LITE` / `q4-lite` / `4lite` | 終了コード 2 | 到達しない |
| `q4` / `q4_lite_` / 24 文字以上 | 有効 | 停止（exit 1、`SHAPE_RE` 不一致） |
| `q4__lite` | 有効 | 停止（exit 1、`__` を含む） |
| `engine` / `vision` | 有効 | 停止（exit 1、component が予約名） |

- シェル側は大文字小文字を区別し、空白・ハイフン・先頭数字を拒否する。長さの上限は無い。
- `SHAPE_RE` は `[a-z][a-z0-9_]{1,21}[a-z0-9]` の全体一致（3〜23 文字、先頭は小文字、末尾は英小文字か数字）で、`__` と予約済み component 名（`strata-engine` 等）も拒否する。
- `STRATA_CMAKE_EXTRA` が `-DSTRATA_GEOMETRY` を含まない場合、`engine/include/strata/core/geometries/<SHAPE>.hpp` の存在を `[ -f ]` で確認し、無ければ終了コード 2（`tools/packaging/shape_build.sh:23-28`）。
- `SHAPE=flash_next` でも `-DSTRATA_GEOMETRY=flash_next` が渡るが、CMake はこれを既定扱いにして include も定義も追加しない（`engine/cmake/strata_geometry.cmake:6-7,27,45-47`）。パッケージだけが別 component になる。

## 有効になる条件

- `shape_build.sh` を source するスクリプト（`tools/packaging/build_cuda_linux.sh:39`、`build_sycl_linux.sh:41`、`build_hip_linux.sh:59`、`build_cuda_linux_aarch64.sh:29`、`engine/spark/build_engine.sh:46`）から起動した場合だけ効く。直接 `cmake` を叩く場合は `-DSTRATA_GEOMETRY` を自分で渡す。
- `STRATA_CMAKE_EXTRA` に `-DSTRATA_GEOMETRY` / `-DSTRATA_GEOMETRY_FILE` が含まれると、ヘッダ検査も `-DSTRATA_GEOMETRY` の追加も行われない（部分一致）。この場合 `SHAPE` は `--shape` と `shape_check` にだけ効く。
- `shape_check` は `<program> --geometry` の 1 行目を完全一致で比較し、不一致・出力なし・実行失敗はすべて exit 1 にする（`tools/packaging/shape_build.sh:32-38`）。
- `--shape` は `shape_engine.valid()` を通る名前しか受け付けないため、シェル検査だけ通る名前はパッケージ段階で止まる（`tools/packaging/package_engine.py:172-174`）。
- HIP では `--shape` が `CUSTOM_SHAPES`（`hy4`, `inkling2`）でない限り hipBLASLt の tuning table 検査が入る（`tools/packaging/package_engine.py:184-188`）。`hy4`/`inkling2` はヘッダを持たず別プログラムなので通常経路では止まる（`terminal/strata_control/shape_engine.py:124-139`）。

## 実行時の詳細

- 読み取りは `shape_setup` / `shape_check` の呼び出し時で cache は無い。スクリプトは `SHAPE` を代入も export もせず、起動時の環境を使う。子プロセスの `cmake` / `python3` は環境の `SHAPE` を読まない。
- `build_cuda_linux_aarch64.sh` は `sh engine/spark/build_engine.sh` を環境ごと起動するため、`SHAPE` はそこで再度読まれる（`:35`）。`shape_setup` の結果は `cmake` と `package_engine.py` の引数に挿入される（CUDA 版 `tools/packaging/build_cuda_linux.sh:44-46,81-83`、他も同様）。
- `shape_check` は CUDA 版が `env LD_LIBRARY_PATH="$stage" "$stage/strata"`、他は stage の `strata` を実行し、HIP 版だけ結果を `build.status` に追記する（`build_cuda_linux.sh:77`、`build_sycl_linux.sh:72`、`build_cuda_linux_aarch64.sh:36`、`build_hip_linux.sh:129`）。
- シンボル保存名も `strata-<shape>` 側になる（`tools/packaging/symbols_build.sh:15-20`）。
- 実行時、エンジンは `--geometry` で `kGeometryName` を出力して 0 で終了する。Control はインストール時にそれを manifest の `shape` と比較して拒否できる（`terminal/strata_control/shape_engine.py:219-265`）。metadata がコンパイル済み geometry と違う GGUF は読み込み時に拒否される（`engine/include/strata/artifact/gguf_reader.hpp:891-933`）。生成 token や選択結果を `SHAPE` が直接変える経路は無い。

## ログと測定値

- シェル（stderr）: `shape_build.sh: SHAPE=$SHAPE is not a geometry name (lower case, digits and _, like q4_lite)`、`shape_build.sh: no header engine/include/strata/core/geometries/$SHAPE.hpp; name the model's header with STRATA_CMAKE_EXTRA=-DSTRATA_GEOMETRY_FILE=<abs path>`、`shape_build.sh: the engine built here says --geometry '${named}', not '$SHAPE' (the header's kGeometryName must be the shape's name)`。
- 成功時（stdout）: `shape_build.sh: the engine is built for $SHAPE (strata --geometry)`。HIP 版はこれを `build.status` に書き、失敗時は `ABORT shape $SHAPE failed (rc=1)` が残る（`tools/packaging/build_hip_linux.sh:47,129`）。
- パッケージ: `--shape {shape!r} is not a model shape name (the compiled geometry's name, like q4_lite: lower case, digits and _)`。
- CMake: `strata: compiled geometry <name> (<header>)`（既定時 `flash_next (default)`）、欠落時 `STRATA_GEOMETRY=<name>: no include/strata/core/geometries/<name>.hpp (have: ...)`（`engine/cmake/strata_geometry.cmake:29-31,44-46`）。
- `docs/` に `SHAPE=` の手順や測定値は無く、この変数について引用できる性能値は無い。

## 根拠

- `tools/packaging/shape_build.sh:12-38`（判定・`shape_cmake`/`shape_pkg`・`shape_check`）
- `tools/packaging/build_cuda_linux.sh:39,44-46,75,77,81-83`、`build_sycl_linux.sh:41,50-51,71-72,76-77`、`build_hip_linux.sh:59,64-66,128-129,136-137`、`build_cuda_linux_aarch64.sh:29,32,35-38,43-45`、`engine/spark/build_engine.sh:46,52-55`
- `tools/packaging/package_engine.py:166-174,184-189,213-219,321-323`
- `terminal/strata_control/shape_engine.py:33-35,84-93,124-139,219-265`
- `engine/cmake/strata_geometry.cmake:11-47`、`engine/include/strata/core/geometry.hpp:72-82`、`engine/include/strata/core/geometries/flash_next.hpp:8`
- `engine/src/program/generate.cpp:3716-3721`、`engine/include/strata/artifact/gguf_reader.hpp:891-933`
- `tools/packaging/symbols_build.sh:15-20`
