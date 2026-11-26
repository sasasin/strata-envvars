# `VISION_BUILD_DIR`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

Windows CUDA engine package 用の `strata-vision.exe` をビルドする作業ディレクトリを指定する。`tools/packaging/build_vision_windows.bat` が CMake の build directory として使い、生成物をそこから stage folder へコピーする。Strata の通常実行時の vision 動作を切り替える変数ではない（`tools/packaging/build_vision_windows.bat:2-19,37,54-60`）。

バッチを直接起動する場合は、非空の値が build directory になる。CUDA Windows package driver の `tools/packaging/build_cuda_windows.py` 経由では、driver が `VISION_BUILD_DIR` を子プロセス環境へ設定して呼び出すため、呼び出し元から継承した値はこの値に置き換わる（`tools/packaging/build_cuda_windows.py:168-172,191-207`）。

## 値と判定

バッチは `if not defined VISION_BUILD_DIR` で有無だけを判定する。整数や真偽値への変換、文字列内容の検証、境界値判定はない。未設定と空文字は同じく未定義として扱われ、`%SRC%\build-vision-%VARIANT%-win` が設定される。非空ならその文字列をそのまま引用符で囲んで CMake に渡す。空白を含む path も一つの引数として渡る。`VARIANT` は先行処理で `cuda12` / `cuda13` に限定される（`tools/packaging/build_vision_windows.bat:21-37,54-58,64-65`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| バッチを直接起動（`cuda12` または `cuda13`） | variant に応じて `%SRC%\build-vision-cuda12-win` または `%SRC%\build-vision-cuda13-win` | `C:\work\vision build` のような任意の非空パス文字列 | 値の形式を使った無効判定はない。空文字は unset と同じ扱い |
| `build_cuda_windows.py` 経由 | driver が `vision_dir` を設定するため unset 状態では呼ばれない | `BUILD_VISION_DIR` の値、または driver の既定 `REPO/build-vision-<variant>-win` | この変数自体の無効値判定はない。空の `BUILD_VISION_DIR` は Python 側で既定値へ fallback |

## 有効になる条件

- Windows CUDA packaging の `tools/packaging/build_vision_windows.bat` が実行されること。Linux 向けや通常の Strata engine 実行時にはこの変数の参照はない（`tools/packaging/build_vision_windows.bat:2-19`）。
- バッチ引数の variant が `cuda12` または `cuda13` で、stage folder が指定されていること。満たさない場合は usage を出して終了コード 2（`tools/packaging/build_vision_windows.bat:21-32,64-66`）。
- CUDA toolkit の `nvcc.exe` と MSVC `cl.exe` が利用可能であること。CUDA_PATH が未設定なら `CUDA_PATH is not set: install the %VARIANT% toolkit`、nvcc がなければ `no nvcc.exe in ...`、cl がなければ `cl.exe not found: run this from an x64 Native Tools prompt` を出して終了コード 1（`tools/packaging/build_vision_windows.bat:26-35,40-46`）。
- 通常の `build_cuda_windows.py` 経由では driver が `VISION_BUILD_DIR` と `VISION_ARCHS` を設定してバッチを起動する。ここでは外部から渡した `VISION_BUILD_DIR` は採用されず、Python 側の `BUILD_VISION_DIR`（空なら variant 別既定値）に従う（`tools/packaging/build_cuda_windows.py:168-172,191-204`）。

## 実行時の詳細

バッチは `setlocal` の後、引数から variant と stage folder を得る。`VISION_BUILD_DIR` が未定義または空なら variant を含む build directory を設定する。その値を `cmake -B` に渡して Release 構成を行い、同じディレクトリで `strata-vision` target を build する。続いて `<VISION_BUILD_DIR>\bin\strata-vision.exe` を stage folder の `strata-vision.exe` へコピーし、`package_engine.py --stamp-vision` を実行して vision architecture 情報を記録する（`tools/packaging/build_vision_windows.bat:20-38,48-61`）。

この値はバッチ内で各処理のたびに参照され、バッチ実行中に環境を外から変更して再評価する仕組みや cache はない。通常の Python driver は `venv` 辞書を作って `run(..., venv)` に渡す時点で値を固定する（`tools/packaging/build_cuda_windows.py:201-204`）。CLI 引数との優先順位はなく、直接バッチを起動したときは環境値が使われ、Python driver 経由では driver が環境値を上書きする。build directory の作成・有効性検査は CMake に委ねられ、Strata バッチは独自の path 正規化や事前検査をしない。

CMake configure、build、copy、または stamp の各コマンドが失敗すると、各 `|| exit /b 1` によりバッチは終了コード 1 で止まり、それ以降の工程は実行されない（`tools/packaging/build_vision_windows.bat:54-60`）。成功時は `built: <stage>\strata-vision.exe  (<variant>, archs <archs>)` を表示する（同:61）。変数値そのものについての Strata 独自ログや警告はない。

## 根拠

- `tools/packaging/build_vision_windows.bat:16-19` — Windows CUDA vision packaging 用設定としての記載。
- `tools/packaging/build_vision_windows.bat:21-37` — variant 判定、未設定値の既定 directory、CUDA 条件。
- `tools/packaging/build_vision_windows.bat:54-61` — CMake configure/build、stage への copy、stamp、失敗時の終了。
- `tools/packaging/build_cuda_windows.py:168-172,191-207` — Python driver の build directory 既定値、環境上書き、バッチ呼び出し。
- `tools/packaging/README.md:25-31` — Windows CUDA engine package recipe が `cuda12` / `cuda13` であること。
