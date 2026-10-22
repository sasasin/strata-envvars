# `STRATA_VISION_HIP_ARCHS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有コード。外部 HIP/ROCm ツールチェーンの内部動作は対象外。

## 役割

Windows の `tools/hip/build_windows.bat` が、HIP 版画像読み取りツール `strata-vision-hip` をビルドするときに、そのツールへ含める AMD GPU アーキテクチャ一覧を指定します。エンジン本体や通常の Strata 実行時の環境変数ではありません。

## 値と判定

| 状況 | 動作 |
|---|---|
| `STRATA_VISION_HIP_ARCHS` が未設定または空 | ビルドスクリプトが `STRATA_HIP_ARCHS` の値を代入します。後者も未設定なら既定値 `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1031;gfx1151` です。 |
| 値を指定 | 文字列をそのまま `-DSTRATA_VISION_HIP_ARCHS=...` として CMake に渡します。値は `gfx1200;gfx1201` のようなセミコロン区切りの gfx 名を想定しています。 |
| 画像読み取りツールをスキップ | `STRATA_NO_VISION=1` のときは読み取りツールの構成・ビルドを行わず、この変数は効果を持ちません。 |

スクリプトは値を数値やアーキテクチャ名として parse せず、文字列として転送します。`STRATA_HIP_ARCHS` と異なる独自の値を指定した場合、同じビルドでインストールする ROCm device wheel の対象とは別になる可能性があります。ビルドスクリプトには両者の整合性検査がありません。

## 有効になる条件

- この環境変数を直接読むのは Windows の `tools/hip/build_windows.bat` です。
- HIP 版画像読み取りツールを作らない構成では使用されません。Windows スクリプトでは `STRATA_NO_VISION=1` がその経路です。
- `packaging/build_hip_linux.sh` は環境変数 `STRATA_VISION_HIP_ARCHS` を読みません。画像読み取りツールにはエンジン用の `ARCHS` を渡します。
- `setup.py` のローカル HIP ビルドもこの環境変数を読みません。エンジンから得た `archs` を CMake に渡します。
- `tools/vision` を CMake から直接構成する場合は、環境変数ではなく CMake cache 変数 `STRATA_VISION_HIP_ARCHS` を指定します。HIP reader を有効にしてこの cache 変数が空なら、CMake は `strata-vision: STRATA_VISION_HIP needs STRATA_VISION_HIP_ARCHS, for example "gfx1200;gfx1201"` で失敗します。

## 実行時の詳細

Windows ビルドスクリプトは、`STRATA_VISION_HIP_ARCHS` が空なら `STRATA_HIP_ARCHS` を設定し、画像読み取りツールの初回 CMake 構成時に値を渡します。既存の `build-vision-hip-win\build.ninja` がある場合はこの CMake 構成を再実行しないため、スクリプトを再実行して環境変数だけ変えても既存ビルド設定は更新されません。CMake は受け取ったリストを HIP の `AMDGPU_TARGETS`、`GPU_TARGETS`、`CMAKE_HIP_ARCHITECTURES` に設定し、コンパイル時にはセミコロンをカンマへ置換した一覧をプログラムに埋め込みます。

ビルドされた `strata-vision-hip --version` は埋め込み一覧を表示します。`--gpu` 起動では GPU を列挙した後、検出した先頭 GPU の gfx 名が埋め込み一覧に完全一致する要素として含まれない場合、標準出力に `ERR this GPU (<gfx>) is not in the picture reader's build (<一覧>)` を出して終了コード 3 を返します。リスト要素の区切りはカンマ、セミコロン、空白で、前方一致ではありません。GPU が見つからない場合も、別の `ERR this picture reader found no GPU (it was built for: <一覧>)` を出して終了コード 3 です。

検出した gfx 名が空の場合、上記の不一致判定は行われません。また別変数 `STRATA_VISION_ARCH_CHECK` が設定され、その値を `atoi` した結果が 0 の場合もアーキテクチャ照合をスキップします（未設定時は照合する）。この実行時変数は、ビルド時のアーキテクチャ一覧そのものを変えません。

## 根拠

- `tools/hip/build_windows.bat:13-23,87-110` — Windows ビルドでの役割、空時の既定、CMake への転送、画像読み取りツールを省く条件。
- `tools/vision/CMakeLists.txt:18-30,84-108` — CMake cache 変数の必須条件、HIP arch 設定への転送、実行ファイルへの一覧埋め込み。
- `tools/vision/strata_vision.cpp:102-112,150-173` — `--version` 表示、GPU 有無・アーキテクチャ検査、終了コードとログ。
- `tools/vision/gpu_arch.h:12-32` — 検出する gfx 名と、区切り文字を使った完全一致判定。
- `packaging/build_hip_linux.sh:30-37,60-72`、`setup.py:4431-4463` — Linux パッケージとローカル HIP ビルドでは、この環境変数ではなく `ARCHS` またはエンジン由来の `archs` を渡すこと。
