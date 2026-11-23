# `CUDA_PATH_V12_9`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Windows 向け CUDA 12.9 エンジンパッケージおよびその vision reader をビルドするときに、CUDA Toolkit のルートディレクトリを指定する変数。通常の Strata アプリ／エンジン実行時に読む箇所はなく、ビルド用 Python スクリプトとバッチスクリプトだけが参照する。エンジン生成スクリプトは選んだ Toolkit で `nvcc.exe` を検査し、そのルートを CMake に渡す。vision reader のバッチは `cuda12` variant のとき、この値で `CUDA_PATH` を設定してから `nvcc.exe` の存在を確認し、CMake に渡す（`tools/packaging/build_cuda_windows.py:96-105, 168-177`; `tools/packaging/build_vision_windows.bat:26-35, 54-60`）。

## 値と判定

| 読み取り箇所・条件 | 未設定／空文字 | 有効になる値 | 無効値・fallback |
|---|---|---|---|
| `build_cuda_windows.py` の `cuda12` variant（Windows のみ） | `os.environ.get()` が `None` または空文字ならその候補を飛ばす | `CUDA_PATH_V12_9` を先に確認し、値が指す `<値>/bin/nvcc.exe` がファイルとして存在し、そこから実行した `nvcc.exe --version` の標準出力にある `release M.m` が `12.9` と完全一致する | 値が空、`nvcc.exe` がない、version 表記が取れない、または `12.9` 以外なら次候補 `CUDA_PATH` を試す。両候補が通らなければ `build_cuda_windows.py: cuda12 needs the CUDA 12.9 toolkit (CUDA_PATH_V12_9 or CUDA_PATH)` で終了する（`tools/packaging/build_cuda_windows.py:96-106`）。 |
| `build_vision_windows.bat` の `cuda12` variant | `if defined CUDA_PATH_V12_9` が偽ならこの変数による上書きはせず、呼び出し元から継承した `CUDA_PATH` を使う | バッチが `if defined` と判定した場合、その値を無加工で `CUDA_PATH` に代入する | `cuda13` variant ではこの名前を参照せず、`CUDA_PATH_V13_0` のみを同じ形で確認する。選択後は `CUDA_PATH` が未定義ならエラー終了し、定義済みでも `%CUDA_PATH%\bin\nvcc.exe` がなければエラー終了する。バッチ内では CUDA version の文字列検査はしない（`tools/packaging/build_vision_windows.bat:26-35`）。 |

Python 側は変数値をパス文字列として扱い、空白除去や値の変換はしない。`nvcc.exe --version` の標準出力を正規表現 `release (数字.数字)` で検索して、バリアント指定の `12.9` と照合する。終了コード自体や標準エラーはこの version 判定に使わない。`CUDA_PATH_V12_9` に不適合な値があれば `CUDA_PATH` が fallback になり、CLI オプションからの Toolkit ルート上書きはない（`tools/packaging/build_cuda_windows.py:96-106, 151-170`）。ただし同じプロセスが vision バッチを起動するとき `CUDA_PATH_V12_9` も環境に残るため、値が定義済みならバッチが fallback 済みの `CUDA_PATH` を再び上書きする。このためエンジン本体と vision reader で異なる Toolkit ルートが選ばれ得る。vision reader 側はそのルートに `nvcc.exe` があれば CMake configure を試みるが、その先の結果はバッチのこのチェックだけからは確定できない（`tools/packaging/build_cuda_windows.py:111-123, 168-190`; `tools/packaging/build_vision_windows.bat:26-35`）。

## 有効になる条件

- `build_cuda_windows.py` で有効なのは Windows 上で `cuda12` を引数にして実行した場合だけ。Linux では `this builds the Windows engine; on Linux use tools/packaging/build_cuda_linux.sh` で失敗し、`cuda13` では `CUDA_PATH_V13_0` を検索するため本変数は使わない（`tools/packaging/build_cuda_windows.py:37-42, 96-105, 151-158`）。
- Python スクリプトでは、この変数のパスに `bin/nvcc.exe` があり、その実行出力から CUDA `12.9` を確認できる必要がある。満たさなければ `CUDA_PATH` に進み、そちらも不適合ならビルドを中止する（`tools/packaging/build_cuda_windows.py:96-106`）。
- ビジョン reader のバッチは `cuda12` を選んだときだけ本変数で `CUDA_PATH` を上書きする。直接バッチを呼ぶ場合は CUDA の版を照合せず、`nvcc.exe` の存在確認まで進む。通常の Python パッケージ生成経路でも `CUDA_PATH_V12_9` は子プロセスに継承される。親スクリプトが本変数を採用した場合は検証済みの同じルートになるが、本変数が不適合で `CUDA_PATH` に fallback した場合でもバッチは本変数を優先し直す（`tools/packaging/build_cuda_windows.py:111-123, 168-190`; `tools/packaging/build_vision_windows.bat:26-35`）。
- CMake／Ninja／Visual Studio の存在やビルド成功も後続処理の条件だが、本変数がそれらを設定・検出するわけではない。バッチは `nvcc.exe` 検査後に `cl.exe`、CMake configure、ビルド、コピー、パッケージへの stamp を順に行い、各失敗で非ゼロ終了する（`tools/packaging/build_vision_windows.bat:34-60`）。

## 実行時の詳細

Python の `find_cuda("cuda12")` はビルドスクリプト実行中に一度、`CUDA_PATH_V12_9`、次に `CUDA_PATH` の順に `os.environ.get()` で読み、適合した最初のルートを返す。スクリプトはそのルートを子プロセス環境の `CUDA_PATH` に設定し、CMake configure にも `CMAKE_CUDA_COMPILER=<root>/bin/nvcc.exe` と `CUDAToolkit_ROOT=<root>` を渡す。続いて vision バッチを同じ環境から起動する（`tools/packaging/build_cuda_windows.py:96-106, 168-177, 189-190`; `tools/packaging/build_cuda_windows.py:68-78`）。

バッチを単独起動した場合は、冒頭で `VARIANT` を選んだ後に `CUDA_PATH_V12_9` を読み、`cuda12` のときだけ `CUDA_PATH` に代入する。どちらもビルドプロセス中に読む値であり、関数内 cache や常駐プロセスの設定ではない。子プロセス起動後に親環境を変更しても、起動済みプロセスへは反映されない。通常のモデルロード、推論、サーバーモードには適用されない。

## ログと測定値

- Python の有効値について専用ログは出さない。Toolkit が両候補とも見つからない場合は上記の `build_cuda_windows.py: ... needs the CUDA 12.9 toolkit ...` を例外ではなく `SystemExit` のメッセージとして出して終了する（`tools/packaging/build_cuda_windows.py:48-49, 96-106`）。
- バッチは未設定時に `CUDA_PATH is not set: install the %VARIANT% toolkit`、`nvcc.exe` 不在時に `no nvcc.exe in %CUDA_PATH%\bin` を表示して `exit /b 1`。CMake configure／build、コピー、stamp が失敗した場合もそれぞれ非ゼロ終了する。成功時は `built: <stage>\strata-vision.exe (<variant>, archs <archs>)` を表示する（`tools/packaging/build_vision_windows.bat:34-35, 54-61`）。
- この変数による実行時ログや性能測定値は該当しない。

## 根拠

- `tools/packaging/build_cuda_windows.py:96-106` — variant に応じた環境変数名の動的生成、候補順、パス・CUDA 版の検査、失敗メッセージ。
- `tools/packaging/build_cuda_windows.py:151-177, 189-190` — Windows 限定、variant 選択、選択値を `CUDA_PATH` として CMake／vision 子プロセスへ渡す流れ。
- `tools/packaging/build_vision_windows.bat:26-35, 54-60` — `cuda12` の読み取りと上書き、後続のパス検査、CMake／ビルド／出力。

