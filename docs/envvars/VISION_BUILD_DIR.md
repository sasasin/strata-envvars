# `VISION_BUILD_DIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`VISION_BUILD_DIR` は Windows CUDA エンジンのパッケージ作成経路にあるビルド用環境変数で、画像 reader `strata-vision` の CMake build directory を指定する。`packaging/build_vision_windows.bat` を直接実行する場合はこの変数が使われる。一方、上位の `packaging/build_cuda_windows.py` は `VISION_BUILD_DIR` を入力として読まず、独自に `BUILD_VISION_DIR` から reader のビルド先を決めて、子のバッチへ `VISION_BUILD_DIR` として渡す。そのため通常の Python ラッパー経由では、呼び出し元が設定した `VISION_BUILD_DIR` は `BUILD_VISION_DIR` の指定（または既定値）で上書きされる。エンジン実行時の設定ではない。`packaging/build_cuda_windows.py:150-164,188-189`、`packaging/build_vision_windows.bat:16,43,60-66`

## 値と判定

| 経路 | unset / 空文字 | 設定時に使われる値 | 無効値・境界 |
|---|---|---|---|
| `build_vision_windows.bat` の直接実行 | `if not defined` により `%SRC%\build-vision-%VARIANT%-win` を設定する | 変数の文字列をそのまま CMake の `-B` 引数、`cmake --build` の build path、reader 実行ファイルのコピー元に使う | 値の数値変換・形式検証・範囲検証はない。文字列が空なら既定値経路になる。 |
| `build_cuda_windows.py` 経由 | Python が `BUILD_VISION_DIR` を未設定または空文字と判定すると `<repo>\build-vision-<variant>-win` を採用し、その値を子環境の `VISION_BUILD_DIR` に設定する | `BUILD_VISION_DIR` の値を `VISION_BUILD_DIR` として子バッチに渡す | 呼び出し元の `VISION_BUILD_DIR` は `dict(env, VISION_BUILD_DIR=...)` で常に置換される。 |

この値はパス文字列であり、`VISION_BUILD_DIR` 自体を parse する処理はない。バッチでは環境変数の有無を `if not defined VISION_BUILD_DIR` で調べ、値があればそのまま引用符付きのパス引数に展開する。Python ラッパーでは `os.environ.get("BUILD_VISION_DIR") or ...` が使われるため、空文字も未設定と同じ既定値になる。`packaging/build_vision_windows.bat:43,60,64-65`、`packaging/build_cuda_windows.py:161-164,188`

## 有効になる条件

- 直接実行の場合、対象は Windows CUDA reader build バッチで、`cuda12` または `cuda13` と stage directory の引数が必要。別 variant / 引数不足は `usage` に進み終了コード 2 となる。`packaging/build_vision_windows.bat:21-32,70-72`
- Python ラッパー経由の場合は Windows 上での CUDA engine package build である必要がある。非 Windows では `this builds the Windows engine; on Linux use packaging/build_cuda_linux.sh` を出して終了する。variant も `cuda12` / `cuda13` のみ。`packaging/build_cuda_windows.py:150-156`
- バッチは CUDA toolkit の `nvcc.exe`、C++ compiler `cl.exe`、CMake、Ninja などが必要。これらの前提を満たさない場合、バッチはエラーを出して失敗する。環境変数のパス指定だけでは依存条件を補わない。`packaging/build_vision_windows.bat:26-52,60-66`
- `VISION_BUILD_DIR` は build directory の選択だけを変える。CUDA variant、architecture、stage directory は別の引数・環境変数で決まり、ここから変更されない。`packaging/build_vision_windows.bat:21-33,54-66`

## 実行時の詳細

バッチは起動したプロセスの環境から `VISION_BUILD_DIR` を参照し、未定義なら variant ごとの既定パスを設定する。その後同じ値を CMake configure の `-B`、build コマンド、`%VISION_BUILD_DIR%\bin\strata-vision.exe` のコピー元に使用する。独自の値キャッシュ、再読込、CLI による優先指定はない。プロセス起動後の親環境の変更を反映する処理もない。`packaging/build_vision_windows.bat:20-25,43,60-66`

Python ラッパーは `BUILD_VISION_DIR` からパスを選び、MSVC 環境を含む子プロセス環境の `VISION_BUILD_DIR` として明示的に設定してバッチを起動する。従ってラッパー経由では、環境変数 `VISION_BUILD_DIR` の呼び出し元設定は使用されない。選択したディレクトリでの reader build 後、生成物を stage へコピーし、その stage をパッケージ処理に渡す。`packaging/build_cuda_windows.py:108-124,161-164,168-189,192-196`

## ログと測定値

バッチが成功すると `built: <stage>\strata-vision.exe  (<variant>, archs <archs>)` を表示する。CMake、build、copy、stamp 処理の失敗はそれぞれ `|| exit /b 1` でバッチを失敗させる。Python ラッパーは実行コマンドを `+ ...` として表示し、子コマンドが非ゼロ終了すると `build_cuda_windows.py: failed: cmd /d /c` をエラーとして終了する。`VISION_BUILD_DIR` 固有の警告・失敗メッセージや測定値は見つからない。`packaging/build_vision_windows.bat:60-68`、`packaging/build_cuda_windows.py:144-147,188-189`

## 根拠

- `packaging/build_vision_windows.bat:16,43,60-66` — 変数の既定値、CMake build directory と生成物コピー先。
- `packaging/build_cuda_windows.py:150-164,188-189` — Windows / variant 条件、`BUILD_VISION_DIR` の読み取りと子環境への `VISION_BUILD_DIR` 設定。
- `packaging/build_cuda_windows.py:108-124,144-147` — 子環境の作成元と subprocess の失敗処理。
