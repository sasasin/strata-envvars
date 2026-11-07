# `PKGVER`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Linux 向けの CUDA / HIP エンジンをパッケージ化するとき、配布パッケージの版数を指定します。Strata の実行時設定ではありません。参照は `packaging/build_cuda_linux_aarch64.sh`、`packaging/build_hip_linux.sh`、`packaging/build_dsv41_hip_linux.sh` に限られます。

## 値と判定

3 スクリプトともシェルの `${PKGVER:-default}` 形式で読みます。この形式では未設定と空文字のどちらも既定値に置き換わります。空白の除去、数値変換、semver 形式の検証はありません。非空の値は引用付きで `package_engine.py --version` に渡され、パッケージ出力ディレクトリ名と `engine-component.json` の `version` 値になります。

| build script | 未設定または空文字 | 非空の値 | 出力への反映 |
|---|---|---|---|
| Linux aarch64 CUDA | `CMakeLists.txt` の `project(... VERSION ...)` から先頭の一致を抽出（この commit では `0.1.58`） | 文字列をそのまま使用 | 同じ値で Qwen / DSV41 の両パッケージを作成し、build ID にも含める |
| Linux HIP engine | `0.1.58` | 文字列をそのまま使用 | stage の `BUILD.json` と engine package に記録 |
| Linux HIP DSV41 | `0.1.58` | 文字列をそのまま使用 | stage の `BUILD.json` と DSV41 package に記録 |

値の制約はコード上で指定されていません。`package_engine.py` は `--version` を文字列引数として受け取り、版数をディレクトリ名と manifest に格納します。したがって、版数の意味や有効性を検査して fallback する処理は確認できません。通常の版数以外の文字列を渡した場合の配布側の解釈は、このコードからは分かりません。

## 有効になる条件

- aarch64 CUDA 用スクリプトは Linux の `aarch64` / `arm64` でのみ先へ進みます。それ以外では `PKGVER` を読む行より前に stderr へ `build_cuda_linux_aarch64.sh: this builds on arm64 Linux (the DGX Spark)` を出して終了コード 2 で終了します（`packaging/build_cuda_linux_aarch64.sh:21-26`）。
- HIP engine スクリプトでは `VISION_ONLY` が非空の場合、画像 reader のビルド後に終了し、`BUILD.json` 作成・engine package 化には進みません。この経路でも冒頭の `PKGVER` 既定値代入は行われますが、版数は成果物に使われません（`packaging/build_hip_linux.sh:30,78-91`）。
- HIP engine と HIP DSV41 の `NO_PACKAGE` が非空の場合は stage を作成し、版数入り `BUILD.json` を書いた後、パッケージ化をせず終了します（`packaging/build_hip_linux.sh:92-95,115-124`、`packaging/build_dsv41_hip_linux.sh:61-82`）。
- 他の CLI 引数や環境変数による `PKGVER` の上書きは見つかりません。`package_engine.py` の `--version` は必須ですが、値は指定スクリプトが渡したものです（`packaging/package_engine.py:287-293,341-355`）。

## 実行時の詳細

値は各 build shell script が版数を設定する行でシェル展開されます。後の環境変更を再読する仕組みや cache はありません。aarch64 CUDA では CMake の `project` 行から版数を抽出し、同値を `release-<版数>-...` build ID と 2 回の package 呼び出しに使います（`packaging/build_cuda_linux_aarch64.sh:26-27,33-47`）。現行 `CMakeLists.txt` の project 版数は `0.1.58` です（`CMakeLists.txt:11`）。

HIP の 2 スクリプトでは、版数を stage の `BUILD.json` に文字列として書き、続けて `package_engine.py --version` に渡します。packager は `<version>-<platform>-<backend>` 形式の出力フォルダーを作り、manifest の `version` に同値を記録します（`packaging/build_hip_linux.sh:30,92-95,119-125`、`packaging/build_dsv41_hip_linux.sh:22,61-65,76-84`、`packaging/package_engine.py:198-229`）。

packager の失敗は HIP scripts では `$OUT/package.log` に記録され、`chk` が `ABORT packaged failed (rc=...)` を `$OUT/build.status` に追記して終了します。たとえば版数から組み立てた出力フォルダーが既に存在すると、packager は `... already exists; remove it first (packages are immutable)` で拒否します（`packaging/package_engine.py:198-200`、`packaging/build_hip_linux.sh:122-125`、`packaging/build_dsv41_hip_linux.sh:79-84`）。aarch64 スクリプトでは package 呼び出しの失敗を独自に変換せず、そのコマンドの失敗で `set -e` により終了します（`packaging/build_cuda_linux_aarch64.sh:16,37-47`）。

## 根拠

- 全参照箇所: `packaging/build_cuda_linux_aarch64.sh:13,26`、`packaging/build_hip_linux.sh:12,30,95,122`、`packaging/build_dsv41_hip_linux.sh:9,22,64,79`。
- CMake 既定版数: `CMakeLists.txt:11`。
- 版数を受け取る CLI、出力先・manifest への使用、既存出力時の拒否: `packaging/package_engine.py:198-229,287-293,341-355`。
