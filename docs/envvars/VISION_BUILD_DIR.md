# `VISION_BUILD_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows CUDA packaging の vision reader ビルド用ディレクトリを指定する環境変数です。`tools/packaging/build_vision_windows.bat` がこの値を CMake の `-B`、ビルド先、および生成された `strata-vision.exe` のコピー元に使います（`tools/packaging/build_vision_windows.bat:37,54-59`）。通常の engine build directory や package 出力先は指定しません。

このバッチを `tools/packaging/build_cuda_windows.py` 経由で実行すると、親プロセスの `VISION_BUILD_DIR` はそのまま使われません。Python 側は別変数 `BUILD_VISION_DIR` から directory を選び、その値で子環境の `VISION_BUILD_DIR` を常に設定します（`tools/packaging/build_cuda_windows.py:161-165,189-190`）。

## 値と判定

| 経路 | unset / 空文字 | 設定値の扱い | 無効値・境界 |
|---|---|---|---|
| `build_vision_windows.bat` を直接実行 | unset または空文字なら `%SRC%\build-vision-%VARIANT%-win` | 空でない文字列をパスとしてそのまま引用し、CMake `-B`、build、copy に使う | 真偽値や数値への parse、trim、存在確認による値の検証はない。`0`、`false`、空白だけも空でない値として使われる（`tools/packaging/build_vision_windows.bat:25,37,54-59`）。 |
| `build_cuda_windows.py` が起動する子バッチ | 子環境では Python が必ず値を設定する | Python は `BUILD_VISION_DIR` の未設定・空文字を variant 別 default に置き換えて `Path` 化し、文字列化して `VISION_BUILD_DIR` に設定する | 親の `VISION_BUILD_DIR` は採用されず、子環境で上書きされる。`BUILD_VISION_DIR=0` や `false` は非空なのでパスとして使われる（`tools/packaging/build_cuda_windows.py:162-163,189-190`）。 |

バッチでの「設定あり」は `if not defined` 判定なので、環境変数が未設定か空文字なら default を選びます。空白は空文字ではなく値として扱われます。値全体を boolean / 数値として解釈する処理はありません（`tools/packaging/build_vision_windows.bat:37`）。

## 有効になる条件

- 直接使う場合は Windows の `cmd` から `tools/packaging/build_vision_windows.bat <cuda12|cuda13> <stage>` を実行する経路です。指定値はバッチの reader build に使われます（`tools/packaging/build_vision_windows.bat:4-5,20-25,54-59`）。
- Python packaging wrapper 経由では Windows (`os.name == "nt"`) かつ `cuda12` / `cuda13` variant が必要です。wrapper は `BUILD_VISION_DIR` を入力にし、`VISION_BUILD_DIR` を子プロセスへ設定します（`tools/packaging/build_cuda_windows.py:151-163,189-190`）。
- バッチは variant に応じた CUDA Toolkit と `nvcc.exe`、CMake、Ninja、`cl.exe` も要求します。これらの条件を満たさない場合は directory 指定値に関係なく先に終了します（`tools/packaging/build_vision_windows.bat:26-46`）。
- Linux の `tools/packaging/build_cuda_linux.sh` と `engine/spark/build_engine.sh` は別名 `BUILD_VISION_DIR` を読みます。Linux packaging ではさらに `BUILD_VISION=1` が reader build の条件です。これらの経路は `VISION_BUILD_DIR` を読みません（`tools/packaging/build_cuda_linux.sh:52-60`、`engine/spark/build_engine.sh:18-22`）。

## 実行時の詳細

バッチは実行時に環境変数を参照します。バッチを直接呼び出した場合、`VISION_BUILD_DIR` が空でなければその値を使い、空または未設定ならソース checkout 直下の variant 別 `build-vision-<variant>-win` を使います。読み取った場所に対する設定の cache はありません（`tools/packaging/build_vision_windows.bat:25,37,54-59`）。

Python wrapper では `BUILD_VISION_DIR` を `os.environ.get(...) or default` で一度取得し、選択した directory を子バッチの環境変数 `VISION_BUILD_DIR` に設定して起動します。wrapper の CLI 引数には vision build directory の指定はなく、wrapper 実行時に親の `VISION_BUILD_DIR` を変更しても反映されません。親側で指定するには `BUILD_VISION_DIR` を使います（`tools/packaging/build_cuda_windows.py:151-165,189-190`）。

有効値は CMake configure の `-B`、`cmake --build`、`strata-vision.exe` のコピー元に順に使われます。directory の存在・作成や CMake の処理はこの変数の値判定とは別です。CMake configure/build、copy、package stamp が失敗するとバッチは `exit /b 1` します（`tools/packaging/build_vision_windows.bat:38,54-60`）。

## ログと測定値

成功時、バッチは `built: <stage>\strata-vision.exe  (<variant>, archs <ARCHS>)` を表示します。reader build directory 自体を表示するログはありません。CUDA Toolkit が未設定なら `CUDA_PATH is not set: install the <variant> toolkit`、`nvcc.exe` がなければ `no nvcc.exe in <CUDA_PATH>\bin`、`cl.exe` がなければ `cl.exe not found: run this from an x64 Native Tools prompt` を出して終了コード 1 です。引数不足・variant 不正は usage を表示して終了コード 2 です（`tools/packaging/build_vision_windows.bat:23-35,40-46,60-65`）。測定値の記載はありません。

## 根拠

- `tools/packaging/build_vision_windows.bat:25-37,54-65` — 直接の環境変数判定、既定 directory、CMake/build/copy、失敗・成功ログ。
- `tools/packaging/build_cuda_windows.py:151-165,189-190` — Windows/variant 条件、別名 `BUILD_VISION_DIR` の fallback と子環境への転送・上書き。
- `tools/packaging/build_cuda_linux.sh:52-60`、`engine/spark/build_engine.sh:18-22` — Linux 経路が `BUILD_VISION_DIR` を使うこと、および Linux packaging の `BUILD_VISION` 条件。
