# `CUDA_PATH_V13_0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Windows 向け CUDA 13 engine パッケージのビルド時に、CUDA 13.0 Toolkit のルートディレクトリを示す変数です。Strata の通常実行時に読む設定ではなく、同梱の packaging スクリプト `tools/packaging/build_cuda_windows.py` と、同スクリプトから呼ばれる `tools/packaging/build_vision_windows.bat` が読みます。engine ビルド用の Python スクリプトは候補ルートの存在と `nvcc --version` のリリース文字列を確認し、選んだルートを子プロセス用 `CUDA_PATH` として設定します。vision reader 用バッチは `cuda13` variant のとき、この変数が定義されていれば `CUDA_PATH` をその値で上書きして CMake に渡します（`tools/packaging/build_cuda_windows.py:96-105,151-174`、`tools/packaging/build_vision_windows.bat:26-35,54-58`）。

## 値と判定

| 読み取り経路 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `build_cuda_windows.py cuda13` | Python 側は空文字を未指定相当として次候補 `CUDA_PATH` へ進む。`CUDA_PATH` も使えなければ終了する。 | `CUDA_PATH_V13_0` が指すディレクトリに `bin/nvcc.exe` があり、その実行結果の stdout にある `release X.Y` が `release 13.0` と完全一致する場合。 | `true`、`1` などの文字列自体を真偽値としては解釈しない。パスが存在しない、`nvcc.exe` がない、出力からリリース番号を抽出できない、または番号が `13.0` 以外なら候補として不採用。空白や大文字小文字の正規化は行わない。 |
| `build_vision_windows.bat cuda13 <stage>` | `if defined` は偽となり、既存の `CUDA_PATH` をそのまま使う。両方未定義ならエラー終了。 | 空でない値は文字列をそのまま `CUDA_PATH` に代入。さらに `%CUDA_PATH%\bin\nvcc.exe` が存在すれば CMake 引数へ渡す。 | `0`、`false` なども空でなければ定義済みとして扱い、パスとして検査する。指定パスに `bin\nvcc.exe` がなければエラー終了。空白や CUDA バージョンの検証はしない。 |

Python 側の検索順は `CUDA_PATH_V13_0`、次に `CUDA_PATH` です。候補ごとに `os.environ.get` で取得し、空でない値だけを検査します。パスの存在確認は `bin/nvcc.exe` に対して行い、`nvcc.exe --version` の stdout から正規表現 `release (\d+\.\d+)` で最初に一致した版を取り出し、`13.0` と比較します。数値や真偽値としての parse、パス文字列の trim はありません（`tools/packaging/build_cuda_windows.py:96-106`）。

バッチ側では `cuda13` の分岐内の `if defined CUDA_PATH_V13_0` が定義有無だけを調べ、非空値なら `CUDA_PATH` に代入します。CLI variant が `cuda12` の場合はこの変数を参照しません（`tools/packaging/build_vision_windows.bat:26-32`）。

## 有効になる条件

- Python 経路では Windows 上で `build_cuda_windows.py cuda13` を実行する必要があります。別 OS では variant 処理より先に Windows 専用エラーで終了します（`tools/packaging/build_cuda_windows.py:151-168`）。
- versioned path が適格であるには `bin/nvcc.exe` がファイルとして存在し、その stdout に `release 13.0` が必要です。適格でない場合は次の `CUDA_PATH` 候補が検査されます（`tools/packaging/build_cuda_windows.py:96-105`）。
- vision reader のバッチでは `cuda13` variant が必要です。`CUDA_PATH_V13_0` が空でなく定義されていれば、Python 経路が選んで `CUDA_PATH` に設定した値よりもバッチ側の値が優先されます。このバッチ内では版番号を確認せず、`bin\nvcc.exe` の存在だけを検査します（`tools/packaging/build_cuda_windows.py:168-174,189-190`、`tools/packaging/build_vision_windows.bat:29-35`）。
- バッチを直接呼び出す場合、`CUDA_PATH_V13_0` が未設定なら既存の `CUDA_PATH` が必要です。どちらも有効な `nvcc.exe` を指さない場合は CMake 前に失敗します（`tools/packaging/build_vision_windows.bat:31-35`）。
- Python 経路で `CUDA_PATH_V13_0` と `CUDA_PATH` の両方が適格なら、前者が選ばれます。vision バッチで前者が定義済みの場合も前者が `CUDA_PATH` を上書きします。CLI 引数は variant を選び、パス候補の順序を変更します（`tools/packaging/build_cuda_windows.py:96-105,151-169`）。

## 実行時の詳細

Python スクリプトは `find_cuda(variant)` の呼び出し時に環境を読みます。設定値をモジュールや関数内の cache に保存する実装ではありません。選んだ CUDA root は `env["CUDA_PATH"]` に設定され、PATH にもその `bin` が前置されます。続く engine の CMake 設定には同じ root が `CMAKE_CUDA_COMPILER` と `CUDAToolkit_ROOT` として渡されます（`tools/packaging/build_cuda_windows.py:96-106,167-175`）。

その後、ステージングディレクトリと `VISION_BUILD_DIR` 等を含む環境で vision バッチを起動します。ここで `CUDA_PATH_V13_0` が定義されていると、Python が版検査後に選択した `CUDA_PATH` をバッチが再度上書きするため、engine と vision reader が異なる Toolkit root でビルドされる場合があります。バッチは上書き後の root を使って `nvcc.exe` の存在を確認し、CMake に compiler と toolkit root を渡します（`tools/packaging/build_cuda_windows.py:168-190`、`tools/packaging/build_vision_windows.bat:29-35,54-58`）。このバッチ経路では Toolkit の版一致は検査されません。

バッチで `CUDA_PATH` が未定義なら `CUDA_PATH is not set: install the cuda13 toolkit` を表示して終了コード 1、`nvcc.exe` がなければ `no nvcc.exe in <パス>\bin` を表示して終了コード 1 です。CMake configure、build、copy、package stamp の失敗も `|| exit /b 1` で終了します（`tools/packaging/build_vision_windows.bat:34-35,54-60`）。変数値そのものを表示する成功ログはこのバッチにありません。

## 根拠

- `tools/packaging/build_cuda_windows.py:96-106` — versioned 変数名を含む候補順、空値の扱い、`nvcc.exe` と CUDA 版の検査、候補不適格時の失敗。
- `tools/packaging/build_cuda_windows.py:151-175,189-190` — Windows/variant 条件、選択 root の子プロセス環境への設定、vision バッチ呼び出し。
- `tools/packaging/build_vision_windows.bat:26-35` — variant ごとの分岐、対象変数による `CUDA_PATH` 上書き、および未設定・ファイル不在時のエラー。
- `tools/packaging/build_vision_windows.bat:54-60` — `CUDA_PATH` を CMake に渡し、後続の build / copy / stamp 失敗で終了する処理。
