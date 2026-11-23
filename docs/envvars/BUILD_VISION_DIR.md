# `BUILD_VISION_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 向けビルドスクリプトが Strata の画像 reader `strata-vision` を構成・ビルドする build directory を指定する。推論時の環境変数ではなく、ビルドツール専用である。Linux x86_64 では `BUILD_VISION=1` のとき、DGX Spark 用 Linux arm64 でも同じ条件のときに使用する。Windows CUDA package では reader のビルドに常に使用する。各経路とも engine 本体の build directory（`BUILD`）や出力先（`OUT`）とは別である（`tools/packaging/build_cuda_linux.sh:26-27,54-60`、`tools/packaging/build_cuda_windows.py:162-164,189-190`、`engine/spark/build_engine.sh:20-23,67-73`）。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux x86_64 CUDA (`tools/packaging/build_cuda_linux.sh`) | 未設定または空文字なら `$repo/build-vision-$variant` | 空でない値をそのまま `cmake -B` に渡す。例: `/tmp/vision-cuda13`、`build/vision` | 値による有効・無効の判定はない。`0`、`false`、空白だけの値も非空のディレクトリ名として扱われる |
| Linux arm64 CUDA / DGX Spark (`engine/spark/build_engine.sh`) | 未設定または空文字なら `$repo/build-vision-spark` | 空でない値をそのまま `cmake -B` に渡す。例: `/tmp/vision-spark`、`build/vision` | 値による有効・無効の判定はない。`0`、`false`、空白だけの値も非空のディレクトリ名として扱われる |
| Windows x86_64 CUDA (`tools/packaging/build_cuda_windows.py`) | 未設定または空文字なら `<repo>/build-vision-<variant>-win` | 空でない値から `Path` を作り、reader build directory としてバッチに渡す。例: `C:\tmp\vision`、`build\vision` | 値による有効・無効の判定はない。`0`、`false`、空白だけの値も非空のパスとして扱われる |

Linux shell の `${BUILD_VISION_DIR:-default}` と Windows Python の `os.environ.get(...) or default` はどちらも未設定と空文字を既定値に置き換える。`BUILD_VISION_DIR` 自体の文字列を数値・真偽値として parse せず、trim、存在確認、正規化もしない。相対パスを含め、決まった値は reader の CMake `-B` 引数へ渡される。Windows では Python から `VISION_BUILD_DIR` という別名で子の `.bat` に渡す。CLI 引数による上書きはない（`tools/packaging/build_cuda_linux.sh:54-59`、`tools/packaging/build_cuda_windows.py:163,189-190`、`tools/packaging/build_vision_windows.bat:37,54-59`、`engine/spark/build_engine.sh:22,67-73`）。

## 有効になる条件

- Linux x86_64 の CUDA packaging script は `VARIANT=cuda12` または `cuda13` を使い、`BUILD_VISION` が文字列 `1` の場合に reader を構成・ビルドする。`BUILD_VISION` は未設定なら `1`。`0`、空文字、`true` などは条件を満たさない（`tools/packaging/build_cuda_linux.sh:17-24,54-60`）。
- DGX Spark 用 script は Linux arm64 で CUDA 13 toolkit を必要とし、CUDA version の検査を通過した後、`BUILD_VISION` が文字列 `1` の場合に reader を構成・ビルドする。未設定時は `1`（`engine/spark/build_engine.sh:29-45,67-73`）。
- Windows の reader build は `build_cuda_windows.py` の `cuda12` / `cuda13` 引数と Windows (`os.name == "nt"`) の条件を通った後に実行される。`BUILD_VISION` による gate はなく、`BUILD_VISION_DIR` は reader directory だけを選ぶ（`tools/packaging/build_cuda_windows.py:151-168,189-190`）。
- Linux x86_64 と Spark のどちらも reader は `terminal/tools/vision` から `STRATA_VISION_CUDA=ON` で構成される。engine の variant / architecture に合わせた CUDA architecture list も渡される（`tools/packaging/build_cuda_linux.sh:35-45,57-59`、`engine/spark/build_engine.sh:48-54,67-72`）。
- Linux x86_64 では `BUILD_VISION` が `1` でなくても `vision_dir` は後段で参照され、そこに既存の `bin/strata-vision` があれば stage にコピーされる。したがって「reader をビルドしない」場合でも、選んだ directory に既存ファイルがあると package に含まれ得る（`tools/packaging/build_cuda_linux.sh:54-60,67-72`）。Spark はコピー時にも `BUILD_VISION=1` を条件にする（`engine/spark/build_engine.sh:80-87`）。

## 実行時の詳細

この変数を読むのはスクリプトの実行時で、3経路とも値をローカル変数に一度取り込む。プロセス起動後に親環境を変更して反映させる読み取りや、Strata engine による runtime lookup はない。Linux x86_64 では script が repo に `cd` した後にこの値を CMake に渡すため、相対指定はその作業ディレクトリから解釈される。Spark でも repo に `cd` した後に使う。Windows script は repo へ `chdir` せず、値を `Path` にした後、子の batch に `VISION_BUILD_DIR` として渡す（`tools/packaging/build_cuda_linux.sh:37,54-59`、`tools/packaging/build_cuda_windows.py:34-36,163,189-190`、`tools/packaging/build_vision_windows.bat:37,54-59`、`engine/spark/build_engine.sh:18,22,50,67-73`）。

指定 directory は CMake configure と `strata-vision` target の build に使われ、生成された `bin/strata-vision`（Windows は `bin\strata-vision.exe`）を package stage または Spark の出力先へコピーする。script 自身は指定先を消去・初期化せず、既存 build directory を CMake に渡す。別の環境変数や CLI が `BUILD_VISION_DIR` の値を上書きする処理はない。なお reader build の有無を決める別変数 `BUILD_VISION` が Linux 2経路にある（上記条件参照）。

## ログと測定値

成功時の最終表示は Linux x86_64 で `built: $out`、Spark で `built: $out`、Windows で `built: <folder>`。この表示は選択した `BUILD_VISION_DIR` 自体を報告しない（`tools/packaging/build_cuda_linux.sh:81-82`、`engine/spark/build_engine.sh:88-89`、`tools/packaging/build_cuda_windows.py:200-204`）。Linux shell は `set -e` のため CMake configure/build が失敗するとその場で終了する。Windows batch は CMake configure/build や reader copy の失敗時に errorlevel 1 で終了し、Python 側の `run` がコマンドを表示した後 `build_cuda_windows.py: failed: cmd /d /c ...` の形式で終了する（`tools/packaging/build_cuda_linux.sh:16,57-60`、`engine/spark/build_engine.sh:17,69-73`、`tools/packaging/build_vision_windows.bat:54-60`、`tools/packaging/build_cuda_windows.py:145-148,189-190`）。この変数について Strata の資料に記載された測定値はない。

## 根拠

- Linux x86_64 CUDA packaging: `tools/packaging/build_cuda_linux.sh:52-72`
- Windows CUDA packaging と値の転送: `tools/packaging/build_cuda_windows.py:151-190`、`tools/packaging/build_vision_windows.bat:16-19,33-60`
- DGX Spark arm64 CUDA build: `engine/spark/build_engine.sh:17-27,67-89`
- 包装される reader の構成条件との照合: `tools/packaging/ENGINE-COMPONENT.md:106-111`、`docs/DGX_SPARK_LINUX.md:63-64`、`docs/DOCKER.md:397`
