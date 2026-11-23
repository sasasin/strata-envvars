# `CUDA_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の setup と Windows 配布用ツールが、CUDA Toolkit のルートディレクトリを候補として参照するための環境変数。engine の実行時設定ではない。setup の `find_nvcc()` は `CUDA_PATH/bin/nvcc[.exe]` をコンパイラ候補に加え、CUDA ソースビルドと CUDA 画像生成ビルドで利用する。Windows 配布では CUDA DLL の検索元になり、専用ビルドスクリプトは CUDA 画像 reader のコンパイラと Toolkit root を指定する。通常の GPU 推論、モデル選択、CLI の実行時動作を直接変える読み取りは確認できない。根拠: `terminal/setup.py:2595-2629, 5838-5849, 6520-6549`; `tools/packaging/package_engine.py:239-249, 252-281`; `tools/packaging/build_cuda_windows.py:96-105, 168-174`; `tools/packaging/build_vision_windows.bat:26-35, 54-58`。

## 値と判定

| 読み取り箇所・条件 | 未設定／空文字 | 有効になる値 | 無効・不採用になる値 |
|---|---|---|---|
| setup の `find_nvcc()`（Windows / Linux） | `os.environ.get()` は `None` / `""` を偽として候補を追加しない | 空でない文字列を Toolkit root として扱い、その下の `bin/nvcc.exe`（Windows）または `bin/nvcc`（それ以外）を候補にする。例: `C:\CUDA\v13.0`、`/opt/cuda-13.0` | `1` や `true` もフラグではなくパス文字列なので、通常はその下に nvcc がなく採用されない。空白の trim、大小文字変換、環境変数値そのものの存在検査はしない。nvcc が存在しても `--version` 出力に `release 数.数` がなければバージョン不明として選ばれない。 |
| Windows `build_cuda_windows.py` | 空・未設定ならその候補を飛ばす | まず `CUDA_PATH_V12_9` または `CUDA_PATH_V13_0` を、その後 `CUDA_PATH` を調べる。root 内の `bin/nvcc.exe` が存在し、出力から取った `release X.Y` が対象 variant と完全一致すれば採用 | パスが空、nvcc がない、version 表記を読めない、または variant と不一致なら次の候補へ進む。両候補が不適合なら `fail()` で終了する。 |
| Windows `build_vision_windows.bat` | `if defined CUDA_PATH` が偽ならエラーで終了 | `cuda12` では設定済み `CUDA_PATH_V12_9`、`cuda13` では設定済み `CUDA_PATH_V13_0` があれば `CUDA_PATH` を上書きする。その後 `CUDA_PATH\bin\nvcc.exe` の存在を確認 | `if defined` は値の内容や version を検証しない。空文字は未定義相当、`0` や空白は定義済みとして扱われ、後者は nvcc のファイル検査で落ち得る。 |
| Windows 向け `package_engine.py` の既定 DLL 検索 | 空・未設定なら CUDA_PATH のディレクトリを加えない | 非空値なら `bin/x64` と `bin` を候補にする。ただし実在するディレクトリだけ残す | 数値・真偽値としての判定はなく、値を Path の root として使う。 |

setup の候補選択では、空でない `STRATA_NVCC` が既存ファイルを指す場合は `CUDA_PATH` より先に単独で検査される。version を読めればそれを返し、指定された version 上限に合わない場合や version を読めない場合は通常候補へ fallback せず `(None, None)` を返す。指定ファイルが存在しない場合だけ警告を出して通常候補へ進む。通常探索では `PATH` 上の nvcc、`CUDA_PATH`、`CUDA_HOME`、さらに OS ごとの既定場所を走査し、要求された version 上限を満たすもののうち最も新しい version を選ぶ。同じ version の候補は先に見つかったものが残るため、`CUDA_PATH` は `PATH` より優先されず、`CUDA_HOME` より先に同率候補となる。`STRATA_NVCC` が空の場合は設定なしと同じ。根拠: `terminal/setup.py:2595-2629`。

## 有効になる条件

- setup の CUDA engine build では `install_build_tools()` が呼ばれる経路で候補になる。要求 Toolkit version は GPU architecture と toolkit 選択により変わり、CUDA 12 build (`old`) では 13.0 未満を検索し、通常 build は上限なしで検索する。必要 version 未満なら採用後も不足として扱われる。根拠: `terminal/setup.py:6520-6549, 6599-6606, 6849-6863`。
- setup の CUDA 画像生成 build では、CUDA backend が選択され、既存生成物の stamp が一致せず再ビルドする場合に `find_nvcc()` を呼ぶ。GPU engine build の `install_build_tools()` とは異なり、画像生成側の `find_nvcc()` 呼び出しは version 上限を渡さない。nvcc が得られない場合は CUDA 画像生成を失敗させ、Vulkan または CPU backend を案内する。根拠: `terminal/setup.py:5816-5849`。
- Windows の CUDA engine 配布ビルドでは、`build_cuda_windows.py` の `cuda12` / `cuda13` variant に対応した Toolkit が必要。専用 version 環境変数が有効な nvcc を指す場合は `CUDA_PATH` より先に選ばれる。選んだ root をプロセス環境の `CUDA_PATH` に設定し、後続の package tool がその Toolkit の DLL を検索できるようにする。根拠: `tools/packaging/build_cuda_windows.py:96-105, 151-174`。
- Windows の CUDA 画像 reader build では `build_vision_windows.bat cuda12|cuda13 <stage>` を実行するときに必要。variant 専用変数が設定されていれば `CUDA_PATH` を上書きし、専用変数が空・未設定なら既存 `CUDA_PATH` を使う。`nvcc.exe` の存在、Visual Studio C++ compiler、CMake/Ninja など他の前提も満たす必要がある。根拠: `tools/packaging/build_vision_windows.bat:20-58`。
- `package_engine.py` の `CUDA_PATH` 検索は target が `windows` で始まる場合だけ行う。`--search` が一つ以上渡される場合は `search or []` が非空となり、既定検索（`CUDA_PATH`、`HIP_PATH`、`PATH`）を置き換える。CUDA DLL が見つからない場合、他候補も含めて不足が解消しなければ package を拒否する。根拠: `tools/packaging/package_engine.py:239-281, 357-371`。
- Nix の開発 shell は `shellHook` で同じ Toolkit root を `CUDA_HOME` と `CUDA_PATH` の両方に export する。これは Strata の読み取りではなく、setup が参照できるように環境を設定する側の記述。根拠: `tools/nix/flake.nix:39-44`。

## 実行時の詳細

setup の `find_nvcc()` は呼び出されるたびに `os.environ.get()` を評価し、CUDA_PATH 用の static cache は持たない。env 値から組み立てた nvcc 候補について `Path.exists()` を確認し、`nvcc --version` の stdout から `release X.Y` を正規表現で探す。実行失敗または 60 秒 timeout は `out()` が空文字を返すため、その候補は version を得られず採用されない。候補の走査後も適格な nvcc がなければ、呼び出し側が Toolkit 不足として停止する。実行中にプロセス環境が変更された場合は次回の `find_nvcc()` 呼び出しで再評価されるが、すでに選択・ビルドされたコンパイラが遡って切り替わるわけではない。根拠: `terminal/setup.py:2595-2629, 1049-1056, 1192-1196`。

`build_cuda_windows.py` は `find_cuda(variant)` 実行時に環境を読み、variant version と一致する CUDA_PATH root を返す。両環境変数の候補で見つからない場合、`fail()` は `[X] <variant> needs the CUDA <version> toolkit (CUDA_PATH_V... or CUDA_PATH)` を表示し、script を終了コード 1 で止める。`build_vision_windows.bat` は起動時の環境を `setlocal` 内で扱い、variant 用の変数から `CUDA_PATH` を設定して nvcc と CMake に渡す。package 呼び出しは選んだ root を含む Python 環境で起動される。根拠: `tools/packaging/build_cuda_windows.py:96-106, 168-174`; `tools/packaging/build_vision_windows.bat:20-35, 54-60`; `terminal/setup.py:1049-1056`。

`package_engine._default_search()` は Windows target かつ packaging が `--search` を受けていない場合に呼ばれる。DLL を見つけると `bundled <name> ...` を表示して package にコピーし、見つからないまま依存が残れば `refusing to package: ...` で停止する。CUDA_PATH はこの packaging 処理の中でのみライブラリ探索元として使われ、配布後の Strata runtime に環境変数を埋め込む読み取りは確認できない。根拠: `tools/packaging/package_engine.py:239-281, 252-281`。

## ログと測定値

- setup の既定探索で CUDA_PATH 配下の nvcc が使われても、CUDA_PATH 自体を示す専用ログは確認できない。Toolkit が足りないときは setup の `[X] ...` と `Setup stopped. Fix the item above and run it again - everything already done is kept and skipped.` を表示し、終了コード 1 になる。根拠: `terminal/setup.py:1049-1056, 6531-6555, 6600-6606`。
- `build_cuda_windows.py` の不適合経路は `fail()` のメッセージを表示して終了する。vision batch は `CUDA_PATH is not set: install the %VARIANT% toolkit` または `no nvcc.exe in %CUDA_PATH%\bin` を表示して終了コード 1。根拠: `tools/packaging/build_cuda_windows.py:105-106`; `tools/packaging/build_vision_windows.bat:34-35`。
- 該当する性能測定値はない。CUDA_PATH が変えるのはビルド・配布時の Toolkit / DLL 候補選択であり、ここで参照したソースや資料には CUDA_PATH による実行性能差の測定値はない。

## 根拠

- setup の nvcc 探索と version 判定: `terminal/setup.py:2595-2629`
- setup での画像生成 CUDA build: `terminal/setup.py:5816-5849`
- GPU 用 engine build の Toolkit 要件と呼び出し: `terminal/setup.py:6520-6606, 6849-6863`
- Windows engine 配布の Toolkit 探索と環境引き渡し: `tools/packaging/build_cuda_windows.py:96-105, 151-174`
- Windows 画像 reader の variant 選択と nvcc 指定: `tools/packaging/build_vision_windows.bat:20-58`
- Windows package の CUDA DLL 検索: `tools/packaging/package_engine.py:239-281, 357-371`
- Nix shell が CUDA_PATH を設定する箇所: `tools/nix/flake.nix:39-44`
- setup の警告・停止・外部コマンド timeout: `terminal/setup.py:1044-1056, 1192-1196`
- docs との照合: `docs/SOURCE_INSTALL.md:77-85` は CUDA Toolkit を要求する source build を案内し、`docs/TROUBLESHOOTING.md:210-217` は setup が Toolkit 候補を探すことと `STRATA_NVCC` の選択を記す。いずれも CUDA_PATH 固有の値規則は記載せず、上記の詳細は現行ソースから確認した。
- `engine/third_party/strata-llama/cmake/arm64-windows-msvc-cuda.cmake:7-10` にも CMake が CUDA_PATH を参照する記述があるが、これは vendored external dependency のコードであり、本書では Strata の挙動の根拠・説明対象に含めていない。
