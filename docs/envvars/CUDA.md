# `CUDA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`CUDA` は通常の Strata 実行時設定ではなく、CUDA split engine をビルドする `tools/packaging/build_split_cuda.sh` が参照するツールキットのルートディレクトリである。スクリプトはその値を `PATH` の先頭に加え、CMake に CUDA compiler (`$CUDA/bin/nvcc`) と `CUDAToolkit_ROOT` を渡す。生成後の Strata エンジンがこの名前を読む箇所は見つからず、GPU 選択やモデル実行を制御する環境変数ではない（`tools/packaging/build_split_cuda.sh:6,12-25`）。

## 値と判定

スクリプトは Bash の `${CUDA:?CUDA=<toolkit root>}` で値を必須化する。`:` があるため未設定と空文字のどちらもエラーになり、非空なら内容を文字列として受け取り、数値・真偽値・ディレクトリの存在確認や正規化はスクリプト内では行わない（`tools/packaging/build_split_cuda.sh:12-16`）。

| 条件 | unset | 設定時に処理を続ける値 | この判定で拒否される値 |
|---|---|---|---|
| `build_split_cuda.sh` 実行時 | エラー終了 | 空でない任意の文字列。例: `/usr/local/cuda-13.1`、`1`、`true` | 空文字。unset と同様にエラー終了 |

`0`、`false`、空白だけの値も空文字ではないため、この必須判定は通る。ただしパスとして有効かどうかは検査されず、後続の `PATH`・CMake 引数へそのまま展開される。値の前後の空白を取り除く処理もない。toolkit root として適切でない値の具体的な失敗箇所は、そこで実行される `cmake` / `ninja` などの結果に依存する（`tools/packaging/build_split_cuda.sh:15,21-25`）。

## 有効になる条件

- `tools/packaging/build_split_cuda.sh` を Bash で実行する場合に限り参照される。スクリプトは NVIDIA 向け Linux split engine のビルド用と説明され、`STRATA_ENABLE_CUDA=ON` および `STRATA_BUILD_SPLIT=ON` で CMake を構成する（`tools/packaging/build_split_cuda.sh:1-6,23-25`）。
- `B` も必須である。`CUDA` が非空でも `B` が unset または空なら、先行する `${B:?...}` の時点で `CUDA` の検査より前に終了する（`tools/packaging/build_split_cuda.sh:12-15`）。
- ランタイムの `strata` / server / model CLI が `CUDA` を読む条件分岐は見つからない。`CUDA` と似た別名の `CUDA_LAUNCH_BLOCKING` や `CUDA_MODULE_LOADING` の処理はこの変数の読み取りではない。

## 実行時の詳細

この変数の効果はビルドスクリプト内に限られる。スクリプト開始時に必須値を確認した後、`$CUDA/bin` を `PATH` の先頭に置き、CMake の `CMAKE_CUDA_COMPILER` と `CUDAToolkit_ROOT` に値を組み立てて渡す。値の変更はスクリプト起動時に渡した値に対して後続コマンドの展開に反映されるが、スクリプトは `CUDA` の再読み込みやキャッシュを行わない（`tools/packaging/build_split_cuda.sh:15,21-25`）。

ここで作られる split engine 自体の実行時に `CUDA` を参照する処理は確認できない。CLI 引数や別の実行時環境変数との優先順位は該当しない。

## ログと測定値

`CUDA` が unset または空の場合、Bash の必須パラメータ展開がエラーを stderr に出してスクリプトを終了する。展開メッセージは `CUDA=<toolkit root>` である（`tools/packaging/build_split_cuda.sh:12,15`）。非空値に対する成功ログや警告はこのスクリプトにはなく、後続コマンドの出力に委ねられる。測定値は該当しない。

## 根拠

- `tools/packaging/build_split_cuda.sh:1-6,12-25` — スクリプトの用途、必須値判定、`PATH` への追加、CMake への引き渡し。
