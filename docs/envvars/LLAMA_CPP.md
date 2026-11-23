# `LLAMA_CPP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`LLAMA_CPP` は `tools/packaging/build_sycl_linux.sh` が読む、ggml のソース checkout を指定する旧名のビルド用 override です。値は `-DSTRATA_GGML_DIR=<値>` として SYCL エンジンの CMake configure に渡されます。通常の実行時環境変数ではなく、エンジンやサーバーの実行時動作を制御する読み取り箇所はありません（`tools/packaging/build_sycl_linux.sh:42-50`）。

現在は同じスクリプト内で `STRATA_GGML_DIR` が優先され、`LLAMA_CPP` はその値が unset または空のときだけ使われる互換用 alias です。他のビルドスクリプト（例: CUDA Linux）は `LLAMA_CPP` を参照せず、`STRATA_GGML_DIR` だけを CMake に渡します（`tools/packaging/build_cuda_linux.sh:37-45`）。

## 値と判定

シェルの `${VAR:-word}` 展開を使い、値を文字列としてパスに連結します。trim、引用符除去、検証、数値変換はありません。空白だけの値も空ではない値として扱われます。ただし組み立てた `ggml` 引数は引用符なしで CMake に渡されるため、空白を含む値はシェルの word splitting を受け、単一のパス引数としては渡りません（`tools/packaging/build_sycl_linux.sh:42-50`）。変数の参照は `setvars.sh` と `shape_setup` の後、CMake configure の直前です。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_GGML_DIR` が unset または空 | `LLAMA_CPP` も unset/空なら override 指定なし | `LLAMA_CPP=/src/llama.cpp` は CMake 引数 `-DSTRATA_GGML_DIR=/src/llama.cpp` になる | `LLAMA_CPP` の空文字は引数を作らない。`0`、`false`、`true` は特別扱いされず、いずれもパス文字列として渡る |
| `STRATA_GGML_DIR` が非空 | `LLAMA_CPP` は参照結果として選ばれない | `STRATA_GGML_DIR=/src/ggml` が CMake に渡る | `LLAMA_CPP` の値は優先順位が低いため採用されない |

このスクリプトで `LLAMA_CPP` が意味を持つのは `STRATA_GGML_DIR` が unset または空の場合だけです。空文字、`0`、`false` を boolean として解釈する処理はありません（`tools/packaging/build_sycl_linux.sh:42-50`）。

## 有効になる条件

- `tools/packaging/build_sycl_linux.sh` を Linux x86_64 の Intel oneAPI SYCL ビルド環境で実行する必要があります。同スクリプトは `icpx` 等を確認し、失敗時はエラーを stderr に出して終了します（`tools/packaging/build_sycl_linux.sh:8-18,30-38`）。
- 値があれば CMake cache 変数 `STRATA_GGML_DIR` に転送されます。CMake はこれを vendor 済み `engine/third_party/strata-ggml` に代わる checkout として選択します（`engine/cmake/strata_ggml.cmake:6-16`）。
- ただしこのパッケージスクリプトは `STRATA_SYCL_PARITY=OFF` を指定し、SYCL CMake の `STRATA_OWN_CPU_QUANT` は既定で `ON` です。この組み合わせでは ggml の `add_subdirectory` を行わず、「no ggml in this build」と記された分岐になります。そのためスクリプトの既定構成では、`LLAMA_CPP` が CMake に渡っても外部 checkout の ggml はビルドに取り込まれません（`tools/packaging/build_sycl_linux.sh:49-50`; `engine/sycl/CMakeLists.txt:204-219,220-227`）。
- `STRATA_CMAKE_EXTRA` 等で `STRATA_SYCL_PARITY` または `STRATA_OWN_CPU_QUANT` を変更して ggml を追加する構成では、選択した checkout の `${root}/ggml` が追加対象です。ディレクトリが存在しない場合の CMake の `add_subdirectory` 失敗はこの条件下で起こり得ます（`engine/sycl/CMakeLists.txt:219-227`; `engine/cmake/backends/sycl.cmake:5-15`）。

## 実行時の詳細

この値を読むのはビルドスクリプトが実行されたときの一度だけです。実行中の環境変更を再読する処理や、生成されたエンジン／子プロセスへ `LLAMA_CPP` を転送する処理はありません。スクリプトは選択した値を CMake の configure 引数へ変換し、その後 `cmake --build` で `strata` target をビルドします（`tools/packaging/build_sycl_linux.sh:42-51`）。

値が unset/空なら CMake 引数を省略し、CMake 側は vendored `third_party/strata-ggml` を root として選びます（`engine/cmake/strata_ggml.cmake:11-16`）。非空なら CMake cache に値が設定されますが、前節の既定 SYCL package 条件では ggml を追加しないため、そこから実行ファイルの挙動が変わることはコード上確認できません。

## ログと測定値

`LLAMA_CPP` の値を表示する専用ログや警告はありません。SYCL configure/build 自体のエラーは CMake の出力と終了状態に現れます。スクリプトは後続で `env -i <package>/strata --version` を実行し、失敗時に `build_sycl_linux.sh: env -i ... --version does not run` を stderr に出して終了しますが、これは `LLAMA_CPP` の個別検証ではありません（`tools/packaging/build_sycl_linux.sh:49-51,76-80`）。関連する Strata の測定値は確認できません。

## 根拠

- `tools/packaging/build_sycl_linux.sh:42-50` — alias の優先順位、空値の処理、CMake への転送。
- `tools/packaging/build_cuda_linux.sh:37-45` — CUDA Linux スクリプトでは `STRATA_GGML_DIR` のみ参照。
- `engine/cmake/strata_ggml.cmake:6-16` — CMake の外部 checkout / vendored tree 選択。
- `engine/sycl/CMakeLists.txt:204-227`、`engine/cmake/backends/sycl.cmake:5-15` — SYCL build 条件と ggml を追加する経路。
