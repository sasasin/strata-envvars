# `STRATA_HIP_ARCHS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

HIP 用のビルドスクリプトが対象 GPU アーキテクチャ一覧を受け取り、CMake の `CMAKE_HIP_ARCHITECTURES` に渡すための環境変数です。Strata エンジンの実行時設定ではありません。HIP エンジンは configure 時に検証・正規化した一覧を `STRATA_HIP_ARCHS` コンパイル定義として埋め込み、起動時の GPU アーキテクチャ確認に使います。

環境から値を読むのは `tools/hip/build_windows.bat`、`tools/dsv41/win/build_hip_win.bat`、`tools/dsv41/build_hip_linux.sh` です。エンジンの C++/HIP ソースに `getenv` による読み取りはありません。`cmake/hip_backend.cmake` に同名の CMake 変数もありますが、こちらは環境変数を読むコードではなく、検証済みアーキテクチャ名から作られるビルド時の値です。

## 値と判定

値は GPU アーキテクチャ名のリストとして扱われ、数値や真偽値には変換されません。

| 読み取り経路 | 未設定・空文字 | 設定値の使い方 |
|---|---|---|
| Windows `tools/hip/build_windows.bat` | `if not defined` により既定の `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1031;gfx1151` を設定 | セミコロン区切りで ROCm device パッケージ一覧を作り、`CMAKE_HIP_ARCHITECTURES` と zip の `--archs` に渡す |
| Windows `tools/dsv41/win/build_hip_win.bat` | `gfx1151` を設定 | `CMAKE_HIP_ARCHITECTURES` に渡す |
| Linux `tools/dsv41/build_hip_linux.sh` | `${STRATA_HIP_ARCHS:-gfx1151}` により `gfx1151` を使う（未設定または空文字） | `CMAKE_HIP_ARCHITECTURES` に渡す |

値のアーキテクチャ名としての検証は `cmake/hip_backend.cmake` が行います。空要素は飛ばし、空白をセミコロンに置き換えてリスト化し、各要素の `:` 以降を除いてから判定します。検証済み一覧は `gfx1100`, `gfx1201`、コミュニティ報告で検証された一覧は `gfx1101`, `gfx1200` です。`gfx1010`, `gfx1011`, `gfx1012`, `gfx1102`, `gfx1103`, `gfx1030`, `gfx1031`, `gfx1032`, `gfx1034`, `gfx1150`, `gfx1151`, `gfx1152` はビルド可能だが実機検証なしとして警告されます。これら以外は configure を `FATAL_ERROR` で停止します。重複は除去されます。要素が残らない場合も `Strata HIP: CMAKE_HIP_ARCHITECTURES is empty` で configure が失敗します。

## 有効になる条件

- `tools/hip/build_windows.bat` は Windows の HIP エンジンをビルド・パッケージするときに使います。`STRATA_NO_VISION=1` は画像 reader のビルドを止めますが、エンジン側のアーキテクチャ指定には影響しません。`STRATA_VISION_HIP_ARCHS` が未設定なら、この変数の値を HIP 画像 reader のビルドにも渡します。
- `tools/dsv41/build_hip_linux.sh` と `tools/dsv41/win/build_hip_win.bat` は DSV41 の HIP ビルド経路でのみ使います。
- ビルドスクリプトは `build.ninja` が既にあると configure を省略します。その場合、環境変数を変更しても既存ビルドディレクトリの `CMAKE_HIP_ARCHITECTURES` はこの実行では更新されません。Windows の一般 HIP バッチはその一方で、現在の値を ROCm パッケージ選択と最終 zip の `--archs` に使います。
- `cmake/hip_backend.cmake` を使う標準 HIP backend は `STRATA_ENABLE_HIP` が有効な場合に読み込まれます。ビルド時に埋め込まれた一覧は HIP エンジンの GPU 検査に使われます。`STRATA_HIP_GFX906` の互換 backend は別経路で、この環境変数を参照しません。
- スクリプトが渡す `-DCMAKE_HIP_ARCHITECTURES=...` と通常の CMake configure で直接指定する `CMAKE_HIP_ARCHITECTURES` が実際のビルド対象を決めます。標準 HIP backend でそれが未定義または空なら `gfx1100` が既定です。したがって、スクリプトを介さない直接 CMake ビルドでは `STRATA_HIP_ARCHS` 環境変数単独では選択されません。

## 実行時の詳細

標準 HIP backend では CMake が対象一覧を正規化し、セミコロン区切りをカンマ区切りへ変換して `strata_hip_runtime` の compile definition に埋め込みます。HIP の device 検査はコンパイル済み一覧と検出した GPU の `gcnArchName`（コロン以降を除去）を照合します。一覧にない GPU では、対象 GPU がコンパイル対象外であること、HIP 用に再ビルドする方法、または `HIP_VISIBLE_DEVICES` で別 GPU を選ぶ案内を含むエラー文字列を返します。GPU が一台もない場合は `no HIP device is present; this engine was compiled for ...` のエラーになります。

ビルド時には CMake の status/warning/error が観測できます。標準 HIP backend が有効な場合、configure 成功時に `Strata: HIP enabled, arch ...` を表示し、未検証アーキテクチャには warning を出します。不許可のアーキテクチャや空リストは configure を停止します。実行時一覧はバイナリに埋め込まれるため、起動後に環境変数を変更しても変化しません。

## 根拠

- `tools/hip/build_windows.bat:13-26,41-49,69-79,87-115` — Windows の既定値、ROCm device package 選択、CMake への転送、画像 reader への既定転送、zip への転送。
- `tools/dsv41/win/build_hip_win.bat:7-16,32-43` — Windows DSV41 ビルドの既定値と CMake 転送。
- `tools/dsv41/build_hip_linux.sh:5-16,19-27` — Linux DSV41 ビルドの既定値・空文字扱いと CMake 転送。
- `CMakeLists.txt:86-93,148-153,190-206` — 標準 HIP backend と gfx906 互換 backend の区別、および標準 backend の include 条件。
- `cmake/hip_backend.cmake:4-5,13-43,94-105,137` — CMake 側の既定値、アーキテクチャ検証・重複除去、コンパイル定義、configure status。
- `src/core/device.cu:29-64,70-75,256-264`、`sycl/src/core/device.dp.cpp:46-81,87-92,303-312` — コンパイル済み一覧による HIP GPU の照合、返される診断、GPU 不在時の例外。これらは `STRATA_HIP_ARCHS` 環境変数を実行時に読む処理ではありません。
