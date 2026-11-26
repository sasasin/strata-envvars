# `STRATA_SYM_CMAKE`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点）。作業ツリーは `## main...origin/main`（未コミット変更なし）。

## 役割

Windows CUDA エンジンのパッケージング時に、ピクチャリーダ `strata-vision` の CMake configure に引数を渡すための内部受け渡し用環境変数である。通常の `build_cuda_windows.py` 経路では、シンボル保持が有効なら `-DSTRATA_KEEP_SYMBOLS=ON` を設定し、バッチファイルが CMake コマンドへ展開する。実行時の `strata` の環境変数ではなく、Windows のパッケージ作成用である（`tools/packaging/build_cuda_windows.py:83-85,201-204`、`tools/packaging/build_vision_windows.bat:54-57`）。

## 値と判定

Strata はこの値を真偽値として解析しない。Python スクリプトは親環境を大文字化して複製し、`STRATA_KEEP_SYMBOLS` が有効なときだけ値を `-DSTRATA_KEEP_SYMBOLS=ON` に上書きする。バッチファイルは `%STRATA_SYM_CMAKE%` を引用符なしで CMake の引数列に展開する（`tools/packaging/build_cuda_windows.py:83-85,116-130,201-204`、`tools/packaging/build_vision_windows.bat:54-57`）。

| 条件 | unset | 設定時に有効になる値 | 無効・効果なしの値 |
|---|---|---|---|
| `build_cuda_windows.py` から通常起動し、`STRATA_KEEP_SYMBOLS` が未設定または値が `0` 以外 | Python が親環境の値を `-DSTRATA_KEEP_SYMBOLS=ON` に設定する | 固定文字列 `-DSTRATA_KEEP_SYMBOLS=ON` が vision の CMake configure に渡る | 該当なし。親環境に別の値があっても Python が上書きする |
| `build_cuda_windows.py` から起動し、`STRATA_KEEP_SYMBOLS=0` | Python はこの名前を新たに設定しない。親環境にも無ければ CMake 引数は増えない | 親環境にこの名前があれば、その値が引き継がれて展開される | 未設定または空文字は実質的に引数なし。任意の文字列の CMake 上の効果は文字列次第であり、Strata は検証しない |
| `build_vision_windows.bat` を直接起動 | 展開結果は空で、追加引数なし | 設定値をそのまま CMake コマンド行へ展開 | `0`、`1`、`true` などを個別に判定しない。空文字は追加引数なし |

Python 側の `keep_symbols()` は `STRATA_KEEP_SYMBOLS` の値が文字列として厳密に `0` の場合だけ無効にし、未設定時は既定値 `1` を使う（`tools/packaging/build_cuda_windows.py:83-85`）。この判定は `STRATA_SYM_CMAKE` 自身には適用されない。大文字小文字、空白、数値妥当性、真偽語の検査もない。空白を含む任意文字列が CMake にどう分割・解釈されるかは Strata のコードで制御していない。

## 有効になる条件

- `build_cuda_windows.py` は Windows 以外では `this builds the Windows engine; on Linux use tools/packaging/build_cuda_linux.sh` で終了する。また引数は `cuda12` / `cuda13` のいずれかでなければならない（`tools/packaging/build_cuda_windows.py:158-165`）。
- この受け渡しが使われるのは、同スクリプトが Windows CUDA パッケージの vision reader 用に `build_vision_windows.bat` を呼ぶ経路である。バッチは `cuda12` / `cuda13` を選び、`terminal/tools/vision` を CUDA / Ninja で configure する（`tools/packaging/build_cuda_windows.py:191-204`、`tools/packaging/build_vision_windows.bat:26-35,54-60`）。
- 既定のシンボル保持判定は `STRATA_KEEP_SYMBOLS` が未設定なら有効、値が厳密に `0` なら無効、それ以外なら有効である。通常の有効経路では Python が `STRATA_SYM_CMAKE` を固定値で上書きする。無効経路では Python が親環境から継承した値を消さないため、親から `STRATA_SYM_CMAKE` を渡していればその値は引き続き CMake に展開される（`tools/packaging/build_cuda_windows.py:83-85,116-130,201-204`）。
- `-DSTRATA_KEEP_SYMBOLS=ON` が vision configure に渡ると、共有 CMake 設定は MSVC の C/C++ と CUDA host compile に `/Z7`、link に debug 関連フラグを追加し、`STRATA_KEEP_SYMBOLS: host debug information on (the code does not change)` を出す。これは `STRATA_SYM_CMAKE` の値を解釈する処理ではなく、渡された CMake option の処理である（`engine/cmake/strata_symbols.cmake:15-20,40`、`terminal/tools/vision/CMakeLists.txt:19`）。
- シンボル保持が有効なパッケージング経路では、vision のビルド後に Python が PDB を回収する（`tools/packaging/build_cuda_windows.py:205-207`）。`STRATA_KEEP_SYMBOLS=0` の経路ではその回収呼び出しも行わない（同 `:205`）。

## 実行時の詳細

`STRATA_SYM_CMAKE` を読むのは `build_vision_windows.bat` の CMake configure 行だけで、Strata の実行バイナリや他 backend の実行時処理には参照がない。Python の親環境から `msvc_env()` が環境を複製し、必要なら Visual Studio 環境を追記する。その環境を `venv` に複製した後、シンボル保持が有効な場合にだけ当該キーを固定値へ設定し、バッチプロセスに渡す（`tools/packaging/build_cuda_windows.py:116-130,176-181,201-204`）。

読み取りはバッチの CMake configure コマンド実行時で、Strata 側に `static` cache や独自の起動時読み取りはない。configure は `build_vision_windows.bat:54-57` で毎回実行され、失敗時はバッチが終了コード 1 を返し、親 Python の `run()` が `build_cuda_windows.py: failed: cmd /d /c` で終了する（`tools/packaging/build_vision_windows.bat:54-58`、`tools/packaging/build_cuda_windows.py:152-155,204`）。

## ログと測定値

この環境変数専用のログや警告はない。親 Python の `run()` は起動するコマンド行を `+ ` 付きで stdout に表示するため、通常の経路ではバッチ呼び出しは見えるが、環境変数の展開後の値を個別に表示する処理ではない（`tools/packaging/build_cuda_windows.py:152-155,204`）。シンボル保持が有効で CMake 設定が適用されれば、CMake 側が `STRATA_KEEP_SYMBOLS: host debug information on (the code does not change)` を出す（`engine/cmake/strata_symbols.cmake:40`）。測定値は該当なし。

## 根拠

- `tools/packaging/build_cuda_windows.py:83-85,116-130,152-155,158-165,176-181,191-207` — 有効条件、親環境の複製、値の上書き、子バッチ呼び出し、失敗処理。
- `tools/packaging/build_vision_windows.bat:26-35,48-60` — Windows CUDA variant の選択、CMake 引数への展開、configure / build の失敗終了。
- `terminal/tools/vision/CMakeLists.txt:19`、`engine/cmake/strata_symbols.cmake:15-20,40` — vision から共有設定を読み込む箇所と、渡された `STRATA_KEEP_SYMBOLS` option の処理。
- `tools/packaging/UPDATES.md:228-240` — パッケージ用シンボルファイルの扱いに関する Strata の説明。コード上の条件は上記実装を根拠とした。
