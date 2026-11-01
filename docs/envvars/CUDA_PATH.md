# `CUDA_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。外部ライブラリや GPU driver が読む動作は対象外です。

## 役割

Strata 自身が `CUDA_PATH` を読むのは、CUDA Toolkit の `nvcc` を探すソースビルド/setup と、Windows 向け engine package の不足 DLL を探す処理です。Strata engine/server の通常実行時にこの変数を読んで CUDA runtime の場所を選ぶ実装は、候補名の全参照検索では見つかりませんでした。

`CUDA_PATH` は候補一覧（`docs/envvars/000_envvers.md:88`）にはあります。ソース上の実読取箇所は `setup.py` と `packaging/package_engine.py` です。Windows の vision build script も値を検査して CMake に渡します。Nix shell は値を export するだけです。

## 値と判定

| 読取箇所 | 未設定・空文字 | 設定時の扱い |
|---|---|---|
| `setup.py` の `find_nvcc()` | `CUDA_PATH` 由来の候補を追加しない | 空でない値を Toolkit root として扱い、`<値>/bin/nvcc.exe`（Windows）または `<値>/bin/nvcc`（それ以外）を候補に加える。ディレクトリ自体の検査や文字列変換は先にせず、候補ファイルが存在するとき `--version` を実行して `release M.m` を探す。 |
| `packaging/package_engine.py` の `_default_search()` | root の候補を加えない | Windows target で空でない値なら `<値>/bin/x64` と `<値>/bin` を検索ディレクトリに加える。存在するディレクトリだけが残る。 |
| `packaging/build_vision_windows.bat` | `CUDA_PATH` が未定義ならエラー終了 | 変数が定義済みでも `<値>\bin\nvcc.exe` がなければエラー終了。 |

この実装は数値として `CUDA_PATH` を parse せず、値に対する clamp もありません。setup の候補探索では値が指すパスが存在しない場合、その候補は飛ばされます。Windows batch の `if defined` は空文字を未定義相当に扱います（`packaging/build_vision_windows.bat:28-35`）。

## 優先順位と有効になる条件

- `setup.py:2215-2234` の `find_nvcc()` は、まず空でない `STRATA_NVCC` を検査します。そのファイルが存在すれば基本的にその compiler だけを使い、`CUDA_PATH` を含む通常探索へは進みません。指定ファイルが無ければ警告を出して通常探索へ進みます。指定 compiler の version が読み取れない場合は `(None, None)` を返し、通常探索へは進みません。`below` 制約があるのに指定 compiler が制約以上の version なら警告して `(None, None)` を返します。
- 通常探索では `PATH` 上の `nvcc`、`CUDA_PATH`、`CUDA_HOME`、さらに OS ごとの既定 Toolkit ディレクトリを候補にします。重複候補を除き、存在する候補の `--version` 出力から version が取れ、かつ `below` 制約を満たすもののうち最も新しいものを選びます。したがって候補順で `CUDA_PATH` が `PATH` より優先されるわけではありません。`CUDA_HOME` も同じ探索に参加します。
- `find_nvcc()` は Windows 判定（`WIN = os.name == "nt"`）に応じて compiler のファイル名を変えます（`setup.py:91,2215-2249`）。CUDA Toolkit が必要なローカル engine build では `install_build_tools()` から呼び出され、CUDA 12 build では CUDA 13 未満の条件が付く場合があります（`setup.py:5660-5677,5934-5949`）。画像生成の CUDA backend を新規 build するときも呼び出されます（`setup.py:5004-5031,5095`）。ready-made engine の通常利用時にこの検索が常に行われるわけではありません。
- Windows packaging では `--search` に明示ディレクトリを渡した場合それが既定探索に優先します（`packaging/package_engine.py:249-255,305-306`）。既定探索は Windows target だけで使われ、ディレクトリ順は CUDA_PATH の `bin/x64`, `bin`、HIP_PATH の `bin/x64`, `bin`、最後に `PATH` です（同:236-246）。
- `packaging/build_vision_windows.bat` は variant が `cuda12` なら `CUDA_PATH_V12_9`、`cuda13` なら `CUDA_PATH_V13_0` が定義されていると `CUDA_PATH` に代入します。その後 `nvcc.exe` を確認し、同じ root を `CMAKE_CUDA_COMPILER` と `CUDAToolkit_ROOT` として CMake に渡します（`packaging/build_vision_windows.bat:26-35,57-60`）。これは vision build 用の batch script の挙動で、一般の setup の `find_nvcc()` とは別経路です。

## 実行時の詳細

setup の値取得は `find_nvcc()` が呼ばれる時点です。`STRATA_NVCC`、`CUDA_PATH`、`CUDA_HOME` は `find_nvcc()` の各呼び出しで読み直され、関数内の static cache はありません。既定候補で選んだ compiler の `--version` を調べるのも、その呼び出し時です。選んだ compiler は setup が CMake に渡します（`setup.py:5934-5949`）。ここで確認できるのは Strata setup が選択・転送する値までであり、compiler や CUDA Toolkit 側の動作は記述対象外です。

Windows packaging の `_default_search()` は package 作成時に環境を読みます。`CUDA_PATH` のディレクトリに不足 DLL が見つかれば package staging area にコピーし、`bundled <name> ... (from <directory>)` を表示します。探索後も不足依存が残れば `SystemExit` で `refusing to package: ...` を出します（`packaging/package_engine.py:249-279`）。この処理は package 作成用であり、実行 engine に環境変数を転送しません。

## 観測できる結果

- Windows vision build script は `CUDA_PATH` 未設定時に `CUDA_PATH is not set: install the <variant> toolkit`、`nvcc.exe` 不在時に `no nvcc.exe in <path>\bin` を表示して exit code 1 で終了します（`packaging/build_vision_windows.bat:34-35`）。CMake に渡すコマンドの失敗も `|| exit /b 1` で伝播します（同:57-63）。
- setup の `STRATA_NVCC` 経路は指定ファイル不在時に `[!]` 警告を出し、version 制約違反時にも警告を出します。通常探索後に必要な Toolkit が見つからない場合、`install_build_tools()` の `fail()` は `[X]`、案内文、`Setup stopped...` を出して exit code 1 で終了します（`setup.py:900-909,2219-2230,5671-5677`）。
- `flake.nix` は開発 shell で `CUDA_HOME` とともに `CUDA_PATH` を export します（`flake.nix:39-44`）。これは環境設定であり、Strata が環境から値を読む箇所ではありません。`packaging/build_dsv41_windows.bat:4` は `package_engine.py` が読む旨のコメントだけです。

## 根拠

- `setup.py:91,2215-2249,5660-5680,5934-5949` — OS 判定、compiler 探索、build 経路。
- `setup.py:5004-5031,5095` — CUDA image backend の compiler 探索と利用。
- `packaging/package_engine.py:236-279,305-306` — Windows package の検索 root、DLL のコピー、失敗。
- `packaging/build_vision_windows.bat:26-35,57-63` — variant 別 root 選択、検証、CMake への引き渡し。
- `flake.nix:39-44` — 開発 shell の export。
- `docs/DETAILS.md` — `CUDA_PATH` の動作を説明する該当記述は見つかりませんでした。
