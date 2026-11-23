# `ARCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`ARCH` は、同梱の `tools/packaging/build_split_cuda.sh` で CUDA 版 `strata-split-N` をビルドするときに、対象とする NVIDIA compute capability を指定するシェル環境変数です。通常の Strata 実行時設定ではなく、生成される split engine の CUDA コード世代と、起動時に受け入れる GPU 世代をビルド時に決めます。スクリプトは値を CMake の `STRATA_SPLIT_ARCH` と `CMAKE_CUDA_ARCHITECTURES` に渡し、CMake は `FNX_ARCH` と CUDA の実ターゲットへ反映します（`tools/packaging/build_split_cuda.sh:18-24`、`engine/src/split/CMakeLists.txt:138-143`）。

## 値と判定

スクリプトは Bash の `${ARCH:-86}` を使います。このため未設定と空文字はどちらも `86` になります。それ以外の値は文字列としてそのまま二つの CMake 引数へ渡され、スクリプト内では数値変換、形式検査、範囲制限をしません（`tools/packaging/build_split_cuda.sh:18-24`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `build_split_cuda.sh` 経由の CUDA split engine build | `86` | 例: `86`。コメント上は単一の compute capability を指定し、`86`（2 枚の RTX A6000）で実行した記録があります。 | スクリプト独自の無効値判定はありません。空文字は unset と同じく `86`。`0`、`1`、`true`、`86abc`、空白を含む値も非空なら加工されず渡されますが、それらが有効な CMake/NVCC 設定とは限らず、ビルド成功は保証されません。 |

スクリプトは `ARCH` を CLI 引数から読みません。呼び出し元の環境に設定するか、`ARCH=86 tools/packaging/build_split_cuda.sh` のようにコマンド前置代入で渡します。他の環境変数や CLI 引数による `ARCH` の優先順位、無効値時の fallback はありません。スクリプト外から直接 CMake を呼ぶ場合の `-DSTRATA_SPLIT_ARCH` は別の入力です（`tools/packaging/build_split_cuda.sh:6,18-24`、`engine/src/split/CMakeLists.txt:16-17`）。

## 有効になる条件

- この読み取り箇所は CUDA 用の `tools/packaging/build_split_cuda.sh` だけです。同スクリプトは CUDA toolkit と `-DSTRATA_BUILD_SPLIT=ON` を指定して CMake を実行します（`tools/packaging/build_split_cuda.sh:15,21-25`）。
- CMake の split engine は明示的に `STRATA_BUILD_SPLIT=ON` とした場合だけ追加されます。CUDA 経路では CUDA backend が有効で、Windows と macOS ではないことが必要です（`engine/CMakeLists.txt:841-843`、`engine/src/split/CMakeLists.txt:20-26`）。
- HIP 用 `build_split_hip.sh` の設定ではありません。HIP の CMake 分岐は `STRATA_SPLIT_ARCH` を `1201` に設定し、CUDA の `ARCH` 値は利用しません（`engine/src/split/CMakeLists.txt:20-22,68-73`）。
- この値が実行時に効くのは、このスクリプトでビルドした split engine です。通常の `strata` エンジンやサーバーの実行時に `ARCH` を設定しても、Strata のコードがこの名前を読む箇所は見つかりません。

## 実行時の詳細

スクリプト開始時に `ARCH` を一度展開し、その値で `CMakeCache.txt` を削除して構成をやり直します。値は `-DSTRATA_SPLIT_ARCH="$ARCH"` と `-DCMAKE_CUDA_ARCHITECTURES=$ARCH` に渡されます。CUDA split target は `STRATA_SPLIT_ARCH` を `FNX_ARCH` compile definition と `${STRATA_SPLIT_ARCH}-real` に使います。カーネルには `FNX_ARCH >= 80` などのコンパイル時分岐があり、モデル読み込み時には各 GPU の compute capability がビルド値と一致するか確認します（`tools/packaging/build_split_cuda.sh:18,22-25`、`engine/src/split/CMakeLists.txt:138-143`、`engine/src/split/src/kernels.cu:1429-1447`、`engine/src/split/src/model.cpp:112-131`）。

このためビルド後にシェルの `ARCH` を変えても、その既存バイナリのコンパイル設定や GPU 判定は変わりません。CUDA build のカード判定で不一致なら、モデル読み込み前の `require_card_arch` が例外を送出します。例外は `sfnx` が stdout に `ERR ...`、stderr に `sfnx: failed: ...` を出し、終了コード 1 で終了します（`engine/src/split/src/card_check.hpp:17-22`、`engine/src/split/src/model.cpp:112-131`、`engine/src/split/tools/sfnx.cpp:1094-1102`）。

## ログと測定値

`ARCH` 自体についてスクリプトが出す専用ログや警告はありません。CMake/NVCC が不正な設定をどう診断するかは、ここで確認した Strata のコードでは定めていません。GPU 世代がビルド値と異なるときは、エラー本文に実際の compute capability と `this build is for sm_<値>` が含まれ、上記の `ERR` / `sfnx: failed:` 経路で観測できます（`engine/src/split/src/card_check.hpp:17-22`、`engine/src/split/tools/sfnx.cpp:1097-1102`）。

スクリプトのコメントは `ARCH=86` を「2 RTX A6000」で実行した値として記していますが、性能測定値はありません（`tools/packaging/build_split_cuda.sh:8-9`）。

## 根拠

- `tools/packaging/build_split_cuda.sh:6-24` — 対象スクリプト、Bash の既定値、CMake への転送。
- `engine/CMakeLists.txt:841-843`、`engine/src/split/CMakeLists.txt:20-26,68-73,138-143` — split build 条件、CUDA/HIP 分岐、compile definition と CUDA target architecture。
- `engine/src/split/src/kernels.cu:1429-1447` — `FNX_ARCH` による CUDA kernel compile-time 分岐。
- `engine/src/split/src/model.cpp:112-131`、`engine/src/split/src/card_check.hpp:17-22`、`engine/src/split/tools/sfnx.cpp:1094-1102` — 起動時の GPU 世代照合と失敗の出力・終了。
