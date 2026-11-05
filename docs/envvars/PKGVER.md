# `PKGVER`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`PKGVER` は、Strata の Linux HIP パッケージ用ビルドスクリプトと Linux ARM64 CUDA パッケージ用ビルドスクリプトで使われる、生成パッケージのバージョン文字列です。エンジン実行時に読む設定ではありません。Strata 所有ソース内の完全一致参照は `packaging/build_cuda_linux_aarch64.sh`、`packaging/build_hip_linux.sh`、`packaging/build_dsv41_hip_linux.sh` の 3 スクリプトに限られます。環境変数索引の候補名はこのビルド用の読み取りに対応しています。

## 値と判定

3 スクリプトとも `${PKGVER:-既定値}` を使います。シェルの `:-` 展開なので、未設定と空文字はいずれも既定値になります。空白を含む場合も引用された引数として渡されます。値の形式、数値性、セマンティックバージョンとしての妥当性をスクリプト側で検査・変換する処理はありません。

| ビルドスクリプト | 未設定または空文字 | 設定値の使用先 |
| --- | --- | --- |
| Linux ARM64 CUDA (`build_cuda_linux_aarch64.sh`) | `CMakeLists.txt` の最初に一致する `project(... VERSION 数字とドット)` の値。現行ソースでは `0.1.57` | `ver` に保持し、パッケージ名・manifest の version・build id に渡す |
| Linux HIP (`build_hip_linux.sh`) | `0.1.57` | stage の `BUILD.json` の `version` と、パッケージ生成時の `--version` |
| Linux HIP の DSV41 (`build_dsv41_hip_linux.sh`) | `0.1.57` | stage の `BUILD.json` の `version` と、パッケージ生成時の `--version` |

CLI から別の値を指定する優先規則や、別の環境変数による上書きはありません。各スクリプト起動時にシェル展開で一度値が決まり、その後の環境変更を再読込する処理はありません。

## 有効になる条件

- Linux ARM64 CUDA スクリプトでは、`uname` が Linux と `aarch64` または `arm64` を返す必要があります。別プラットフォームでは `PKGVER` の利用前後に関わらず、stderr に `build_cuda_linux_aarch64.sh: this builds on arm64 Linux (the DGX Spark)` を出して終了コード 2 で終了します。
- Linux HIP スクリプトでは通常のエンジンパッケージ作成経路で stage を作ると `BUILD.json` に反映されます。`VISION_ONLY` が空でない場合は `BUILD.json` 作成前に終了するため、`PKGVER` は使われません。`NO_PACKAGE` が空でない場合は `BUILD.json` には書かれますが、`package_engine.py` による最終パッケージは作られません。
- DSV41 HIP スクリプトは stage 作成後に `BUILD.json` へ値を書きます。`NO_PACKAGE` が空でない場合は最終パッケージ作成を省略します。
- HIP スクリプトは `VARIANT`、`LLAMA`、`HP` などの必須設定がないと先にパラメータ展開で停止します。これらや backend、variant はビルド経路を決めますが、`PKGVER` の値自体を変更しません。

## 実行時の詳細

Linux HIP の両スクリプトは `PKGVER` を stage の `BUILD.json` に文字列として埋め込み、パッケージ作成時に `packaging/package_engine.py --version` へ渡します。パッケージ作成コードはこの値を出力ディレクトリ名の先頭と `engine-component.json` の `version` に使います。Linux ARM64 CUDA スクリプトは `ver` を 2 個の CUDA パッケージに渡し、パッケージ名・manifest の version に加えて `release-${ver}-...` 形式の build id に含めます。実行ファイルのバージョンをコンパイル時に変更する処理や、起動後に参照する処理は確認できません。

スクリプトに値の形式を検証する処理はありません。HIP の `BUILD.json` では値を JSON 文字列としてエスケープせずに挿入します。後続のパッケージ作成では `--version` が必須かは確認されますが、空でない値の形式検証はなく、値はそのままパッケージフォルダー名と JSON manifest に使われます。出力先に同じ名前のパッケージフォルダーがすでにあると、パッケージ作成側が `... already exists; remove it first (packages are immutable)` で拒否します。

明示値・空文字・未設定について `PKGVER` 固有の警告やログはありません。HIP のパッケージ作成コマンドは `$OUT/package.log` に出力を記録し、失敗時は `build.status` に失敗理由と終了コードを記録してスクリプトを終了します。ARM64 CUDA は `set -eu` のため、パッケージ作成コマンドの失敗でスクリプトが終了します。

## 根拠

- 全参照と既定値: `packaging/build_cuda_linux_aarch64.sh:13,21-28`, `packaging/build_hip_linux.sh:22-32`, `packaging/build_dsv41_hip_linux.sh:14-24`。
- ARM64 CUDA の platform 条件、`ver` の導出、build id と 2 パッケージへの受け渡し: `packaging/build_cuda_linux_aarch64.sh:21-28,34-47`。
- HIP の条件分岐、`BUILD.json` への埋め込みと package 作成: `packaging/build_hip_linux.sh:60-63,91-96,118-126`, `packaging/build_dsv41_hip_linux.sh:61-65,76-84`。
- 現行 CUDA 既定値: `CMakeLists.txt:11`。
- `--version` の必須引数判定、値の受け渡し、出力ディレクトリ名と manifest の version: `packaging/package_engine.py:198-200,213-218,287-317,341-355`。
