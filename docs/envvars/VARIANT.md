# `VARIANT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`VARIANT` は実行中の Strata engine の設定ではなく、Linux CUDA/HIP engine package のビルドスクリプトが package の variant と構成を選ぶために読む環境変数である。CUDA は `cuda12` / `cuda13` の分岐を選び、HIP は `rx9070` などの名前から既定 GPU archs を選ぶ。いずれも最終的に packager の `--variant` 引数へ渡される。サーバー、engine 実行ファイル、モデルの実行時挙動を直接切り替える読み取りは見つからなかった（`tools/packaging/build_cuda_linux.sh:17-25,78-80`、`tools/packaging/build_hip_linux.sh:22-40,134-135`）。

## 値と判定

| 読み取り箇所 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux CUDA package (`tools/packaging/build_cuda_linux.sh`) | `${VARIANT:-cuda13}` により、未設定・空文字のどちらも `cuda13` | 大文字小文字を区別する完全一致 `cuda12` または `cuda13` | `CUDA13`、`cuda12 `、`other` など。case の default が stderr に `build_cuda_linux.sh: VARIANT must be cuda12 or cuda13` を出し、status 2 で終了 |
| Linux HIP package (`tools/packaging/build_hip_linux.sh`) | `${VARIANT:?…}` により未設定・空文字はシェル展開エラーとなり、処理を開始しない | `rx9070`、`rx7900`、`rx6000`、`halo`、`igpu` は既定 archs を選択。それ以外の空でない値も `ARCHS` を指定すれば `V` として受け付ける | 任意名で `ARCHS` も未設定または空文字の場合、`${ARCHS:?ARCHS=gfx...}` で停止。名前自体の一般的な形式検査はない |

CUDA の variant が選択された後も toolkit version を別途検査する。`cuda12` には `nvcc` の version が `12.*`、`cuda13` には `13.*` であることが必要で、一致しなければ `build_cuda_linux.sh: <variant> needs the matching CUDA toolkit; nvcc here is <version-or-missing>` を stderr に出し status 2 で終了する（`tools/packaging/build_cuda_linux.sh:29-33`）。

## 有効になる条件

- CUDA 経路は Linux x86_64 向け `tools/packaging/build_cuda_linux.sh` を実行する場合に限る。同スクリプトは `#!/bin/sh` で、選択した variant に応じて archs、最小 NVIDIA driver、`STRATA_EXPERIMENTAL_SM60` の CMake 値を決める。`ARCHS` があれば archs の既定値だけを上書きし、variant の分岐や driver / SM60 設定は変えない（`tools/packaging/build_cuda_linux.sh:1,19-25`）。
- CUDA package build には対応する `nvcc` toolkit が必要。`BUILD_VISION=0` は vision reader のビルドを省くが、`VARIANT` 判定は省かない（`tools/packaging/build_cuda_linux.sh:29-33,52-60`）。
- HIP 経路は Linux 向け `tools/packaging/build_hip_linux.sh` を実行する場合に限る。既知の 5 variant は `ARCHS` 未指定時にそれぞれの arch を選ぶ。別の variant 名では `ARCHS` を明示する必要がある（`tools/packaging/build_hip_linux.sh:21-40`）。
- HIP のビルド作業には `HP`（ROCm devel root）も必須であり、`VARIANT` が有効でも `HP` がなければ `HP=${HP:?...}` で後続処理に入る前に失敗する（`tools/packaging/build_hip_linux.sh:22-29`）。
- `tools/packaging/build_vision_windows.bat` の `VARIANT` は環境変数読み取りではなく第 1 positional argument (`%~1`) であるため、この環境変数の追加読み取り箇所には数えない（`tools/packaging/build_vision_windows.bat:21-29`）。

## 実行時の詳細

両方ともスクリプト開始時に一度 shell parameter expansion で値を取り込み、以後は CUDA では `variant`、HIP では `V` を使う。プロセス内で後から環境を変更して再評価する cache やリクエスト単位の読み取りはない。

CUDA では `cuda12` が既定 `ARCHS=60;61;70;75;80;86;120;89`、`mindriver=575.51`、`sm60=ON` を選び、`cuda13` は `75;86;89;120`、`580.65`、`OFF` を選ぶ。arch list は実/virtual CUDA architectures に組み立てて CMake と vision reader の build に渡される。最終的に packager に `--variant "$variant"` と build id `release-<version>-<variant>-<CUDA version>` を渡す。variant 既定の build/output directory 名にも使う（`tools/packaging/build_cuda_linux.sh:22-27,35-45,52-60,78-80`）。

HIP では `rx9070`, `rx7900`, `rx6000`, `halo`, `igpu` の既定 arch list がそれぞれ `gfx1200;gfx1201`, `gfx1100;gfx1101;gfx1102`, `gfx1030;gfx1031;gfx1032`, `gfx1151`, `gfx1103;gfx1150`。`ARCHS` の明示値はこれら既定 archs を置き換える。`V` は出力作業ディレクトリの既定名、build status の開始行、BUILD.json の `variant`、package engine の `--variant` と notes に渡される。環境変数そのものを packager に渡すのではなく、スクリプトが値を CLI 引数・生成 metadata に写す（`tools/packaging/build_hip_linux.sh:29-43,57,88-90,134-135`）。

## ログと測定値

CUDA の不正な variant と toolkit version 不一致は、前述の固定文言を stderr に出して status 2 で終了する（`tools/packaging/build_cuda_linux.sh:24,32`）。HIP の未設定・空文字や、任意 variant に対する `ARCHS` 不足は shell の `${parameter:?word}` エラーで停止する。HIP は `build.status` に `start $V ($ARCHS) commit $COMMIT` を記録するが、入力値の一般的な検証警告はない（`tools/packaging/build_hip_linux.sh:22,39,44-45,57`）。

## 根拠

- `tools/packaging/build_cuda_linux.sh:1-33` — CUDA 側の読み取り、既定値、許容値、arch/toolkit 条件。
- `tools/packaging/build_cuda_linux.sh:35-80` — CMake、reader、package への適用。
- `tools/packaging/build_hip_linux.sh:1-40` — HIP 側の必須判定と既定 arch 選択。
- `tools/packaging/build_hip_linux.sh:44-57,88-90,134-135` — ログ、BUILD.json、package への適用。
- `tools/packaging/build_vision_windows.bat:21-29` — 同名 positional argument の区別。
- `tools/packaging/ENGINE-COMPONENT.md:109-113` — CUDA / HIP Linux package の variant 記載との照合。
