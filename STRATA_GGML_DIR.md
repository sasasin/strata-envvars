# `STRATA_GGML_DIR`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの内部動作は対象外。

## 役割

この名前は通常の実行時環境変数ではなく、主に CMake の cache PATH 変数として使われます。llama.cpp の checkout を指定し、その中の `ggml` ディレクトリを Strata のビルドに組み込みます。空なら、リポジトリが固定した llama.cpp revision を CMake が取得します。

環境変数として直接読む Strata 所有コードは `tools/hip/build_windows.bat` です。この Windows HIP ビルドラッパーは、設定されていれば値を `-DSTRATA_GGML_DIR=...` にして CMake configure に渡します。一般の CMake 実行や Linux のセットアップで同名のプロセス環境変数を読む処理は確認できません。`setup.py` の HIP/CUDA ビルドは環境変数ではなく、内部で得た `llama` のパスを `-DSTRATA_GGML_DIR` として渡します。

## 値と判定

| 経路 | 未設定・空 | 設定値 |
|---|---|---|
| `tools/hip/build_windows.bat` の環境変数 | `GGML` を空にし、CMake に当該 `-D` 引数を渡さない。CMake 側の空の既定値となり、固定 revision を取得する | 値中の `\` を `/` に置き換え、`-DSTRATA_GGML_DIR=<値>` として configure に渡す |
| CMake cache 変数 | 空文字が既定値。`STRATA_NATIVE_EXPERTS` が有効なら FetchContent で固定 revision `3cf03257f219afbe7334045ff7c6a06ac68c627d` を取得 | `<値>/ggml` を `add_subdirectory` に渡す |

バッチは `if defined` で有無を判定し、文字列の trim、存在確認、revision 検査はしません。パスが無効、または `<値>/ggml` が存在しない場合、Strata はそのパスを `add_subdirectory` に渡し、configure が失敗します。値は CMake が解釈するディレクトリパスであり、commit hash や llama.cpp URL を指定する機能ではありません。

## 有効になる条件

- Windows HIP の `tools/hip/build_windows.bat` を使う場合、環境変数を CMake に渡すのは `%BUILD_DIR%\build.ninja` がまだ存在しない初回 configure 時だけです。既存 build directory ではこのスクリプトは configure をスキップするため、環境変数を変えても cache 値は更新されません。変更を反映するには CMake を再 configure する必要があります。
- 通常の CMake 経路では、OS 環境変数だけを設定しても CMake cache 変数にはなりません。`-DSTRATA_GGML_DIR=...` のように cache 変数として渡す必要があります。
- `STRATA_NATIVE_EXPERTS=OFF` の場合、主な `ggml` の組み込みブロックは実行されません。このオプションはメイン構成と SYCL 構成で既定 ON です。Windows HIP ラッパーは明示的に `STRATA_NATIVE_EXPERTS=ON` を渡します。
- CUDA では指定 checkout が native expert support に使われるほか、prompt MMQ ソースの場所としても選ばれます。HIP の `STRATA_PREFILL_MMQ` 経路も同じ checkout 内の CUDA/HIP 共通 MMQ ソースを参照し、必要ファイルがなければ CMake の fatal error になります。
- SYCL の `sycl/CMakeLists.txt` にも同名の CMake cache 変数がありますが、そこでは環境変数を直接読みません。

## 実行時の詳細

この設定が作用するのは configure/build 時です。アプリ起動時やリクエスト処理時に値を読むコードはなく、実行中の Strata の挙動を切り替える環境変数ではありません。

CMake は native experts が有効なとき、指定があれば `${STRATA_GGML_DIR}/ggml` を `add_subdirectory` します。指定がなければ `FetchContent` で `ggml-org/llama.cpp` の固定 revision `3cf03257f219afbe7334045ff7c6a06ac68c627d` を取得して、その `ggml` を追加します。CUDA の prompt MMQ と HIP の `STRATA_PREFILL_MMQ` も、指定 checkout がある場合はその中の `ggml/src/ggml-cuda` を参照します。

Windows HIP バッチは値のパス区切りを変換しますが、CMake 引数の値部分を個別に引用符で囲んでいません。空白を含むパスの処理はこのバッチから保証できず、失敗する可能性があります。これはバッチの引数構成からの判断です。

## 文書との照合

`docs/AMD_HIP.md` はオフラインビルド用に、リポジトリが pin した llama.cpp revision の checkout を指定するよう案内しています。現行 CMake は空値の場合に同じ固定 revision を取得し、指定値の場合はその checkout を使います。`docs/INTEL_ARC.md` も build fetch の代わりに checkout を指定できるとしています。いずれも CMake 設定についての説明で、プロセス環境変数を全ビルド経路で読むという意味ではありません。

## 根拠

- `tools/hip/build_windows.bat:13-18,64-75` — 環境変数一覧、値の区切り変換、初回 configure 時の CMake 引き渡し。
- `CMakeLists.txt:104,1208-1265` — `STRATA_NATIVE_EXPERTS` の既定値、CMake cache 変数、ローカル ggml の追加または固定 revision の取得。
- `CMakeLists.txt:1353-1365,1418-1429` — CUDA/HIP prompt MMQ で選択 checkout と必要ソースを使う条件。
- `sycl/CMakeLists.txt:151-175` — SYCL の cache 変数と、環境変数ではなく CMake 変数として扱う経路。
- `setup.py:2655-2673,3417-3426` — HIP/CUDA セットアップが内部の `llama` パスを `-DSTRATA_GGML_DIR` に渡す箇所。
- `docs/AMD_HIP.md:151-154`, `docs/INTEL_ARC.md:60-62` — checkout 指定と FetchContent に関する説明。
