# `STRATA_CMAKE_EXTRA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

これは Strata の実行時設定ではなく、いくつかの Strata エンジン構築スクリプトが CMake のエンジン configure 呼び出しに追加引数を挿入するためのビルド時環境変数です。Strata のエンジン実行ファイルやサーバーがこの名前を読み取る箇所はありません。渡した引数の効果は、その引数が指定する CMake 変数とビルド構成次第です。Linux CUDA/HIP/SYCL のパッケージビルド、DGX Spark の CUDA ビルド、Windows CUDA パッケージビルド、および Windows HIP ビルドで参照されます（`tools/packaging/build_cuda_linux.sh:40-45`; `tools/packaging/build_hip_linux.sh:60-67`; `tools/packaging/build_sycl_linux.sh:40-51`; `engine/spark/build_engine.sh:46-54`; `tools/packaging/build_cuda_windows.py:151-177`; `terminal/tools/hip/build_windows.bat:71-89`）。

Windows CUDA では `configure_args()` が固定引数に ggml 指定を加え、その後ろに `extra` を連結します。同じ CMake cache 変数を重ねて渡した場合は extra 側が後段です（`tools/packaging/build_cuda_windows.py:68-78,166-174`）。

## 値と判定

実行時機能の ON/OFF 値として parse されません。構築スクリプトが環境から取り出した文字列を、CMake の引数列へ展開するだけです。

| 経路 | 未設定・空文字 | 値の分割・処理 | 引数順と適用 |
|---|---|---|---|
| Linux CUDA、HIP、SYCL、および Spark CUDA (POSIX shell) | `${STRATA_CMAKE_EXTRA:-}` が空に展開され、追加引数なし | クォートされていない shell 展開。空白で単語分割され、各単語は pathname expansion の対象にもなる。引用符やエスケープを含む文字列をシェルコードとして再評価する処理はない | エンジンの CMake configure 時に展開。CUDA/HIP/SYCL では固定引数や ggml 引数の後、shape helper が作る引数の前に置かれる（`tools/packaging/build_cuda_linux.sh:42-45`; `tools/packaging/build_hip_linux.sh:63-65`; `tools/packaging/build_sycl_linux.sh:48-51`; `engine/spark/build_engine.sh:51-54`） |
| Windows CUDA (Python) | `os.environ.get(...) or ""` により未設定と空文字はともに空 | Python の `str.split()` が連続する whitespace で分割する。shell の quoting/escaping や glob 展開はしない | token の配列を configure 引数 builder に渡す（`tools/packaging/build_cuda_windows.py:166-174`） |
| Windows HIP (batch) | 未定義なら `%STRATA_CMAKE_EXTRA%` は空 | batch の通常の `%...%` 展開で CMake コマンド行へ挿入。独自 parse・検証はない | `build.ninja` がまだない場合の configure に挿入（`terminal/tools/hip/build_windows.bat:76-85`） |

たとえば POSIX shell で `-DSTRATA_WINDOW_MAX_T=8 -DSTRATA_MMQ=ON` のように渡すと、空白で分かれた各項目が別の CMake 引数になります。`0`、`1`、`true`、`false`、空文字に対する Strata 独自の真偽判定や数値境界はありません。任意の文字列が構築スクリプト側の検査を通る場合も、CMake が受理するかはその引数次第です（例として Windows HIP の説明は `-DSTRATA_WINDOW_MAX_T=8` を挙げます: `terminal/tools/hip/build_windows.bat:25`）。

`SHAPE` も設定された POSIX ビルドでは、helper がこの値を `-DSTRATA_GEOMETRY` を含むかどうかの部分文字列パターンとして調べます。一致すれば既定の `-DSTRATA_GEOMETRY=<SHAPE>` を追加せず、一致しなければ該当 geometry header の存在を確認してその既定引数を追加します。この確認は CMake 引数の parse ではなく文字列パターン判定です（`tools/packaging/shape_build.sh:12-29`）。

## 有効になる条件

- 対応する Strata の構築スクリプトを実行し、エンジンの CMake configure 経路に到達する必要があります。実行ファイル起動時、CLI、サーバーリクエストから読む機能ではありません（上記各 configure 箇所）。
- Windows HIP は `%BUILD_DIR%\build.ninja` が存在しない場合だけ configure するため、既存 build tree がある経路ではこの値を CMake に渡しません（`terminal/tools/hip/build_windows.bat:76-85`）。
- HIP Linux は `VISION_ONLY` が空の場合にだけエンジン configure を行います（`tools/packaging/build_hip_linux.sh:60-69`）。
- POSIX の対応スクリプトで `SHAPE` も指定する場合、値に `-DSTRATA_GEOMETRY` が含まれるかで helper の geometry 引数と header 検査が変わります。自動追加引数がない場合に header が存在しなければ、標準エラーに `shape_build.sh: no header ...` を出して終了コード 2 で停止します。ビルド後の `shape_check` で `strata --geometry` が shape 名と異なればエラーを出して終了します（`tools/packaging/shape_build.sh:15-37`）。
- 対象スクリプトは CUDA、HIP、SYCL 等のそれぞれの構築要件を満たし、configure に到達する必要があります。これは当該変数の値判定ではなく、各スクリプトの実行条件です。

## 実行時の詳細

値はエンジン configure 呼び出し時に環境から展開されます。POSIX スクリプトは configure のたびに現在の環境値を展開します。Windows CUDA Python スクリプトも `main()` 内で値を取得して configure 引数を組み立てます。子プロセスへ渡す後続の build 実行には `STRATA_CMAKE_EXTRA` 自体を専用設定する処理はなく、configure 呼び出しの argv にだけ追加値が載ります（`tools/packaging/build_cuda_windows.py:166-177`; `tools/packaging/build_cuda_linux.sh:42-50`; `tools/packaging/build_sycl_linux.sh:48-51`）。

POSIX CUDA/HIP/SYCL の行ではこの変数由来の引数は固定 configure 引数や ggml 指定より後ろにあります。`SHAPE` が設定され helper が `shape_cmake` を作った場合はその後ろです（`tools/packaging/build_cuda_linux.sh:43-45`; `tools/packaging/build_hip_linux.sh:63-65`; `tools/packaging/build_sycl_linux.sh:49-51`; `engine/spark/build_engine.sh:51-54`）。同じ CMake cache 変数を重ねて指定した場合の最終的な扱いは CMake configure に委ねられ、Strata 側の独自優先規則はありません。Windows CUDA では extra が ggml 指定より後ろです（`tools/packaging/build_cuda_windows.py:68-78`）。

Windows HIP は `build.ninja` の存在確認で再 configure を省くため、既存 build tree の cache を使う場合は環境値を変えても configure には反映されません（`terminal/tools/hip/build_windows.bat:76-85`）。他の記載したビルドスクリプトにはこの変数専用の cache や起動後再読込機構はありません。

configure の失敗時は各ビルド手順に従って停止します。HIP Linux は configure 出力を `$OUT/cfg.log` にリダイレクトし、終了コードを status log に記録して失敗なら終了します（`tools/packaging/build_hip_linux.sh:63-67`; `tools/packaging/build_hip_linux.sh:44-47`）。Windows HIP は CMake の失敗で `exit /b 1` します（`terminal/tools/hip/build_windows.bat:76-85`）。他の経路も `set -e` や `run()` の失敗処理で停止します（`tools/packaging/build_cuda_linux.sh:16,43-50`; `tools/packaging/build_sycl_linux.sh:18,49-51`; `tools/packaging/build_cuda_windows.py:145-148,174-177`）。

## ログと測定値

この変数自体が値や有効状態を報告するログはありません。configure が不正・不適合な引数を拒否した場合は CMake の configure 失敗として構築が止まります。HIP Linux ではその出力先は `$OUT/cfg.log` で、status に `engine configured rc=<終了コード>` または `ABORT engine configured failed (rc=<終了コード>)` を追記します（`tools/packaging/build_hip_linux.sh:44-47,63-67`）。他の固有のログ文言や実行時の結果は、渡された CMake 引数の内容に依存します。

## 根拠

- 候補名の全参照と用途: `tools/packaging/build_cuda_linux.sh:40-45`; `tools/packaging/build_sycl_linux.sh:43-50`; `tools/packaging/build_hip_linux.sh:61-65`; `tools/packaging/build_cuda_windows.py:15-16,166-174`; `tools/packaging/shape_build.sh:5-6,23-27`; `engine/spark/build_engine.sh:10,51-54`; `terminal/tools/hip/build_windows.bat:25,76-85`。
- `tools/packaging/make_model_release.py:149` と各ファイルのコメントにも名前が出ますが、前者は生成文書内の説明文字列、後者は説明コメントであり、環境からの読み取り箇所ではありません。
- `docs/DETAILS.md` は対象 checkout に存在しませんでした。対象変数について Strata が実際に環境値を読む実装は構築ラッパーの上記箇所に限られ、engine runtime / server 側の読み取りは確認されませんでした。
