# `BUILD_DIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`BUILD_DIR` は Strata 本体の実行時設定ではなく、SYCL ビルドスクリプトと Windows HIP ビルド・パッケージ用バッチでビルドディレクトリを指定する環境変数である。SYCL では `sycl/tools/build.sh` の `cmake -B`、`cmake --build`、ログ出力先に使い、Windows HIP では CMake の configure/build とパッケージャーの `--build` 引数に使う。候補一覧に載る名前だが、アプリケーション起動時に読む実装は見つからなかった。SYCL の利用例は `docs/INTEL.md:68-79` と `docs/INTEL_ARC.md:77-80` にある。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL (`sycl/tools/build.sh`) | `$repo/build-sycl`。`repo` は `REPO` が未設定または空なら `git rev-parse --show-toplevel` の結果 | 空でない値をそのままディレクトリ名として使う。例: `/work/Strata/build-sycl-aot` | `BUILD_DIR` 自体の値検証はない。パスが不正、または必要な作成・アクセスができなければ後続の CMake 等が失敗する |
| Windows HIP (`tools/hip/build_windows.bat`) | `%SRC%\build-hip-win` | `if not defined` に該当しない値を使う | 値の形式検証はない。空または未定義は既定値に置き換わる |

SYCL 側は Bash の `${BUILD_DIR:-...}` を使うため、未設定と空文字の両方が既定値になる。文字列としての比較、数値変換、範囲制限、空白除去はしない。Windows 側は `if not defined BUILD_DIR` で判定し、空・未定義なら既定値を設定する。どちらもパスが存在するかの一般的な検証は変数判定時には行わず、後述の `build.ninja` 確認やビルド処理に委ねる。SYCL のパス展開は引用符で囲まれていないため、空白や glob 文字を含む値はシェルの語分割・展開の影響を受ける。`sycl/tools/build.sh:38-44`、`tools/hip/build_windows.bat:25-32,70-85`。

## 有効になる条件

- SYCL ビルド経路で `sycl/tools/build.sh` が呼び出されること。リポジトリ資料は Docker の `strata-sycl-dev` 内での実行例を示し、`BUILD_DIR` を `docker run -e` で渡している（`docs/INTEL.md:55-70,73-79`）。この変数自体に GPU 世代やモデル状態の条件はない。
- Windows HIP 経路では `tools/hip/build_windows.bat` が実行されること。Windows バッチ内の `SRC` を既定パスの基点にする（`tools/hip/build_windows.bat:25-32`）。
- 指定ディレクトリに `build.ninja` があると configure をスキップし、既存 CMake cache を使う。従って `BUILD_DIR` は既存ビルドの選択先にもなり、同ディレクトリに以前の構成があれば、それがそのまま使われる（`sycl/tools/build.sh:40-43`、Windows は `tools/hip/build_windows.bat:73-80`）。
- `REPO` は SYCL スクリプトのソース位置・既定ビルド先を決める別環境変数である。`BUILD_DIR` が明示されればそのディレクトリが使われる。CLI の build-directory 引数による上書きはスクリプトにない。SYCL の CLI 引数は任意の CMake target (`--target`) に渡されるだけ（`sycl/tools/build.sh:38-44`）。
- Windows HIP では第 1 CLI 引数 `tests` がビルド target を変えるが、ビルドディレクトリは変えない（`tools/hip/build_windows.bat:33-34,82-85`）。

## 実行時の詳細

SYCL スクリプトは起動時に `BUILD_DIR` を `b` に展開する。指定先に `build.ninja` がなければ `cmake -S $repo/sycl -B $b ...` を実行し、存在すれば configure を省略する。続いて `cmake --build $b` を実行し、標準出力・標準エラーを `$b/build.log` に tee する。スクリプト内に環境変数値を後から再読込する処理や cache はない。環境の変更を反映するには新たなスクリプト実行が必要だが、指定先に既存 cache があれば CMake 構成は引き継がれる。configure 時は `AOT`、`SPIN_MAX`、`I8_ESIMD`、`IQ_DECODE_FAST` など別の設定も渡る。既存 build では `I8_ESIMD` だけを明示的に再設定する処理がある（`sycl/tools/build.sh:38-45`）。

Windows HIP バッチは起動後、値が未定義なら既定値を設定し、`%BUILD_DIR%\build.ninja` がなければその場所を `cmake -B` に渡す。その後同じ場所で `cmake --build` し、最後に `tools/hip/package_windows.py --build` に渡す。ビルドディレクトリを選ぶ別の cache はバッチ内にない。既存 `build.ninja` があると初回 configure の CMake 引数（例: HIP arch や compiler）を再適用せず、その既存 build を使う（`tools/hip/build_windows.bat:31,70-85,118-120`）。

## ログと測定値

測定値は該当しない。SYCL はビルド後に `BUILD EXIT <終了コード>` と `errors: <error: 行数>` を出力し、`cmake --build` の終了コードで終了する。ビルドログは選択したディレクトリの `build.log` に保存される（`sycl/tools/build.sh:44-52`）。Windows HIP は configure/build の失敗時に終了コード 1 で中断し、成功時には `%DIST_DIR%\strata-windows-x64-hip.zip` の出力先を表示する（`tools/hip/build_windows.bat:73-85,118-122`）。これらは `BUILD_DIR` の値に応じた特別な警告ではなく、指定されたパス上でのビルド結果である。

## 根拠

- `sycl/tools/build.sh:38-52` — SYCL の既定値、configure 判定、build とログの出力先、終了結果。
- `tools/hip/build_windows.bat:25-34,70-85,118-122` — Windows HIP の既定値、configure/build とパッケージャーへの受け渡し。
- `docs/INTEL.md:55-83`、`docs/INTEL_ARC.md:71-83` — Docker 実行時の設定例と説明。
