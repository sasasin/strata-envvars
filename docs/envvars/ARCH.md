# `ARCH`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`ARCH` は `packaging/build_split_cuda.sh` が strata-split CUDA 実行ファイルのビルド対象 compute capability を指定するために読む環境変数です。通常の Strata 推論実行時には読み取られず、ビルド後の動作を実行時に切り替える変数でもありません。スクリプトは値を `STRATA_SPLIT_ARCH` と `CMAKE_CUDA_ARCHITECTURES` の両方として CMake に渡します（`packaging/build_split_cuda.sh:13-24`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `packaging/build_split_cuda.sh` による Linux CUDA split build | `ARCH` が未設定または空文字なら `86` | 1 個の compute capability を表す値。スクリプトは `86` などの値をそのまま 2 つの CMake 引数へ渡す | スクリプト内に形式・範囲の検証や fallback はない。空文字は unset と同じく `86`。それ以外の不正値はそのまま CMake/NVCC に渡り、後段の構成またはビルドで扱われる |

シェルの `${ARCH:-86}` を使うため、空白除去、数値変換、大文字小文字変換はありません。`0`、`true`、`false`、`0anything` もブール値として判定されず、そのまま渡されます。Strata のこのスクリプトには `ARCH` の受理範囲を検証する処理がありません（`packaging/build_split_cuda.sh:18,23-24`）。

## 有効になる条件

- `packaging/build_split_cuda.sh` を実行して strata-split の CUDA build を行う経路に限られます。スクリプトは `STRATA_BUILD_SPLIT=ON` と `STRATA_ENABLE_CUDA=ON` を指定して CMake を実行します（`packaging/build_split_cuda.sh:23-25`）。
- split target が構成されるのは Linux CUDA または HIP build の場合です。通常の CUDA 実行ファイルや HIP split build が `ARCH` を参照するわけではなく、ここでの `ARCH` は CUDA 用ビルドスクリプト専用です（`src/split/CMakeLists.txt:20-26`）。
- 既定値 `86` を含む選択値は、その compute capability と一致する NVIDIA GPU で split engine を使う前提です。ビルドされた CUDA kernel は単一のアーキテクチャを対象にし、split engine はロード時にカードの capability が一致するか検査します（`src/split/CMakeLists.txt:129-137`、`src/split/src/card_check.hpp:13-23`）。

## 実行時の詳細

値は build script 実行時にシェル展開され、CMake の `STRATA_SPLIT_ARCH` と `CMAKE_CUDA_ARCHITECTURES` に同じ文字列として渡されます。CMake は `STRATA_SPLIT_ARCH` を `FNX_ARCH` compile definition と CUDA target の `CUDA_ARCHITECTURES` に設定します。したがって値は kernel のビルド対象と compile-time 分岐に反映され、実行中に環境変数を変更しても既に作成した実行ファイルには反映されません（`packaging/build_split_cuda.sh:18,23-24`、`src/split/CMakeLists.txt:129-137`）。

split engine のモデルロード時、カード情報を取得した後、モデルデータを配置する前に各カードの compute capability を `FNX_ARCH` と比較します。一致しないカードでは `std::runtime_error` を投げ、文面に実カードの capability と `this build is for sm_<値>`、再ビルド用の `rebuild with make ARCH=<実カード値>` を含めます（`src/split/src/model.cpp:102-107,120-122,1238-1249`、`src/split/src/card_check.hpp:17-23`）。値がどのような token 生成や通常 engine の選択に影響するかを示す `ARCH` 読み取りは見つかりませんでした。

## ログと測定値

`ARCH` の値に対する専用ログや測定値はありません。スクリプトはビルド失敗を `set -e` で終了させますが、`ARCH` 用の独自エラー文言は出しません（`packaging/build_split_cuda.sh:12,23-35`）。実行時にカードの compute capability がビルド値と異なる場合は、上記の例外メッセージで不一致を報告します（`src/split/src/card_check.hpp:17-23`）。

## 根拠

- `packaging/build_split_cuda.sh:6-24` — 用途、既定値、値の転送先。
- `packaging/build_split_cuda.sh:28-39` — build の後続処理と終了・失敗経路。
- `src/split/CMakeLists.txt:20-26,60-65,129-137` — split build の条件、`STRATA_SPLIT_ARCH` の決定、compile definition と CUDA target への適用。
- `src/split/src/model.cpp:102-107,120-122,1238-1249`、`src/split/src/card_check.hpp:13-23` — モデルロード時のカード検査と capability 不一致の例外。
