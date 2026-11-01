# `LLAMA_CPP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`LLAMA_CPP` は `packaging/build_sycl_linux.sh` 専用のビルド時環境変数です。値が空でない場合、SYCL エンジンの CMake configure にローカル llama.cpp checkout の場所を渡し、FetchContent のネットワーク取得を無効にします。Strata の実行ファイル、CLI、サーバーが起動後に読む環境変数ではありません。

## 値と判定

| 値 | スクリプトの扱い |
|---|---|
| 未設定 | 空文字と同じ。`LLAMA_CPP` 用の CMake 引数を追加しない。 |
| 空文字 | 未設定と同じ。 |
| 空でない文字列 | その文字列を `FETCHCONTENT_SOURCE_DIR_STRATA_LLAMACPP` の値として CMake に渡し、`FETCHCONTENT_FULLY_DISCONNECTED=ON` も渡す。 |

値の存在判定は shell の `[ -n "${LLAMA_CPP:-}" ]` であり、空白除去、パス検証、正規化、commit 検査はありません。空白だけの値も指定ありとして扱われます。値は `ggml` 文字列へ埋め込まれ、後で未引用の `$ggml` として CMake コマンドに展開されます。そのため、空白を含むパスは単語分割され、glob 文字 `*` などもファイル名展開の対象になります。

## 有効になる条件

- Linux の SYCL エンジンパッケージを作る `packaging/build_sycl_linux.sh` を実行したときだけ評価されます。このスクリプトは oneAPI `setvars.sh` を読み込んで `icpx` を使い、`cmake -S sycl` を実行します。
- `LLAMA_CPP` が空でない場合、この指定が同スクリプト内の `third_party/llama.cpp/ggml` 自動検出より優先します。
- `LLAMA_CPP` が未設定または空で、リポジトリ内に `third_party/llama.cpp/ggml` ディレクトリがあれば、代わりに `-DSTRATA_GGML_DIR=<repo>/third_party/llama.cpp` を渡します。
- どちらも該当しない場合、スクリプトは llama.cpp source 指定を渡しません。SYCL CMake は `STRATA_NATIVE_EXPERTS` が有効な既定経路で pinned commit `3cf03257f219afbe7334045ff7c6a06ac68c627d` を FetchContent で取得しようとします。

この変数は `packaging/build_sycl_linux.sh` に限られ、他の Strata のビルドスクリプトが同名の環境変数を読む箇所はありません。`LLAMA_CPP_COMMIT` は `setup.py` の固定文字列定数などとして別に現れますが、`LLAMA_CPP` の読み取りや同変数の値ではありません。

## 実行時の詳細

スクリプトの configure 時に一度だけ shell が環境値を展開します。エンジン実行時への引き継ぎや、CLI 引数による上書きはありません。CMake には `FETCHCONTENT_SOURCE_DIR_STRATA_LLAMACPP=<値>` と `FETCHCONTENT_FULLY_DISCONNECTED=ON` が渡ります。SYCL CMake は `STRATA_GGML_DIR` が空なら `FetchContent_Declare(strata_llamacpp ...)` で pinned repository を宣言し、FetchContent の populated source の `ggml` サブディレクトリを追加します。このため、指定パスはその FetchContent source として使われ、ネットワーク取得は許可されません。ローカルソースが不正・不足なら configure の CMake エラーで停止し、`set -e` により後続の build/package 手順へ進みません。

スクリプトの `BUILD` で既定と異なる CMake build directory を指定できます。同じ build directory を再利用する場合、以前 CMake に `-D` で渡した FetchContent 変数が CMake cache に残る可能性があります。シェル側で `LLAMA_CPP` が未設定でも、それだけでは既存 cache を消去しません。

スクリプト自身は `LLAMA_CPP` の選択値を表示する専用ログや独自の警告を出しません。CMake configure が失敗した場合は CMake のエラーが出てスクリプトが中断し、configure が通れば `cmake --build` に進みます。CMake build cache に値が記録されるのは configure/build directory 内の話で、実行時環境変数としては保存されません。

## 根拠

- `packaging/build_sycl_linux.sh:2-16,39-46` — Linux SYCL package build であること、空でない値を FetchContent source override と disconnected mode に変換すること、ローカル `third_party/llama.cpp` への fallback、CMake 実行。
- `packaging/build_sycl_linux.sh:17,25-26,44-46` — `set -eu`、`BUILD` による build directory 指定、configure/build の失敗時に後続へ進まない制御。
- `sycl/CMakeLists.txt:171-202` — native experts の条件、`STRATA_GGML_DIR` が指定された場合の ggml source 使用、未指定時の pinned llama.cpp FetchContent と `ggml` の追加。
- `setup.py:222-223` — `LLAMA_CPP_COMMIT` は固定値から作る別の定数であり、ここでは `LLAMA_CPP` を環境から読まない。
