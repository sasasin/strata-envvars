# `STRATA_GGML_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、Strata のエンジンをソースから構成するとき、同梱の `engine/third_party/strata-ggml` の代わりに使う llama.cpp checkout の場所を指定します。実行中のエンジンが読む設定ではありません。`terminal/setup.py` は環境変数を確認して CMake の `-DSTRATA_GGML_DIR=...` に変換し、ビルド用スクリプトも値を CMake に渡します。CMake 側は指定された checkout の `ggml` サブディレクトリを選びます（`terminal/setup.py:4226-4235`、`engine/cmake/strata_ggml.cmake:7-16`）。

環境変数名の実参照を全件確認しました。環境から値を読むのは `terminal/setup.py` と各ビルド用スクリプトです。CMake の `STRATA_GGML_DIR` は環境変数を直接読むものではなく、スクリプトが渡す CMake の cache 変数です。候補一覧との食い違いはありません。

## 値と判定

値は真偽値や数値ではなく、checkout へのパスとして扱われます。文字列の trim、大小文字変換、数値変換はありません。

| 読み取り経路 | 未設定・空文字 | 非空文字列 | 無効なパス |
|---|---|---|---|
| `terminal/setup.py` の `llama_override()` | `None` を返し、呼び出し側から CMake 定義を渡さない | `<値>/ggml/CMakeLists.txt` が存在する場合だけ `Path` を返す | 条件に合わなければ `None`。この判定自体は警告しない。新規 cache なら同梱 ggml が選ばれる（`terminal/setup.py:4226-4235`） |
| Linux/macOS/Spark/HIP Windows のシェルスクリプト | 空として扱い、通常は `-DSTRATA_GGML_DIR` を付けない | 値を `-DSTRATA_GGML_DIR=...` として渡す。SYCL Linux のみ、空なら旧名 `LLAMA_CPP` を使う（`tools/packaging/build_cuda_linux.sh:38-45`、`tools/packaging/build_sycl_linux.sh:43-50`、`tools/packaging/mac/build_engine.sh:49-65`、`engine/spark/build_engine.sh:26-27`、`terminal/tools/hip/build_windows.bat:71-78`） | スクリプトでは checkout 構造を検証しない。CMake の構成段階まで渡る |
| Windows の Python パッケージビルダー | `os.environ.get(..., "")` の空文字となり、定義を付けない | 空でなければ値を渡し、`\` を `/` に置き換える | CMake に渡した後の判定（`tools/packaging/build_cuda_windows.py:68-78,174`） |

`0`、`1`、`true`、`false` も特別な値ではありません。`terminal/setup.py` ではそれらの文字列で指される場所に `ggml/CMakeLists.txt` がなければ無効として扱い、シェル／パッケージ用経路ではパス文字列としてそのまま CMake に渡します。空白を除去する処理もありません（`terminal/setup.py:4229-4235`、各スクリプトの上記箇所）。

シェルスクリプトの一部は `-D` 引数を文字列変数に組み立て、引用符なしで展開します。そのためパスに空白がある場合、CMake へ一つのパス引数として渡る保証はありません。Windows の Python パッケージビルダーは `-D` 全体を一つの引数として渡します（`tools/packaging/build_cuda_linux.sh:38,43-45`、`tools/packaging/mac/build_engine.sh:49,64`、`tools/packaging/build_cuda_windows.py:76-78`）。

CMake は `STRATA_GGML_DIR` を空の `CACHE PATH` として宣言し、空なら vendored tree、非空なら指定 root を選びます（`engine/cmake/strata_ggml.cmake:11-16`）。そのため環境変数を読まない直接の CMake 実行では、環境変数を設定しただけでは効きません。CMake の `-DSTRATA_GGML_DIR=...` が必要です。既存 build directory に cache 値が残っている場合、スクリプトが空値を理由に `-D` を省略しても、その cache 値はこの `set(... CACHE ...)` で空に戻されません。

## 有効になる条件

- `terminal/setup.py` 経由では、環境変数を読んだ時点で値が非空で、かつ `<値>/ggml/CMakeLists.txt` が存在する必要があります。値が空または条件不成立なら、この関数は override を返しません（`terminal/setup.py:4226-4235`）。
- CMake で実際に ggml を追加する構成である必要があります。通常の engine project では `STRATA_NATIVE_EXPERTS` が有効で、さらに `STRATA_BUILD_TESTS` が有効か `STRATA_OWN_CPU_QUANT` が無効のとき `strata_ggml_configure_root()` が呼ばれます。テストなし・Strata 独自 CPU pool の構成では ggml を追加せず、選択したパスはビルドに使われません（`engine/CMakeLists.txt:641-650`）。
- SYCL では `STRATA_NATIVE_EXPERTS` が有効で、`STRATA_OWN_CPU_QUANT` が無効か `STRATA_SYCL_PARITY` が有効なとき ggml を追加します。どちらにも当たらない構成では CMake が「no ggml in this build」と表示します（`engine/sycl/CMakeLists.txt:219-227`）。
- Metal では `STRATA_OWN_CPU_QUANT` が無効か `STRATA_BUILD_TESTS` が有効な場合に ggml を追加します。どちらも無効なら同梱／外部どちらの ggml もこの build では使いません（`engine/metal/CMakeLists.txt:116-127`）。
- CMake が ggml を追加する構成では、指定 root の下に `ggml` ソースが必要です。Metal は `${_strata_ggml_root}/ggml/CMakeLists.txt` を検査し、なければ `ggml sources not found in '…' (third_party/strata-ggml, or the -DSTRATA_GGML_DIR checkout)` で構成を停止します（`engine/metal/CMakeLists.txt:118-123`）。共通 resolver は値を選ぶだけで存在確認しません（`engine/cmake/strata_ggml.cmake:11-16`）。

## 実行時の詳細

`terminal/setup.py` は `llama_override()` が呼ばれるたびに `os.environ.get("STRATA_GGML_DIR")` を読み、その場でパス検査します。値を環境変数用の static cache に保存する処理はありません。エンジン構成時には `ggml_defs()` が有効なパスだけを CMake 定義にし、`cmake_build()` が CMake configure を実行します。Windows 用 setup では `-D` 定義内のバックスラッシュをスラッシュに変換します（`terminal/setup.py:4226-4235,6700-6717`）。

シェル系パッケージビルダーは起動中に環境値を取り出して configure 引数を作ります。Linux CUDA、macOS、Spark、SYCL Linux、HIP Windows はそれぞれ値を CMake に渡します。SYCL Linux は `${STRATA_GGML_DIR:-${LLAMA_CPP:-}}` の順で選ぶため、前者が未設定または空なら `LLAMA_CPP` に fallback します（`tools/packaging/build_cuda_linux.sh:38-45`、`tools/packaging/build_sycl_linux.sh:46-50`、`tools/packaging/mac/build_engine.sh:49-65`、`engine/spark/build_engine.sh:26-27`、`terminal/tools/hip/build_windows.bat:72-78`）。

この変数はエンジンプロセスが実行時に読む設定ではなく、CMake configure 時に ggml のソースツリーを選ぶためのものです。setup 内では起動時に一度だけではなく、`llama_override()` の呼び出しごとに環境を読みます（`terminal/setup.py:4226-4230`）。macOS のパッケージスクリプトは同じ値を `strata-vision` の `--llama` にも渡しますが、受け取る `build_vision_mac.sh` はこの引数を「no longer used」として読み飛ばします（`tools/packaging/mac/build_engine.sh:49-50,70-75`、`tools/packaging/build_vision_mac.sh:14-21`）。CMake cache は build directory ごとに残るため、実行中の環境変更では既存 cache は変わらず、次の configure で `-D` が渡されたときに更新されます（`engine/cmake/strata_ggml.cmake:11-16`）。

## ログと測定値

有効な値を受け取ったことだけを知らせる専用ログは確認できません。`terminal/setup.py` がパス検査で値を退ける場合も、この判定箇所からは警告を出しません（`terminal/setup.py:4226-4230`）。ggml を要求する Metal 構成でソースが見つからないときは、前節の `message(FATAL_ERROR ...)` で CMake configure が失敗します（`engine/metal/CMakeLists.txt:118-123`）。setup 経由の configure が失敗した場合、setup はそのコマンドの失敗を伝播させます（`terminal/setup.py:6716-6733`）。測定値はありません。

`docs/DETAILS.md` にこの変数の記載は見つかりませんでした。ソースの CMake コメントと `engine/third_party/strata-ggml/UPSTREAM.md` の記述は、vendored ggml と CMake override の関係を示す設計説明として確認しましたが、実際の条件・失敗経路は上記 CMake 実装に基づいています。

## 根拠

- 環境変数の読み取り、パス検査、CMake 定義生成: `terminal/setup.py:4226-4235`
- setup の configure 引数生成・Windows パス変換: `terminal/setup.py:6700-6717`
- 共通 CMake root の選択と ggml の追加: `engine/cmake/strata_ggml.cmake:7-16,19-60`
- 通常 engine の ggml 利用条件: `engine/CMakeLists.txt:641-650`
- SYCL と Metal の ggml 利用条件: `engine/sycl/CMakeLists.txt:219-227`、`engine/metal/CMakeLists.txt:116-127`
- パッケージ用スクリプトから CMake への転送: `tools/packaging/build_cuda_linux.sh:38-45`、`tools/packaging/build_sycl_linux.sh:43-50`、`tools/packaging/mac/build_engine.sh:49-65`、`engine/spark/build_engine.sh:26-27`、`tools/packaging/build_cuda_windows.py:68-78,174`、`terminal/tools/hip/build_windows.bat:71-78`
