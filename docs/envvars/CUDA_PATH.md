# `CUDA_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

この checkout では `CUDA_PATH` は通常の engine 実行時設定ではありません。Strata 所有の setup とパッケージ作成・Windows vision build が、CUDA Toolkit の候補を見つけるか、Windows DLL のコピー元を組み立てるために読みます。

主な用途は次の三つです。

- `setup.py` は CUDA を使うローカル engine build、または NVIDIA image generator build で `nvcc` 候補の一つとして参照します。候補に採用された `nvcc` の場所と version が後続の build 設定へ渡ります。
- `packaging/build_vision_windows.bat` は CUDA 12 / 13 の vision reader build 用 Toolkit root を `CUDA_PATH` から取り、variant 別変数があればそちらで上書きします。
- `packaging/package_engine.py` は Windows 向け engine package の DLL 不足分を探すフォルダーとして `CUDA_PATH\bin\x64` と `CUDA_PATH\bin` を使います。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 設定値の扱い | 選択・優先順位 |
|---|---|---|---|
| `setup.py:2231-2249` の `find_nvcc()` | CUDA_PATH 候補を追加しない | root として扱い、その下の `bin/nvcc`（Windows は `bin/nvcc.exe`）を候補に追加する。候補ファイルが存在し、`nvcc --version` 出力に `release 数字.数字` があれば version 候補になる | 非空の `STRATA_NVCC` が有効なファイルならそれだけを使う。そうでなければ PATH 上の `nvcc`、CUDA_PATH、CUDA_HOME、OS ごとの既知ディレクトリを重複排除して調べ、条件を満たす候補のうち最大の major/minor version を選ぶ。PATH が常に優先されるわけではない |
| `packaging/build_vision_windows.bat:26-35` | variant 別 root も未設定なら失敗 | `cuda12` は `CUDA_PATH_V12_9`、`cuda13` は `CUDA_PATH_V13_0` が定義されていれば既存 CUDA_PATH を置き換える。空値は cmd の `if defined` では選ばれない | variant 別変数が定義済みならそれが優先。なければ継承した CUDA_PATH を使う。root が未設定、または `bin\nvcc.exe` がなければ build を中止 |
| `packaging/package_engine.py:236-246,254-255` | 空なら CUDA_PATH の検索先を追加しない | 非空値の下に `bin\x64` と `bin` を検索先として追加する | 明示した `--search` が一つでもあれば既定検索先全体を置き換える。なければ CUDA_PATH の二つのフォルダー、HIP_PATH の二つのフォルダー、PATH の順 |

`setup.py` で `STRATA_NVCC` が非空で、指定パスが存在しない場合は警告を出し通常候補探索へ進みます。指定ファイルは存在するものの version を読めない場合は `(None, None)` を返し、通常候補には fallback しません。`below` 制約がある build で指定 version が上限以上の場合も警告して `(None, None)` を返します。CUDA_PATH 自体は単なる候補で、ファイルが存在しない、または version 文字列を読めない場合は選択対象になりません。文字列の部分一致や Toolkit 自体の探索規則をここから推測するものではありません。

## 有効になる条件

- `setup.py` の engine build では、既存のローカル engine が source・architecture 等の条件を満たさず再 build が必要な場合に `install_build_tools()` が呼ばれます。CUDA 12 用 build は `find_nvcc(below=(13, 0))` を使い、CUDA 13 以上を候補から除外します。通常の CUDA engine build は `find_nvcc()` です。`STRATA_NVCC` の指定が有効なら CUDA_PATH や CUDA_HOME の候補より優先されます（`setup.py:2215-2249,5660-5677,5931-5947`）。
- NVIDIA image generator を新規 build する経路も `find_nvcc()` を使います。既に同じ backend / architecture の build が揃っていればこの処理は行われません（`setup.py:5004-5031`）。
- `packaging/build_vision_windows.bat` の CUDA_PATH 読み取りは Windows で同バッチを `cuda12` または `cuda13` variant と stage directory 付きで実行した場合だけ有効です。そこで見つけた `nvcc.exe` と root は CMake の `CMAKE_CUDA_COMPILER` と `CUDAToolkit_ROOT` に渡されます（`packaging/build_vision_windows.bat:20-35,57-63`）。このバッチは setup.py の `STRATA_NVCC` / `CUDA_HOME` / PATH 候補探索を呼びません。
- package 作成時の CUDA_PATH 検索先は target が `windows...` のときだけ作られます。`--search` を指定すると既定検索先の代わりになります。見つかった DLL は package stage にコピーされ、DLL の import 依存を最大 8 回たどります（`packaging/package_engine.py:236-246,249-279,305-306,351-355`）。

## 実行時の詳細

### Setup の nvcc 候補

`find_nvcc()` は呼ばれるたびに `os.environ` を読み、結果を cache しません。最初に非空の `STRATA_NVCC` を確認します。指定ファイルがなければ `STRATA_NVCC=<値>: no such file; looking for a CUDA toolkit as usual` を warning として出し、通常候補を検索します。指定ファイルがあればその `--version` 出力から version を取り、成功すれば他候補を比べずに返します。`below` が渡されていて指定 version が上限以上なら warning を出して候補なしを返します（`setup.py:2215-2230`）。

通常探索では PATH の `nvcc` を最初に列挙し、続いて非空の CUDA_PATH と CUDA_HOME それぞれの `bin`、さらに OS 別候補を調べます。候補順は優先順位ではなく、version を読み取れた候補の最大 major/minor を選びます。同じパスは一度だけ調べます。`below` がある場合は version がその値未満の候補だけが選択対象です（`setup.py:2231-2249`）。ここでの PATH の扱いは Strata が `shutil.which("nvcc")` で得た候補についてだけ述べています。

engine build では候補がない、または要求 version を満たさない場合、CUDA Toolkit が不足している旨の `fail()` で setup を止めます。CUDA 12 build の要求は GPU architecture により 12.0 または 12.8 以上です。CUDA 13 build は通常 12.0 以上、sm_120 を含む場合は 13.0 以上を要求します（`setup.py:5660-5689`）。setup が build tools を自動導入した後も候補を再確認し、不足なら `the CUDA Toolkit did not install` で停止します（`setup.py:5739-5746`）。選択した `nvcc` は engine build の `CMAKE_CUDA_COMPILER` と Toolkit root の導出に使われます（`setup.py:5936-5949`）。

### Windows vision build

バッチは `setlocal` 内で環境を扱います。`cuda12` なら定義済みの `CUDA_PATH_V12_9`、`cuda13` なら定義済みの `CUDA_PATH_V13_0` を CUDA_PATH に代入します。variant 専用変数がなければ元の CUDA_PATH を使います。CUDA_PATH が未設定なら `CUDA_PATH is not set: install the <variant> toolkit`、root 内に `bin\nvcc.exe` がなければ `no nvcc.exe in <root>\bin` を表示して終了コード 1 で止まります。検証を通ると CUDA_PATH 由来の compiler と Toolkit root で CMake を構成します。CMake、build、copy、stamp の失敗も `|| exit /b 1` で伝播し、成功時は stage の exe と architecture を表示します（`packaging/build_vision_windows.bat:20-64`）。

### Windows package の DLL 収集

`package_engine.py` の既定検索先は target が Windows の場合だけ、CUDA_PATH の `bin\x64` と `bin`、HIP_PATH の同じ相対フォルダー、PATH の各要素をこの順で候補にします。実在するディレクトリーだけを残します。DLL が足りないとき、まずファイル名そのままで探し、次に大文字小文字を無視した名前で探します。見つかったファイルを stage へコピーすると `bundled <dll> (imported by the engine; from <folder>)` を表示します。依存 DLL が解決しきれない場合は `refusing to package: ...` と不足名を出し、clean PC で engine を開始できないとして package を拒否します（`packaging/package_engine.py:236-279`）。

## 根拠

- Setup が候補を読み、`STRATA_NVCC`、CUDA_PATH、CUDA_HOME と PATH 候補を比較する処理: `setup.py:2215-2249`。
- setup の build tools 選択、CUDA version 条件、失敗経路、engine build への compiler 指定: `setup.py:5660-5689,5710-5746,5931-5949`。
- NVIDIA image generator build で `find_nvcc()` を使う条件: `setup.py:5004-5031`。
- Windows vision build の variant 選択、CUDA_PATH の検証、CMake 指定、終了経路: `packaging/build_vision_windows.bat:20-64`。
- Windows package の既定 DLL 検索順、`--search` による置換、コピー・拒否ログ: `packaging/package_engine.py:236-279,305-306,341-358`。

Strata の engine runtime 本体に CUDA_PATH を読む箇所はこの調査では見つかりませんでした。ここに記した挙動は Strata 所有の setup / Windows vision build / package 作成時の処理に限り、CUDA Toolkit、CMake、Windows loader など外部ツールや OS が環境変数をどう解釈するかは含めていません。
