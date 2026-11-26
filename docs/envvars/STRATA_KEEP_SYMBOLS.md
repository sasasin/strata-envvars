# `STRATA_KEEP_SYMBOLS`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

これは Strata エンジンの実行時設定ではなく、Strata 同梱のリリース用パッケージングスクリプトが読むビルド時スイッチである。ビルドスクリプトは有効時に CMake へ -DSTRATA_KEEP_SYMBOLS=ON を渡し、エンジンや strata-vision のホスト側デバッグ情報をビルドし、パッケージ化前にシンボルファイルを別フォルダーへ保存する。無効時はこの CMake オプションとシンボル抽出処理を省く。エンジン本体にこの環境変数を読む箇所はなく、生成・サーバー実行中の挙動を切り替える環境変数ではない。Windows CUDA パッケージャーの判定と、Linux/macOS 系パッケージャーが source する共通シェルで使われる（tools/packaging/build_cuda_windows.py:68-85,181-207、tools/packaging/symbols_build.sh:1-19）。

## 値と判定

いずれも文字列を数値や真偽値として parse せず、文字列全体が厳密に 0 かを比較する。したがって 00、0 、false、off などは無効値ではなく「有効」扱いになる。空白除去はない。

| 呼び出し元 | unset | 設定時に有効（シンボルを保持） | 設定時に無効（保持しない） |
|---|---|---|---|
| Windows CUDA: build_cuda_windows.py | 1 を既定値として有効 | 0 以外すべて（例: 1, 00, 空文字, false, 0 ） | 文字列が厳密に 0 |
| Linux CUDA/HIP/SYCL・macOS 共通: symbols_build.sh | ${STRATA_KEEP_SYMBOLS:-1} により未設定・空文字とも 1 扱いで有効 | 展開後の文字列が厳密に 0 以外（例: 1, 00, false, 0 ） | 展開後の文字列が厳密に 0 |

Windows Python 側では os.environ.get("STRATA_KEEP_SYMBOLS", "1") != "0"、シェル側では [ "${STRATA_KEEP_SYMBOLS:-1}" != 0 ] が判定式であり、明示的な空文字の扱いに差がある（tools/packaging/build_cuda_windows.py:83-85、tools/packaging/symbols_build.sh:12-13）。

## 有効になる条件

- 対応するパッケージング経路を実行する必要がある。Windows の対象は tools/packaging/build_cuda_windows.py の CUDA 12/13 ビルドであり、Linux の CUDA・HIP・SYCL、macOS Metal は symbols_build.sh を source する各ビルドスクリプトである（tools/packaging/build_cuda_windows.py:1-5,158-165、tools/packaging/build_cuda_linux.sh:37-46、tools/packaging/build_hip_linux.sh:57-66、tools/packaging/build_sycl_linux.sh:40-52、tools/packaging/mac/build_engine.sh:56-67）。
- 判定が有効ならスクリプトが CMake に -DSTRATA_KEEP_SYMBOLS=ON を渡す。CMake オプション自体の既定値は OFF で、有効時にコンパイル・リンクのデバッグ情報フラグを設定する（engine/cmake/strata_symbols.cmake:15-40）。
- CMake の STRATA_KEEP_SYMBOLS はビルド設定名で、環境変数をエンジンが直接読む機構ではない。環境変数の判定結果をスクリプトが -D...=ON に変換する必要がある。Windows CUDA では同じ判定結果を STRATA_SYM_CMAKE として vision ビルドにも渡し、Linux/macOS では sym_cmake をエンジン・reader の configure 引数に加える（tools/packaging/build_cuda_windows.py:76-80,201-204、tools/packaging/build_cuda_linux.sh:44-60、tools/packaging/build_hip_linux.sh:64-81、tools/packaging/mac/build_engine.sh:57-76）。
- 対応スクリプトを介さず CMake を直接実行する場合、この環境変数の判定は行われない。CMake オプションを直接指定しなければ既定 OFF となる（engine/cmake/strata_symbols.cmake:15-17）。

## 実行時の詳細

Windows CUDA パッケージャーは keep_symbols() を configure 引数の作成時、エンジンビルド後の PDB 抽出時、vision 用環境変数の構築時、vision PDB 抽出時に呼び、各呼び出しで現在の Python プロセスの os.environ を参照する。通常の起動方法では環境変数はプロセス開始時に決まり、別途 os.environ を書き換えるコードはこの判定箇所にない。無効時はエンジン・vision のシンボル抽出をスキップし、vision 子プロセスへ STRATA_SYM_CMAKE も設定しない（tools/packaging/build_cuda_windows.py:78-85,181-207）。

共通シェルは symbols_build.sh を source した時点で一度 sym_cmake を決める。その後の CMake configure に渡され、シンボル抽出関数 symbols_keep も同じ値が空かどうかで実行可否を判断する。シェル実行中に環境変数を変更しても、すでに設定済みの sym_cmake には反映されない（tools/packaging/symbols_build.sh:12-19）。同じ helper は Linux CUDA/HIP/SYCL、macOS、DGX Spark 向け CUDA ビルドスクリプトから利用される（tools/packaging/build_cuda_linux.sh:39-46,74-75、tools/packaging/build_hip_linux.sh:59-66,98-101、tools/packaging/build_sycl_linux.sh:40-52,68-71、tools/packaging/mac/build_engine.sh:56-67,78-85、tools/packaging/build_cuda_linux_aarch64.sh:29-38）。

保持が有効なら、Windows は keep_symbols.py pe --require で対象実行ファイルの PDB を抽出し、Linux は keep_symbols.py elf --require で stage バイナリからデバッグ情報を分離する。macOS は keep_symbols.py macho を呼ぶ（tools/packaging/build_cuda_windows.py:185-207、tools/packaging/build_cuda_linux.sh:73-75、tools/packaging/build_hip_linux.sh:98-101、tools/packaging/mac/build_engine.sh:82-85）。CMake 側では OS・compiler に応じたホストコード用フラグを設定し、ON 時に configure 出力へ STRATA_KEEP_SYMBOLS: host debug information on (the code does not change) と表示する（engine/cmake/strata_symbols.cmake:17-40）。

## ログと測定値

有効時の CMake configure 出力は STRATA_KEEP_SYMBOLS: host debug information on (the code does not change)。Windows で CodeView レコードがない場合は keep_symbols.py が <file>: no CodeView record (built without -DSTRATA_KEEP_SYMBOLS=ON / /DEBUG) を表示し、--require により終了コード 1 を返す。Linux ELF で .debug_info がない場合も <file>: no debug information (built without -DSTRATA_KEEP_SYMBOLS=ON) を表示し、--require なら終了コード 1 になる（engine/cmake/strata_symbols.cmake:40、tools/packaging/keep_symbols.py:105-119,182-196）。パッケージャーは子コマンドの非ゼロ終了を失敗として終了する（tools/packaging/build_cuda_windows.py:152-155）。環境変数の未知文字列そのものに対する警告やエラーは実装されていない。性能測定値は該当しない。

## 根拠

- tools/packaging/build_cuda_windows.py:68-85,181-207 — Windows CUDA での環境変数読み取り、CMake 引数、PDB 抽出と vision への伝達。
- tools/packaging/symbols_build.sh:12-19 — 共通シェルでの値判定、CMake 引数と抽出関数の有効化。
- engine/cmake/strata_symbols.cmake:15-40 — CMake オプション既定値、ホストデバッグ情報フラグ、configure メッセージ。
- tools/packaging/build_cuda_linux.sh:39-46,73-75、tools/packaging/build_hip_linux.sh:59-66,98-101、tools/packaging/build_sycl_linux.sh:40-52,68-71、tools/packaging/build_cuda_linux_aarch64.sh:29-38、tools/packaging/mac/build_engine.sh:56-67,78-85 — 共通シェルの適用経路。
- tools/packaging/keep_symbols.py:105-128,182-205 — 必須シンボルがない場合の出力・失敗経路。
