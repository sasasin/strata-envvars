# `VCVARS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Windows の CUDA 版 vision reader をパッケージ用にビルドする `tools/packaging/build_vision_windows.bat` が、現在の環境に `cl.exe` が見つからない場合に呼び出す `vcvars64.bat` のパスを指定する。環境変数としての `VCVARS` はこのバッチでのみ参照される。Strata の通常実行時のエンジン、モデル選択、生成処理を制御しない（`tools/packaging/build_vision_windows.bat:40-46`）。

同じ大文字列は `tools/packaging/build_cuda_windows.py` にも現れるが、そこでは `ProgramFiles` / `ProgramFiles(x86)` から Visual Studio の候補ディレクトリを作る Python 定数 `VCVARS` であり、`VCVARS` 環境変数の読み取りではない（`tools/packaging/build_cuda_windows.py:43-45,109-124`）。セットアップ側の `STRATA_VCVARS` は別名の環境変数である（`terminal/setup.py:2674-2687`）。

## 値と判定

バッチは値の文字列を数値・真偽値として parse しない。`where cl` が失敗したときだけ `if defined VCVARS` で設定有無を判定し、定義されていればその内容を `call "!VCVARS!" >nul` のバッチファイル名として使う。値の存在確認や正規化は呼び出し前には行わない（`tools/packaging/build_vision_windows.bat:40-46`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `where cl` が成功 | 値を参照せず、vcvars の呼び出しもしない | 該当なし（設定されていても使われない） | 該当なし |
| `where cl` が失敗 | 既定の候補を順に調べ、見つかった最初の `vcvars64.bat` を `VCVARS` に設定して呼び出す | 実行可能な `vcvars64.bat` のパス（例: `C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat`） | 空文字は `if defined` の判定に委ねられる。存在しないパスや、呼び出し後も `cl.exe` が `PATH` に現れない値では、後続の確認に失敗する |

文字列全体の比較、大文字小文字判定、空白除去、パスの事前検証は行わない。`0`、`1`、`true`、`false`、`0anything` も真偽値としては解釈されず、`where cl` が失敗している状況で設定済みなら、その文字列を呼び出すパスとして渡す。`if defined` は cmd.exe の環境変数定義判定であり、空文字の扱いもこの判定に従う。`setlocal` の範囲内で探索結果を設定するため、見つかったパスは呼び出し元プロセスの環境へは引き継がれない（`tools/packaging/build_vision_windows.bat:20,40-46`）。

## 有効になる条件

- `tools/packaging/build_vision_windows.bat` を Windows の cmd.exe から実行する必要がある。同スクリプトは `cuda12` または `cuda13` と stage フォルダーの 2 引数を要求し、欠けていれば usage で終了する（`tools/packaging/build_vision_windows.bat:21-24,64-66`）。
- `VCVARS` の判定より前に、variant に応じた `CUDA_PATH_V12_9` / `CUDA_PATH_V13_0` があれば `CUDA_PATH` に設定され、`CUDA_PATH\bin\nvcc.exe` の存在が確認される。CUDA toolkit が見つからなければ `VCVARS` は評価されず終了する（`tools/packaging/build_vision_windows.bat:26-38`）。
- 先行する `where cl` が失敗した場合だけ `VCVARS` が評価される。既に `cl.exe` が `PATH` にある x64 Native Tools prompt 等では、設定値は無視される（`tools/packaging/build_vision_windows.bat:40-46`）。
- 未設定時に探す候補は `%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools`、`%ProgramFiles%\Microsoft Visual Studio\2022\Community`、`%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools` の各 `VC\Auxiliary\Build\vcvars64.bat`。既定パスを持つ環境変数は `ProgramFiles` と `ProgramFiles(x86)` であり、候補の存在確認は `if exist` で行う。見つかった候補は `if not defined VCVARS` により最初の一つだけ採用される（`tools/packaging/build_vision_windows.bat:41-44`）。
- 同梱の `build_cuda_windows.py` から起動する経路では、先に `msvc_env()` が `cl.exe` を PATH から探し、なければ同じ 2022 Build Tools / Community 候補の `vcvars64.bat` を使って環境を得る。得られなければ `cl.exe not found: install Visual Studio 2022 Build Tools with the C++ workload, or run this from an x64 Native Tools prompt` で停止する。その後の vision バッチ呼び出しには `msvc_env()` の環境を渡すため、通常この経路ではバッチ内の `where cl` が成功し、`VCVARS` 分岐は通らない（`tools/packaging/build_cuda_windows.py:109-124,167-190`）。
- `STRATA_VCVARS` は `terminal/setup.py` のセットアップが別途読む環境変数である。`VCVARS` をこのセットアップの override として使うコードは確認できない（`terminal/setup.py:2674-2699`）。

## 実行時の詳細

バッチの引数チェックと CUDA variant の設定後、`where cl` でコンパイラーの有無を調べる。見つからない場合、既存の `VCVARS` があればその値を呼び出し、なければ上記候補を走査して最初に存在するファイルを設定して呼び出す。呼び出し後には必ず再度 `where cl` を実行する。成功すれば CMake configure、`strata-vision` の build、stage への exe コピー、`BUILD.json` の vision architecture 記録へ進む（`tools/packaging/build_vision_windows.bat:21-24,40-61`）。

このバッチ内に値のキャッシュや再読み取りはない。各起動時に、そのプロセスの環境を判定する。実行中に外から環境変数を変更する経路は実装されていない。環境変数 `VCVARS` は `build_vision_windows.bat` の処理を決めるもので、同梱 Python の `msvc_env()` が使用する候補一覧を上書きしない（`tools/packaging/build_cuda_windows.py:109-124,189-190`）。

## ログと測定値

`vcvars64.bat` 呼び出しの標準出力は `>nul` で捨てる。呼び出し後も `cl.exe` が見つからない場合は `cl.exe not found: run this from an x64 Native Tools prompt` を出力して終了コード `1` で終わる。値が使われない（`where cl` が成功する）場合に `VCVARS` 固有のログはない（`tools/packaging/build_vision_windows.bat:40-46`）。測定値に関する Strata 資料は該当しない。

## 根拠

- `tools/packaging/build_vision_windows.bat:20-46` — `setlocal`、引数と variant 判定、`cl.exe` の事前確認、`VCVARS` の自動検出・呼び出し、および失敗時の確認。
- `tools/packaging/build_vision_windows.bat:48-61` — CMake configure/build、stage へのコピー、architecture 記録への後続処理。
- `tools/packaging/build_cuda_windows.py:43-45,109-124,167-190` — 同名 Python 定数の内容、`msvc_env()` の独立した探索と、vision バッチへの環境引き渡し。
- `terminal/setup.py:2674-2699` — セットアップが読む別変数 `STRATA_VCVARS`。
