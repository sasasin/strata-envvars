# `ARCH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリや GPU driver の環境変数は対象外。

## 役割

`ARCH` は、Strata の通常実行時設定ではなく、Linux 向け CUDA ビルド用シェルスクリプトが CMake に渡す GPU アーキテクチャ指定です。`packaging/build_dsv41_cuda.sh` では DeepSeek-V4.1 エンジンの CUDA architecture list、`packaging/build_split_cuda.sh` では Split engine の compute capability と CUDA architecture に使います。両スクリプトは別々に同名の値を読みます。

調査対象ソース全体の `ARCH` 参照を確認した結果、Strata のエンジン、サーバー、CLI が実行時に `ARCH` を読む箇所は見つかりませんでした。したがって、起動中の Strata プロセスの環境に設定しても、ここで確認した実行時動作は変わりません。索引の候補名は、上記ビルドスクリプトで環境から値を読むため実在します。

## 値と判定

どちらのスクリプトも Bash の `${ARCH:-既定値}` を使います。未設定または空文字なら既定値になり、空白以外の非空値は文字列としてそのまま後続の CMake 引数に渡されます。スクリプト内で数値変換、空白除去、許容値リストとの照合、clamp は行いません。

| 読み取り箇所 | 未設定・空文字 | 非空値と渡し先 |
| --- | --- | --- |
| `packaging/build_dsv41_cuda.sh` | `86-real;89-real;120` | `-DCMAKE_CUDA_ARCHITECTURES=<ARCH>` |
| `packaging/build_split_cuda.sh` | `86` | `-DSTRATA_SPLIT_ARCH=<ARCH>` および `-DCMAKE_CUDA_ARCHITECTURES=<ARCH>` |

DeepSeek 用スクリプトのコメントは、既定値を sm_86 / sm_89 / sm_120 の SASS と PTX sm_120 の構成と説明しています。また CUDA 12.9 向けには `86-real;89` を指定する例を示しています。これは同スクリプトの用途説明であり、Strata が `ARCH` 値を個別に検証していることを意味しません（`packaging/build_dsv41_cuda.sh:6-11,18,28-31`）。

## 有効になる条件

- `packaging/build_dsv41_cuda.sh` を使う CUDA ビルドでは、スクリプトが `STRATA_ENABLE_CUDA=ON` と `STRATA_BUILD_DSV41=ON` を設定し、`ARCH` を `CMAKE_CUDA_ARCHITECTURES` に渡します。これは独立した `strata-dsv41` バイナリを作る経路です（`packaging/build_dsv41_cuda.sh:28-32`）。同じ CMake 変数が別経路で未指定の場合、Strata の CMake は DSV41 ビルド向けに `86-real;89-real;120` を既定にしますが、このスクリプトは明示的に `-D` を渡すため、その既定処理より先にスクリプトの値が指定されます（`CMakeLists.txt:225-239`）。
- `packaging/build_split_cuda.sh` を使う Linux CUDA ビルドでは、`ARCH` が `STRATA_SPLIT_ARCH` と `CMAKE_CUDA_ARCHITECTURES` の両方に渡されます。Split engine 自体は `STRATA_BUILD_SPLIT` で opt-in されます（`packaging/build_split_cuda.sh:22-25`; `CMakeLists.txt:2945-2949`）。CMake は `STRATA_SPLIT_ARCH` を `FNX_ARCH` の compile definition にし、CUDA target architecture を `<STRATA_SPLIT_ARCH>-real` に設定します（`src/split/CMakeLists.txt:92-117`）。
- Split engine の CUDA 実行時には、モデルを読み込む際に各 GPU の compute capability とビルド時の `FNX_ARCH` を比較します。不一致なら `card_check.hpp` の `require_card_arch()` が `runtime_error` を投げ、エラーメッセージに検出した capability と `rebuild with make ARCH=<値>` を含めます（`src/split/src/model.cpp:91-120`; `src/split/src/card_check.hpp:13-23`）。これはビルド値による実行時カード検査であり、実行時に環境変数 `ARCH` を再読込するものではありません。
- `ARCH` は上記のビルドスクリプトを実行しない通常の Strata CLI / サーバー経路には接続されていません。なお Split の CMake 設定自体が Linux CUDA または特定 HIP 経路以外では target をスキップする条件を持ちますが、この CUDA 用スクリプトは `STRATA_ENABLE_CUDA=ON` を指定します（`src/split/CMakeLists.txt:20-30`）。

## 実行時の詳細

値は各ビルドスクリプトの起動時にシェル展開され、その一回の CMake 呼び出しに渡されます。スクリプトには `ARCH` の再読込やキャッシュ処理はありません。Split の場合、ビルド時に `FNX_ARCH` へ埋め込まれ、モデル読み込み時のカード検査に使われます。DeepSeek 用の値は CUDA バイナリをコンパイルする architecture 指定として渡されます。スクリプトから runtime の子プロセスへ `ARCH` を転送する処理は確認できません。

どちらのスクリプトも `set -eu` で実行し、CMake/Ninja の失敗は失敗経路になります。Split スクリプトはさらに生成バイナリが見つからない場合に `build_split_cuda.sh: no strata-split-<N>` を stderr に出して終了し、生成バイナリに CUDA peer 関数への未定義参照があればその旨を stderr に出して終了します（`packaging/build_split_cuda.sh:12,22-35`）。DeepSeek スクリプトは実行可能な `strata-dsv41` が無い場合に `no <path>` を stderr に出して終了し、`COMMIT` を指定しているのにビルド ID がバイナリに含まれない場合もエラーを出して終了します（`packaging/build_dsv41_cuda.sh:13,32-36`）。これらの出力はスクリプトの失敗経路であり、無効な `ARCH` に固有の Strata エラー文言はありません。`ARCH` の形式検証や無効値時の Strata 独自 fallback はコード上に確認できず、CMake / CUDA toolchain に渡した後のエラー内容はその実装に依存します。

## 根拠

- `packaging/build_dsv41_cuda.sh:6-18,28-38` — DeepSeek CUDA ビルドの用途、既定値、引数への引き渡し、ビルド確認と出力。
- `packaging/build_split_cuda.sh:6-19,22-38` — Split CUDA ビルドの用途、既定値、2つの CMake 引数への引き渡し、失敗経路。
- `CMakeLists.txt:225-239,2945-2949` — CUDA architecture 既定処理と Split target の opt-in。
- `src/split/CMakeLists.txt:92-117` — `STRATA_SPLIT_ARCH` から compile definition と CUDA target architecture への反映。
- `src/split/src/model.cpp:91-120`, `src/split/src/card_check.hpp:13-23` — ビルド時アーキテクチャの必須条件と実行時カード検査。
- `docs/DEEPSEEK41.md:221-240` — DeepSeek engine の手動ビルド説明。コード説明と同様に Linux で `ARCH=...` を使うと記載。
