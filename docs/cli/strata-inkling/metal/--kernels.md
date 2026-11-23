# `strata-inkling-metal --kernels`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal standalone CLI） |
| オプション | `--kernels` |
| 別名 | なし |
| 値 | 値を1つ取る。Metal shader source を置くディレクトリの文字列。CLI 側で形式・存在確認・正規化はしない |

## 役割

Metal shader source をファイルから読み込む構成の standalone CLI では、必須 shader と任意の Metal 4 MPP shader のファイルパスを組み立てる基準ディレクトリを指定する。shader が実行ファイルに埋め込まれたビルドではこの値は使われず、同梱済みの source がコンパイルされる。

## 使い方

```sh
# shader source を ./metal-src に置いた、非埋め込みビルドの例
strata-inkling-metal --model ./model.strata --kernels ./metal-src
```

## 値と既定値

`--kernels` の直後の argv をそのまま `kernel_dir` に代入する。未指定時は空文字列で、非埋め込み経路では各 shader 名だけをパスとして渡す。指定値が空文字列でも parser は受理し、非埋め込み standalone 経路では同じく shader 名だけを使う。値が末尾 `/` を含むかなどの検査や補正はない。複数回指定した場合は parser が順に代入するため、最後の値が残る。値を省略した場合は `missing value for --kernels` を stderr に出して終了コード 2 で終了する（`engine/src/inkling2/metal/ink_metal_main.cpp:418-419,432-437,447`）。

## 実行時の動作

parser は `--kernels` の値を `kernel_dir` に保存し、モデルのロードと warm 処理の後に `InkMetalRunner::init` へ渡す（`engine/src/inkling2/metal/ink_metal_main.cpp:481-492`）。runner は初期化時に shader library のコンパイルを行う（`engine/src/inkling2/metal/ink_metal_runner.h:230-242`）。

`INK_EMBED_KERNELS` が定義されていない standalone 経路では、値が空なら `ink_metal_codecs.metal` などのファイル名をそのまま、空でなければ `<値>/<ファイル名>` を `compile_try` に渡す。必須ファイルは `ink_metal_codecs.metal`、`ink_metal_ops.metal`、`ink_metal_dspark.metal`、`ink_metal_vision.metal`（`engine/src/inkling2/metal/ink_metal_main.cpp:64-75`）。

一方、同ファイルの `INK_EMBED_KERNELS` 経路では埋め込み source を名前で検索してコンパイルし、`kernel_dir` は参照しない（`engine/src/inkling2/metal/ink_metal_main.cpp:32-63`）。同梱の standalone build script は source を埋め込んでから `-DINK_EMBED_KERNELS` 付きでビルドするため、このスクリプトで作った実行ファイルでは `--kernels` を指定しても場所は切り替わらない（`engine/src/inkling2/metal/build_mac.sh:32-43`）。Metal backend の CMake target も `INK_METAL_EMBEDDED_SHADERS=1` を指定し、embedded 経路では引数を使わず source をコンパイルする（`engine/src/inkling2/metal/CMakeLists.txt:13-30,40-45`、`engine/src/inkling2/metal/ink_metal_backend.mm:22-42`）。この backend target は `strata-inkling` に組み込む library であり、standalone CLI の parser とは別の入口である。

## 適用条件と副作用

このオプションがファイル探索先を変えるのは、Metal standalone CLI が非埋め込み shader 経路でコンパイルされた場合に限る。値のディレクトリを事前検査せず、指定先の各 shader を実際に `compile_try` へ渡す。Metal 4 をサポートする場合は `ink_metal_mpp.metal` も同じ規則で試すが、この MPP shader のコンパイル失敗は警告扱いで、必須 shader の失敗とは異なり初期化失敗にしない（`engine/src/inkling2/metal/ink_metal_main.cpp:64-83`）。埋め込み経路では指定値が無視される。

## 出力とエラー

必須 shader のコンパイルに失敗すると、runner 初期化が失敗し、CLI は stderr に `[ERROR] runner init: ...` を出して終了コード 1 を返す。エラー文字列には失敗した shader のパスと Metal compile error が含まれる（`engine/src/inkling2/metal/ink_metal_main.cpp:65-75,489-493`）。Metal 4 MPP shader のコンパイルだけに失敗した場合は `[ink_metal] Metal 4 MPP optional compile skipped: ...` を stderr に出して続行する（`engine/src/inkling2/metal/ink_metal_main.cpp:77-82`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-467` — standalone CLI の引数 parser、値の取得、重複指定時の代入、引数不足・未知引数の処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:481-493` — モデル処理後の runner 初期化と失敗時の stderr / 終了コード。
- `engine/src/inkling2/metal/ink_metal_main.cpp:32-84` — embedded / file based の shader コンパイル分岐、必須・任意 shader の扱い。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-242` — `kernel_dir` の受け渡しと初期化時のコンパイル呼び出し。
- `engine/src/inkling2/metal/build_mac.sh:32-43` — standalone build での shader source 埋め込みと `INK_EMBED_KERNELS` 定義。
- `engine/src/inkling2/metal/CMakeLists.txt:13-30,40-51`、`engine/src/inkling2/metal/ink_metal_backend.mm:22-60` — CMake backend library の embedded shader 経路。
