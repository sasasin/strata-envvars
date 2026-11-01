# `ROCM_ROOT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`ROCM_ROOT` は `tools/dsv41/build_hip_linux.sh` 専用のビルド補助スクリプトで、HIP SDK のルートディレクトリを指定します。指定したルートから HIP コンパイラと device bitcode の場所を探し、`PATH` に SDK の `bin` を加えて、CMake に HIP compiler root・ROCm path・device library path・prefix を渡します。Strata エンジンの通常実行時設定ではありません。

## 値と判定

| 値 | スクリプトの処理 |
|---|---|
| 未設定 | `/opt/rocm` をルート `R` にする |
| 空文字 | Bash の `${ROCM_ROOT:-/opt/rocm}` により、未設定と同じく `/opt/rocm` を使う |
| 空でない値 | 文字列をそのまま `R` として使う。値の形式やディレクトリ全体の存在を先に検証しない |

`R/llvm/bin/clang++` が実行可能ならそれをコンパイラに選び、そうでなければ `R/lib/llvm/bin/clang++` を選びます。bitcode は `R/amdgcn/bitcode`、`R/lib/llvm/amdgcn/bitcode`、`R/llvm/amdgcn/bitcode` の順にディレクトリを探します。3か所ともなければ最後のパスが CMake に渡ります（`tools/dsv41/build_hip_linux.sh:12,15-17,23-25`）。

## 有効になる条件

この変数を読むのは Linux 用の `tools/dsv41/build_hip_linux.sh` を実行した場合だけです。用途は `strata-dsv41` と DeepSeek V4.1 の parity test target のビルドです。スクリプト冒頭の説明では、Linux Strix Halo 機での実行確認はなく、同じソースの Windows build を確認済みとしています（`tools/dsv41/build_hip_linux.sh:1-8`）。

他の環境変数との関係では、`STRATA_HIP_ARCHS` は対象 architecture（既定 `gfx1151`）、`BUILD_DIR` は build directory（既定 `$SRC/build-dsv41-hip`）、`JOBS` は並列数（既定 `nproc`）、`STRATA_GGML_DIR` は任意の llama.cpp checkout をそれぞれ指定します。これらは `ROCM_ROOT` の既定値を変更しません（同:11-16）。

通常の `setup.py` の HIP engine build 経路は `ROCM_ROOT` を読みません。`rocm_root()` は `ROCM_PATH`、未設定または空の場合は `/opt/rocm` を使い、条件に合う system ROCm がなければ TheRock wheels の経路へ進みます（`setup.py:4690-4733`）。同ファイルが `CMAKE_HIP_COMPILER_ROCM_ROOT` を組み立てる箇所は CMake 引数への値の受け渡しであり、`ROCM_ROOT` 環境変数の読み取りではありません（同:4809-4827）。

## 実行時の詳細

スクリプト起動時にシェル展開で一度読みます。`$R/bin` は `PATH` の先頭に追加されます。`$R` から決めた compiler と bitcode path が CMake に渡されるのは、build directory に `build.ninja` がまだない場合だけです。すでに `build.ninja` が存在すると再 configure は行わないため、その build directory で `ROCM_ROOT` を変更しても、CMake の既存設定は更新されません（`tools/dsv41/build_hip_linux.sh:10-25`）。

`set -e` が設定されているため、CMake configure または build が失敗するとスクリプトはその失敗で終了し、最後の `built in ...` は出ません。成功時には `built in $B` を出力します。スクリプト独自の `ROCM_ROOT` 警告やエラー処理はなく、存在しない SDK root や必要ファイルの不足は後続コマンドの失敗として現れます（同:9,19-28）。

## 根拠

- 環境変数の読み取り、既定値、パス選択、CMake への転送、build 条件と終了経路: `tools/dsv41/build_hip_linux.sh:9-28`。
- 通常の setup.py ROCm 検出が `ROCM_PATH` を参照すること、および別の候補経路: `setup.py:4690-4733`。
- `CMAKE_HIP_COMPILER_ROCM_ROOT` が CMake 引数として構成される例: `setup.py:4809-4827`。

`ROCM_ROOT` の完全一致検索では、上記スクリプトのほかにビルド手順のコメント・文書と benchmark reproduction 文書に名前が現れます。ソース内の `CMAKE_HIP_COMPILER_ROCM_ROOT` は CMake cache variable 名であり、環境変数 `ROCM_ROOT` の別の読み取り箇所ではありません。
