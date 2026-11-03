# `CUDA`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

`CUDA` は、Strata の Linux 用 DeepSeek-V4.1 エンジンおよび split エンジンのビルドスクリプトが CUDA Toolkit のルートディレクトリを受け取るための値です。エンジンの通常実行時に読む設定ではありません。実行時の `strata` や `strata-dsv41` の挙動を制御する環境変数としての読み取りは確認できません。

対象は `packaging/build_dsv41_cuda.sh` と `packaging/build_split_cuda.sh` です。両スクリプトの使用例は `CUDA=/path/to/toolkit` の形で示されています（`packaging/build_dsv41_cuda.sh:6`, `packaging/build_split_cuda.sh:6`）。

## 値と判定

| 状態 | 判定・処理 |
|---|---|
| 未設定 | `${CUDA:?...}` の展開に失敗し、Bash は必須値がない旨を stderr に出してスクリプトを終了する。既定値はない。 |
| 空文字 | 同じく必須値チェックに失敗し、Bash は stderr に診断を出して終了する。 |
| 非空文字列 | 文字列の形式・ディレクトリの存在・`nvcc` の存在はスクリプト内で事前検証せず、その値を toolkit root として使う。 |

数値変換や値域判定はありません。空白やパス表記を正規化する処理もありません。`CUDA` を別の CLI 引数で上書きする仕組みはこれらのスクリプトにはありません。必須チェックは `set -eu` の後にあり、失敗時は `cmake` の実行前に処理が止まります（`packaging/build_dsv41_cuda.sh:13-17`, `packaging/build_split_cuda.sh:12-16`）。

## 有効になる条件

- これらの Linux 向けビルドスクリプトを実行するときだけ参照されます。CUDA Toolkit の場所を `CUDA` に渡す必要があります。
- スクリプトは `PATH` の先頭に `$CUDA/bin` を加え、CMake に `-DCMAKE_CUDA_COMPILER="$CUDA/bin/nvcc"` と `-DCUDAToolkit_ROOT="$CUDA"` を明示します。したがって、`CUDA` の値はコンパイラと Toolkit root の指定に使われます（`packaging/build_dsv41_cuda.sh:20,28-30`, `packaging/build_split_cuda.sh:20,22-24`）。
- 他の Strata 実行ファイルが `CUDA` を読む箇所は確認できません。CUDA backend の選択は別のビルド設定（例: `STRATA_ENABLE_CUDA`）で行われ、この環境変数自体は実行時の backend 選択や GPU 動作を切り替えません。

## 実行時の詳細

値は各ビルドスクリプトのシェル実行中に展開されます。スクリプトは `CUDA` を CMake の環境変数として設定し直すのではなく、`PATH` の変更と CMake のコマンドライン引数に展開して渡します。CMake による configure の後、各スクリプトは Ninja で対象エンジンをビルドします（`packaging/build_dsv41_cuda.sh:20,28-32`, `packaging/build_split_cuda.sh:20-29`）。

`CUDA` が未設定または空の場合は必須値展開で停止します。値が非空でも Toolkit のパスが誤っていれば、後続の CMake configure で指定したコンパイラや Toolkit を利用できず失敗し得ます。後者の具体的なエラー文言や終了状態は CMake 側の結果に依存し、これらのスクリプトでは独自の検査・警告を行いません。

## 根拠

- `packaging/build_dsv41_cuda.sh:6,13-20,28-32`: 使用例、必須値チェック、PATH への追加、CMake の compiler / Toolkit 指定、ビルド実行。
- `packaging/build_split_cuda.sh:6,12-24,27-29`: 使用例、必須値チェック、PATH への追加、CMake の compiler / Toolkit 指定、ビルド実行。
- `docs/DEEPSEEK41.md:221-238`: Linux で `packaging/build_dsv41_cuda.sh` を使う案内。`CUDA` の値判定や実行時の意味は記載されていないため、値の挙動は上記スクリプトを根拠とした。
