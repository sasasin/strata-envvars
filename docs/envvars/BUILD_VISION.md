# `BUILD_VISION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

ビルド用の切り替え値です。Linux CUDA のエンジン build script、DGX Spark 向け script、および Dockerfile が画像 reader `strata-vision` の構成・ビルドを選びます。無効にすると通常の `strata` はそのままビルドされますが、画像 reader が成果物に含まれないテキスト専用構成になります。

Strata の実行時エンジンが `BUILD_VISION` を読み、モデルやリクエストの画像機能を切り替える実装は見つかりませんでした。この値はソース中で CMake の build directory を決める `BUILD_VISION_DIR` とも別です。

## 値と判定

| 経路 | 未設定 | 明示的な空文字 | reader をビルドする条件 | その他の値 |
|---|---|---|---|---|
| `packaging/build_cuda_linux.sh`、`spark/build_engine.sh` | `${BUILD_VISION:-1}` により `1` として有効 | `:-` のデフォルトが適用され `1` として有効 | 値が文字列 `1` と完全一致 | `0`、`true`、`01` などは無効 |
| `packaging/build_cuda_linux_aarch64.sh` 経由 | wrapper が `BUILD_VISION=${BUILD_VISION:-1}` として Spark script に渡すため有効 | wrapper で `1` に置き換わり有効 | wrapper から渡る値が `1` | `1` 以外は無効 |
| Dockerfile の `ARG BUILD_VISION=1` | build arg を省略すると `1` | `--build-arg BUILD_VISION=` の空文字は無効 | Docker build stage 内で値が文字列 `1` と完全一致 | `1` 以外は無効 |

数値 parse、真偽文字列 parse、大文字小文字変換、範囲検査はありません。各ビルドスクリプトでは `set -eu` が設定されていますが、未設定・空値の差は上記の `${...:-1}` 展開によって処理されます。Dockerfile は `ARG` の既定値を持ちますが、シェル条件は `${BUILD_VISION:-1}` ではなく `[ "$BUILD_VISION" = "1" ]` です。

## 有効になる条件

- `packaging/build_cuda_linux.sh` は Linux x86_64 CUDA package build の経路です。値が有効なら `tools/vision` を CUDA、portable mode、エンジンと同じ CUDA architectures で configure し、`strata-vision` target をビルドします。無効時もエンジン本体と package 作成は続きます（`packaging/build_cuda_linux.sh:14-20,34-46,63-66`）。
- `spark/build_engine.sh` は Linux arm64（DGX Spark）専用で、CUDA 13 toolkit を要求します。reader の CMake configure/build は値が有効な場合だけ行われます（`spark/build_engine.sh:27-43,70-75`）。`packaging/build_cuda_linux_aarch64.sh` は `BUILD_VISION` を既定値付きで Spark script に渡します（`packaging/build_cuda_linux_aarch64.sh:21-33`）。
- Docker の source build は Dockerfile の `engine-build` stage にある build arg で判定します。`strata-vision` の build を飛ばしても `strata` / `strata_kq` の build は独立して実行されます（`Dockerfile:31-50`）。Docker build arg はこの build stage 内の値であり、最終 runtime image の実行時環境変数として設定されません（`Dockerfile:69-100`）。
- `BUILD_VISION_DIR` は Linux x86_64 と Spark script で vision CMake build directory を上書きします。`BUILD_VISION` の有効・無効判定には使われません（`packaging/build_cuda_linux.sh:41-45`, `spark/build_engine.sh:21,70-74`）。

## 実行時の詳細

有効時、Linux x86_64 package script は `$BUILD_VISION_DIR`（未設定または空なら `$repo/build-vision-$variant`）で reader をビルドし、そのディレクトリに `bin/strata-vision` があれば staging にコピーします。reader があれば `BUILD.json` に `vision_archs` も記録し、CUDA package 作成時に reader の architecture coverage が検査されます（`packaging/build_cuda_linux.sh:41-46,48-58`; `packaging/package_engine.py:80-119,191-193`）。無効時は新たな reader build をせず、存在する reader がなければ packaging は「picture reader なし」の CUDA package を許容し、text-only の note を出します（`packaging/package_engine.py:100-104`）。ただし Linux x86_64 script は build を省略した後の staging copy をファイル存在で判定するため、以前の `BUILD_VISION_DIR` に `bin/strata-vision` が残っていれば、値を無効にしていてもそれをコピーし `vision_archs` を付けます（`packaging/build_cuda_linux.sh:41-57`）。

Spark script は reader の copy 条件にも `BUILD_VISION=1` を要求するため、無効値なら既存 build directory に reader が残っていても今回の出力フォルダーにはコピーされません。Dockerfile も reader build を飛ばし、stage にファイルがある場合だけ `/stage` にコピーします。fresh な Docker build では build arg の値に応じた reader の有無が package 内容に反映されます（`spark/build_engine.sh:21,70-88`; `Dockerfile:46-66`）。`packaging/package_engine.py` は CUDA package で reader がない構成を許容し、text-only である旨を note にします（`packaging/package_engine.py:100-104`）。

この値は各 script の実行中にシェル展開され、実行中の再読込や cache はありません。Docker は build arg を build stage のコマンドに渡します。`BUILD_VISION` に固有の警告・終了コード分岐はなく、reader 有効時の CMake configure/build が失敗すれば各 script の `set -e`（Docker の `RUN set -e`）により build が失敗します。無効値そのものによる警告は実装されていません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:56`（`BUILD_VISION` と `BUILD_VISION_DIR` を列挙）。
- Linux x86_64 CUDA: `packaging/build_cuda_linux.sh:39-46,48-58,63-66`。
- DGX Spark / arm64 wrapper: `spark/build_engine.sh:21,27-43,70-91`; `packaging/build_cuda_linux_aarch64.sh:21-33,36-51`。
- Docker source build: `Dockerfile:31-66,69-100`; 使用例 `docs/DOCKER.md:303-309`。
- package 内の reader 選択と CUDA reader なしの扱い: `packaging/package_engine.py:16-20,80-119,149-165,191-193`。
- 関連記述: `docs/DGX_SPARK_LINUX.md:63-66`, `packaging/ENGINE-COMPONENT.md:103-110`。これらも `BUILD_VISION=0` で reader を省けると説明しています。
