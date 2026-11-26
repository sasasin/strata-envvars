# `STRATA_NVCC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_NVCC` は Strata の `terminal/setup.py` がローカルの CUDA ビルドに使う `nvcc` の場所を指定する。空でない値は `nvcc` 実行ファイルのパスとして扱われ、通常の候補探索を止めて指定先だけを検査する。これはセットアップ時のビルドツール選択であり、ビルド済みエンジンの起動時に読む設定ではない。CUDA エンジンまたは CUDA 画像生成器をビルドする経路で作用し、HIP・Vulkan・CPU のビルド経路からは `find_nvcc()` が呼ばれない（`terminal/setup.py:2637-2671, 5900-5933, 6902-6965`）。

値が採用されると、エンジンと CUDA 画像エンコーダーの CMake に `-DCMAKE_CUDA_COMPILER=<nvcc>` が渡り、選択された nvcc の toolkit root が `/usr` 以外なら `CUDAToolkit_ROOT` も指定される（`terminal/setup.py:6861-6867, 6941-6965`）。CUDA 画像生成器では同じ nvcc から toolkit root を組み立て、CMake 定義と実行時ライブラリ候補を選ぶ（`terminal/setup.py:5922-5933`）。

## 値と判定

`find_nvcc()` は呼ばれるたびに `os.environ.get("STRATA_NVCC")` を読み、Python の真偽値で分岐する。値の空白除去や `strip()`、数値変換はしない。非空値はそのまま `Path(pick)` と `[pick, "--version"]` に渡され、バージョン出力から正規表現 `release (\d+)\.(\d+)` の最初の一致を探す。バージョンは major/minor の整数タプルで扱う。空白・大文字小文字・パス形式は正規化されない（`terminal/setup.py:2637-2652`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の CUDA ビルド（`below` なし） | `PATH`、`CUDA_PATH`、`CUDA_HOME`、OS 固有の標準場所から候補を集め、バージョンを読める中で最も新しいものを選ぶ | 存在し、`--version` 出力に `release M.m` がある実行可能な nvcc パス。例: `/opt/cuda-13.0/bin/nvcc` | 空文字は未設定と同じ。存在しないパスは警告後に通常探索。存在するが起動できない、60 秒以内に完了しない、または出力にバージョンがないパスは `(None, None)` となり、通常探索には戻らない |
| CUDA 12 ビルド（`below=(13, 0)`） | 上記候補から `13.0` 以上を除いて最新を選ぶ | 指定 nvcc の版が `13.0` 未満であること。実際のビルド要件は GPU により `12.0` または `12.8` 以上 | 指定 nvcc が `13.0` 以上なら警告し、候補探索へ戻らない。必要最低版未満も後段で不足扱い |
| RTX 50 / sm_120 の CUDA 13.2.0・13.2.1 補正 | 条件に合えば、ユーザー指定がない場合に限り古い 13.x を再探索する | ユーザーが選んだ版は保持。指定なしなら 13.0 以上 13.2 未満の nvcc が自動選択され得る | 非空値があると自動差し替えしない。空文字は「ユーザー指定なし」として扱われる |

空文字は `if pick:` と `if not os.environ.get(...)` の双方で未指定扱いであり、指定パスを意味しない。`0` や `true` のような文字列も特別扱いされず、文字通りのパスとして調べられる。値が存在しない場合だけ通常探索に進み、存在しない指定パスの場合も警告後に通常探索する。一方、存在するパスで `--version` が失敗する・時間切れになる・出力形式が合わない場合は通常探索にフォールバックせず、nvcc 不明として返す。`below` が設定されている場合、指定版が境界以上なら警告して同じく候補探索へは戻らない（`terminal/setup.py:2637-2671, 1192-1197`）。

通常探索は `PATH` の `nvcc`、`CUDA_PATH` と `CUDA_HOME` の下の `bin/nvcc`（Windows は `nvcc.exe`）、Windows の NVIDIA toolkit 標準フォルダー、または非 Windows の `/usr/local/cuda*` と `/opt/cuda*` を調べる。重複を除き、版を読めて条件を満たす候補のうち最大の major/minor を選択する（`terminal/setup.py:2653-2671`）。

## 有効になる条件

- ローカル CUDA エンジンを新規ビルド・再ビルドする経路で `install_build_tools()` が呼ばれること。既存エンジンと必要な画像エンコーダーが最新と判定されればビルドを省略し、この値も読み取られない（`terminal/setup.py:6902-6933`）。
- CUDA 画像生成器をビルドする場合は `backend == "cuda"` のときに読み取る。既に同じ backend と build stamp の生成器があれば `find_nvcc()` より先に返る（`terminal/setup.py:5900-5928`）。
- CUDA 12 の旧 GPU ビルド、または `--cuda 12` 相当では `13.0` 未満が必要で、sm_120 を含む場合の最低版は `12.8`。他の CUDA ビルドでは基本的に CUDA `12.0` 以上が必要で、sm_120 を含む場合は CUDA `13.0` 以上が必要（`terminal/setup.py:6607-6623, 6615-6621`）。
- RTX 50 / sm_120 向けに CUDA 13.2.0 / 13.2.1 の nvcc build number が 86 未満または読めない場合、指定がなければ古い 13.x を探す。`STRATA_NVCC` が非空なら指定版を維持し、警告を出す場合がある（`terminal/setup.py:6563-6593`）。
- Windows では選択された CUDA 版に対応する Visual Studio 環境も別途必要。非 Windows では `g++` が必要。これらは `STRATA_NVCC` の値によって代替されない（`terminal/setup.py:6624-6634`）。
- HIP・Vulkan・CPU 経路では対象の `find_nvcc()` を呼ばない。CUDA 以外の backend にこの変数が転送される処理も見つからない（`terminal/setup.py:5900-5953, 5656-5712`）。

## 実行時の詳細

セットアップの Python プロセス内で `find_nvcc()` を呼ぶ都度、環境から読み直す。関数内 static cache やモジュール起動時の固定読み取りはないため、同一プロセス内で環境が変更された場合、後続呼び出しにはその時点の値が使われる。通常、ツールキット確認後は戻り値の nvcc を CMake 引数に使う。`STRATA_NVCC` 自体を子プロセスへ設定し直す処理はないが、nvcc のパスを CMake 定義へ渡す（`terminal/setup.py:2637-2671, 6615-6634, 6683-6690, 6941-6965`）。

指定ファイルが存在しない場合は「そのパスだけを候補とする」扱いにはならず、通常の候補探索に進む。指定パスが存在してもバージョンを取得できない場合、`find_nvcc()` は `(None, None)` を返す。ツール導入前の確認では必要ツール不足としてインストール案内へ進む場合があり、導入後の再確認では CUDA Toolkit が入らなかったとしてセットアップを終了する。CUDA 12 ビルドで必要版に届かない場合は、通常のツールインストール案内より前に `fail()` で終了する（`terminal/setup.py:2641-2652, 1049-1056, 6615-6621, 6683-6689`）。

## ログと測定値

観測可能な文言は次のとおり。`warn()` は `  [!]  ` を付けてセットアップ出力に表示し、warning event も記録する。`fail()` は `  [X]  ` と案内を表示し、error event の `exit_code=1` を記録して終了する（`terminal/setup.py:1044-1056`）。

- 指定パスが存在しない: `STRATA_NVCC=<値>: no such file; looking for a CUDA toolkit as usual`
- `below` の境界以上を指定: `STRATA_NVCC=<値> is CUDA M.m; this build needs one older than X.Y`
- RTX 50 向けの不具合版をユーザーが指定: CUDA 13.2.0 / 13.2.1 が誤った回答を生むという警告。自動で指定を差し替えない。
- `--version` が失敗・timeout・不一致でも、それ自体の警告はない。後続の要件検査が失敗すれば、不足または CUDA Toolkit の導入失敗として終了する。

`docs/OLDER_GPUS.md:117-119` と `docs/TROUBLESHOOTING.md:210-217, 287-291` は指定 nvcc による CUDA toolkit 選択と既知の CUDA 版条件を記述しており、コードの選択処理と一致する。`STRATA_NVCC` 自体の性能測定値は該当資料にない。

## 根拠

- 候補の読取、指定値の検査、fallback と通常候補選択: `terminal/setup.py:2637-2671`
- nvcc のコマンド出力・timeout 処理: `terminal/setup.py:1192-1197`
- CUDA 画像生成器の読取と適用: `terminal/setup.py:5900-5933`
- sm_120 の自動代替と警告: `terminal/setup.py:6563-6593`
- CUDA ビルドの版要件と不足時の分岐: `terminal/setup.py:6604-6634, 6683-6690`
- CMake へのコンパイラ・toolkit root 適用: `terminal/setup.py:6861-6867, 6941-6965`
- 出力・warning/error event: `terminal/setup.py:1039-1056`
