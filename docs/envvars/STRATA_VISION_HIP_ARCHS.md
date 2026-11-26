# `STRATA_VISION_HIP_ARCHS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは Windows の HIP パッケージ作成スクリプトが読む**ビルド時環境変数**で、AMD 向け画像 reader `strata-vision-hip.exe` に含める gfx アーキテクチャ一覧を指定する。`terminal/tools/hip/build_windows.bat` は未設定または空なら `STRATA_HIP_ARCHS` を使い、値を `-DSTRATA_VISION_HIP_ARCHS=...` として Vision reader の CMake 設定へ渡す（`terminal/tools/hip/build_windows.bat:101-119`）。Strata の実行プログラムがこの名前を環境から読むわけではない。CMake は値を HIP の対象アーキテクチャに設定し、セミコロン区切りをコンパイル時のカンマ区切りマクロに変換する（`terminal/tools/vision/CMakeLists.txt:28,36-38,63-68,84-90`）。

reader は `--gpu` 実行時、GPU が利用可能で、かつ `STRATA_VISION_ARCH_CHECK` が `0` でない場合に、検出した gfx 名がこのビルド時リストに含まれるか確認する。一覧にない GPU では reader が画像処理を始めず、サーバーは CPU reader に切り替える（`terminal/tools/vision/strata_vision.cpp:108-124`、`terminal/tools/vision/gpu_arch.h:22-33`、`terminal/serve/server.py:3063-3068,3142-3157`）。

## 値と判定

| 条件 | 未設定・空文字 | 有効になる値（例） | 無効になる値・扱い |
|---|---|---|---|
| Windows の `build_windows.bat` が vision reader をビルドする場合 | `if not defined` により `STRATA_HIP_ARCHS` の値に置換される（`terminal/tools/hip/build_windows.bat:28,103-105`）。 | `gfx1200;gfx1201` のような gfx 名をセミコロンで区切ったリスト。バッチは値を解析せず、そのまま CMake の `-D` 引数に渡す（同 `:111-117`）。 | バッチ側で構文・アーキテクチャ名を検証しない。空白だけなどの非空値も CMake に渡る。HIP の対象値として受理されるかは CMake/HIP の構成・コンパイル結果による。 |
| Vision を直接 CMake configure する場合 | CMake cache 変数の既定値は空文字。`STRATA_VISION_HIP=ON` で空なら configure 時に `FATAL_ERROR`（`terminal/tools/vision/CMakeLists.txt:26-28,36-38`）。 | `-DSTRATA_VISION_HIP_ARCHS="gfx1200;gfx1201"` の形式で指定する（同 `:4-7,63-68`）。 | ソースに独自の文字列 parser や gfx 名の許可リストはない。空値以外を検査して有効性を決める処理は確認できない。HIP compiler が対象を扱えない場合の configure/build 結果は compiler 側に依存する。 |

Windows バッチの `if not defined` は値を数値・真偽値として parse しないため、`0`、`false`、`true` はすべて通常の非空文字列としてそのまま転送され、アーキテクチャ名として特別扱いされない。空文字を明示しても未設定と同じく `STRATA_HIP_ARCHS` に置き換わる。実行時にコンパイル済みリストと比較する helper は `,`、`;`、空白で token を分け、完全一致で照合する（`terminal/tools/vision/gpu_arch.h:22-33`）。

## 有効になる条件

- Windows HIP パッケージ作成の `terminal/tools/hip/build_windows.bat` が Vision reader をビルドすること。`STRATA_NO_VISION=1` の場合は reader の configure/build 節を飛ばすため、この変数は実質使われない（`terminal/tools/hip/build_windows.bat:101-120`）。
- HIP reader の configure で `STRATA_VISION_HIP=ON` になっていること。HIP を有効にしてアーキテクチャ値が空なら CMake は fatal error にする（`terminal/tools/vision/CMakeLists.txt:26-28,36-38`）。
- 環境変数を変更した値がビルドに反映されるのは、バッチが CMake configure を実行するとき。既存の `%SRC%\build-vision-hip-win\build.ninja` があると configure をスキップして既存 build directory を使うため、環境変数を変えてもこの分岐からは新しい値を渡さない（`terminal/tools/hip/build_windows.bat:111-119`）。
- 実行時の照合は HIP reader を `--gpu` で起動した場合だけ。GPU が利用不可ならアーキテクチャ照合より先に `ERR this picture reader found no GPU ...` を出して終了コード 3 となる。GPU は利用可能でも検出 gfx がビルド一覧にない場合、照合を行う既定経路では `ERR this GPU (...) is not in the picture reader's build (...)` を出して終了コード 3（`terminal/tools/vision/strata_vision.cpp:108-124`）。
- `STRATA_VISION_ARCH_CHECK=0` は `std::atoi` で 0 になると照合をスキップする。ただし GPU 利用可能性の確認は先に行う。未設定、空文字、`junk` も照合条件上 `atoi` の結果が 0 になり照合をスキップする。`1` や `1junk` は非ゼロで照合する（同 `:118-124`）。この別変数は `STRATA_VISION_HIP_ARCHS` の値を変更しない。
- サーバーが AMD GPU reader の起動失敗を受けた場合、CPU reader に切り替え、`[strata] the GPU picture reader did not start ({why}); pictures are read on the CPU` の形式でログを出す（`terminal/serve/server.py:3142-3157`）。

## 実行時の詳細

Windows バッチは開始時に `STRATA_HIP_ARCHS` の既定値を設定し、Vision reader 節の冒頭で `STRATA_VISION_HIP_ARCHS` が未定義ならその値を代入する。その後、HIP 用 build directory に `build.ninja` がない場合にだけ CMake configure を実行し、値を cache 変数として渡す。CMake はこれを `CMAKE_HIP_ARCHITECTURES` に設定し、コンパイル定義 `STRATA_VISION_HIP_ARCHS` にはセミコロンをカンマへ置換した文字列を埋め込む（`terminal/tools/hip/build_windows.bat:28,101-119`、`terminal/tools/vision/CMakeLists.txt:63-68,84-90`）。

したがって reader 起動後に環境変数を変更しても、reader の埋め込み一覧は変わらない。reader の `--version` はビルド済み一覧を表示する。`STRATA_VISION_HIP_ARCHS` そのものを実行時に読む箇所はない。起動時に読む `STRATA_VISION_ARCH_CHECK` は別の照合スイッチであり、関数内 cache ではなく当該 reader 起動時の分岐で参照される（`terminal/tools/vision/strata_vision.cpp:75-85,108-124`）。

この変数と実行時引数・設定ファイルとの優先順位はない。Windows ビルドラッパーでは非空のこの変数が `STRATA_HIP_ARCHS` より優先され、未設定・空の場合のみ後者を採用する。なお、Linux の `tools/packaging/build_hip_linux.sh` と `terminal/setup.py` はそれぞれ内部の `ARCHS`・引数 `archs` を CMake に渡しており、この環境変数を読むコードではない（`tools/packaging/build_hip_linux.sh:78-80`、`terminal/setup.py:5750-5774`）。

## ログと測定値

- `strata-vision-hip --version` は `strata-vision hip (GPU architectures: <コンパイル済み一覧>)` を出力する（`terminal/tools/vision/strata_vision.cpp:75-85`）。
- GPU がない場合と、検出 GPU の gfx がビルド一覧にない場合の stdout メッセージおよび終了コード 3 は「有効になる条件」のとおり（同 `:108-124`）。サーバー経由では GPU reader の起動失敗理由をログに出して CPU reader を開始する（`terminal/serve/server.py:3142-3157`）。
- この環境変数についての測定値は、調査対象ソースに条件付きで示されていない。

## 根拠

- `terminal/tools/hip/build_windows.bat:22,28,101-125` — 環境変数の default、Vision build のスキップ条件、CMake への転送、既存 build directory の扱い。
- `terminal/tools/vision/CMakeLists.txt:26-38,63-90` — cache 既定値、HIP build の空値エラー、HIP architectures と compile definition。
- `terminal/tools/vision/strata_vision.cpp:75-85,108-124` — 埋め込み値の version 表示、GPU 実行時の利用可否・gfx 照合。
- `terminal/tools/vision/gpu_arch.h:12-33` — gfx 名抽出と区切り token の完全一致。
- `terminal/serve/server.py:3063-3068,3142-3157` — AMD GPU reader の CPU fallback と起動失敗ログ。
- `tools/packaging/build_hip_linux.sh:78-80`、`terminal/setup.py:5750-5774` — 他のビルド経路が内部値・引数から CMake に渡すこと。
