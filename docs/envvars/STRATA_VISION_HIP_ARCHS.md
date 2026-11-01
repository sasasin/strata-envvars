# `STRATA_VISION_HIP_ARCHS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Windows の `tools/hip/build_windows.bat` が、HIP 版画像エンコーダー `strata-vision-hip.exe` をビルドする際に参照する環境変数です。指定値は CMake の `STRATA_VISION_HIP_ARCHS` に渡され、HIP コンパイラー向けアーキテクチャ指定と、生成プログラムに埋め込む対応アーキテクチャ一覧になります。Strata の通常の実行時設定ではありません。

候補一覧には載っていますが、Strata の実行プログラムや Python サーバーがこの名前の環境変数を読む箇所は確認できませんでした。ソース全体での同名参照は Windows ビルドバッチ、CMake 設定、ビルドスクリプト、実行ファイル内のコンパイル時定数、`setup.py` の CMake 引数です。後者は Python の `archs` 引数から値を作っており、同名の環境変数は参照しません（`setup.py:4876-4900`）。

## 値と判定

| Windows HIP ビルド時の状態 | バッチ内で使われる値 |
|---|---|
| 未定義または空 | `STRATA_HIP_ARCHS` の値を設定する。既定値は `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1031;gfx1151`（`tools/hip/build_windows.bat:14-17,26`）。 |
| 非空の値 | その値をそのまま `-DSTRATA_VISION_HIP_ARCHS=...` に渡す（同 `:90,101-107`）。 |

アーキテクチャは `gfx` 名をセミコロンで区切る文字列として CMake に渡す想定です（`tools/vision/CMakeLists.txt:7,21`）。バッチ側は内容を個別に parse・正規化しません。CMake は `STRATA_VISION_HIP=ON` かつ `STRATA_VISION_HIP_ARCHS` が空相当なら `FATAL_ERROR` にします（同 `:28-30`）。値の形式・各アーキテクチャのサポート可否は最終的に HIP ビルド設定に渡されますが、Strata のこのバッチには追加の妥当性検査や範囲制限はありません。

## 有効になる条件

- Windows で `tools/hip/build_windows.bat` を実行し、`STRATA_NO_VISION` が `1` でないこと。`STRATA_NO_VISION=1` の場合は画像リーダーのビルド節を飛ばします（`tools/hip/build_windows.bat:87-110`）。
- HIP 版画像リーダーを構成する CMake 実行が必要です。既に `build-vision-hip-win\build.ninja` が存在するとバッチは再構成を省き、既存ビルドツリーをビルドするため、その実行では環境変数を変更しても新しい値が CMake キャッシュに反映されません（同 `:101-109`）。
- Linux の `packaging/build_hip_linux.sh` は `$ARCHS` を `-DSTRATA_VISION_HIP_ARCHS=...` に渡しますが、同名の環境変数を読みません（`packaging/build_hip_linux.sh:83-88`）。また `setup.py` は `archs` リストを `;` で結合して CMake に渡します（`setup.py:4876-4900`）。したがって、これらの経路で同名環境変数を設定しても、このコード上は選択値になりません。

## 実行時の詳細

CMake は HIP モードでこの値を `AMDGPU_TARGETS`、`GPU_TARGETS`、`CMAKE_HIP_ARCHITECTURES` に設定し、セミコロンをカンマに置換した文字列を `STRATA_VISION_HIP_ARCHS` のコンパイル定義として `strata-vision-hip` に埋め込みます（`tools/vision/CMakeLists.txt:84-108`）。実行ファイルの `--version` は埋め込み一覧を表示します（`tools/vision/strata_vision.cpp:102-105`）。

HIP 版を `--gpu` 付きで起動すると、プログラムは backend のデバイス情報から最初に見つけた GPU アーキテクチャ名を集め、ビルド時一覧と照合します。GPU が見つからない場合は stdout に `ERR this picture reader found no GPU (it was built for: ...)` を出して終了コード 3 を返します。検出したアーキテクチャが一覧にない場合も、既定のチェックが有効なら `ERR this GPU (...) is not in the picture reader's build (...)` を出して終了コード 3 を返します（`tools/vision/strata_vision.cpp:46-54,150-172`、一覧照合は `tools/vision/gpu_arch.h:22-32`）。この照合を無効にする別環境変数 `STRATA_VISION_ARCH_CHECK` が設定され、`atoi` の結果が 0 の場合は不一致チェックを行いません。同名の対象変数そのものは実行時に再読込されません。

サーバーは GPU リーダー起動時に `READY` 以外を受け取ると起動失敗として扱い、CPU リーダーが構成されている場合はそちらに切り替え、`[strata] the GPU picture reader did not start (...); pictures are read on the CPU` を出します（`serve/server.py:2829-2842,2844-2870`）。

## 根拠

- `tools/hip/build_windows.bat:13-23,26,87-110` — Windows ビルドでの環境変数の説明、既定値、CMake への転送、ビルドキャッシュ条件。
- `tools/vision/CMakeLists.txt:17-30,84-108` — CMake キャッシュ変数、空値時のエラー、HIP アーキテクチャ設定と compile definition。
- `tools/vision/strata_vision.cpp:46-54,102-105,150-172`、`tools/vision/gpu_arch.h:12-32` — 埋め込み値の表示、GPU 検出後の一覧照合とエラー終了。
- `serve/server.py:2829-2842,2844-2870` — 起動失敗時の CPU リーダーへの切り替え。
- `packaging/build_hip_linux.sh:83-88`、`setup.py:4876-4900` — Linux パッケージと setup 経路での値の供給元。
- `docs/DETAILS.md:946-949` — AMD で GPU リーダーが起動できない場合にサーバーが CPU リーダーを開始するという説明。
