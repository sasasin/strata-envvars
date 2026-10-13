# `BUILD_DIR`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Strata 同梱のビルドスクリプトが CMake のビルドツリーを置く場所を指定する。SYCL ビルドでは configure/build の両方に使われ、Windows HIP ビルドでは configure/build に加えて ZIP パッケージ作成時の入力ディレクトリにも使われる。エンジンの実行時動作を変える変数ではない。

## 値と判定

| 実行経路 | 未設定または空文字 | 設定時 |
| --- | --- | --- |
| `sycl/tools/build.sh` | `REPO` の値（未設定または空なら `git rev-parse --show-toplevel` の結果）に `/build-sycl` を加えたパス | `${BUILD_DIR:-...}` で値を採用する。未設定と空文字はどちらも既定値へフォールバックする |
| `tools/hip/build_windows.bat` | `%SRC%\build-hip-win`。`SRC` はバッチファイルの場所から求めたリポジトリルート | `if not defined BUILD_DIR` で既定値を設定するため、未定義または空なら既定値となり、非空ならその値を使う |

SYCL スクリプトでは値をシェル変数 `b` に代入し、`build.ninja` の確認、`cmake -B`、`cmake --build`、`build.log` の保存先に使う。値を数値や列挙値には変換しない。SYCL 側では `$b` を含むパス展開が引用符で囲まれていないため、空白を含むパスはシェルの単語分割の影響を受ける。

Windows HIP 側では値をパスとして扱い、CMake の `-B`、`cmake --build`、ZIP 作成スクリプトの `--build` に渡す。これらのパス引数は引用符で囲まれている。

## 有効になる条件

- `BUILD_DIR` を読むのは `sycl/tools/build.sh` または `tools/hip/build_windows.bat` を実行したときだけ。各スクリプトは異なる既定値を使う。
- SYCL スクリプトは `$b/build.ninja` にファイルがないときだけ CMake configure を実行する。存在すれば configure を省略して同じディレクトリで build する。
- Windows HIP スクリプトも `"%BUILD_DIR%\build.ninja"` が存在しないときだけ configure する。その後 `tests` 引数の有無に応じて同ディレクトリをビルドし、`package_windows.py --build` に渡す。
- 同梱ドキュメントでは Docker 内の SYCL ビルドで、AOT 用に `build-sycl-aot`、JIT 用に `build-sycl` を指定する例がある。これらはビルド成果物を分ける使用例である。

## 実行時の詳細

SYCL の `build.sh` は `REPO` を優先してリポジトリ位置を決め、`BUILD_DIR` 未設定・空ならその場所の `build-sycl` を使う。指定ディレクトリの `build.ninja` の有無を見て configure の要否を判定し、build 出力を `<BUILD_DIR>/build.log` に tee する。スクリプトはビルド終了コードを `BUILD EXIT ...` と表示する。

Windows HIP のバッチはリポジトリ直下の `build-hip-win` を既定値にし、ビルド完了後に `<BUILD_DIR>` をパッケージャーの `--build` 引数に指定する。従って、既存の `build.ninja` があるディレクトリを別の設定用ビルドツリーとして指定すると、これらのスクリプト自身は再 configure せず、そのツリーの既存 CMake 設定を使う。

## 根拠

- `sycl/tools/build.sh:5-12` — `REPO` と `BUILD_DIR` の既定値、`build.ninja` 判定、configure/build のディレクトリ、ログ出力。
- `tools/hip/build_windows.bat:19-26` — `SRC` と Windows HIP ビルド用既定値。
- `tools/hip/build_windows.bat:64-84` — `BUILD_DIR` による configure/build、および `package_windows.py --build` への引き渡し。
- `tools/hip/package_windows.py:70-84` — `--build` を `Path` として受け取り、そのディレクトリから成果物をコピーする処理。
- `docs/INTEL.md:96-109,675-676`、`docs/INTEL_ARC.md:80-83` — SYCL の AOT/JIT ビルドで異なるビルドディレクトリを指定する使用例。
