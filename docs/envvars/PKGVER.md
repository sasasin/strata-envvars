# `PKGVER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`PKGVER` は Strata の実行時設定ではなく、同梱の Linux engine パッケージ作成スクリプトがパッケージ版を指定するための環境変数。CUDA aarch64 用では package の `--version` と出力ディレクトリ名に、HIP Linux 用では中間 `BUILD.json` の `version` と package の `--version` に使われる。エンジンの実行時動作やビルド機能を切り替える参照は見つからなかった（`tools/packaging/build_cuda_linux_aarch64.sh:25,40`; `tools/packaging/build_hip_linux.sh:30,89,134`）。

## 値と判定

どちらのスクリプトもシェルの `${PKGVER:-既定値}` を使う。この展開は変数が未設定または空文字のとき既定値に置き換え、非空の値は文字列のまま採用する。真偽値判定、数値変換、前後空白の除去、バージョン形式の検査、文字大小の変換はスクリプトにない（`tools/packaging/build_cuda_linux_aarch64.sh:25`; `tools/packaging/build_hip_linux.sh:30`）。

| スクリプト・条件 | unset / 空文字 | 非空値の扱い | 例 |
|---|---|---|---|
| Linux aarch64 CUDA。OS/architecture 判定を通過した後に評価 | `engine/CMakeLists.txt` の最初の `project(... VERSION ...)` から `sed` で数字とドットの連続部分を取る。現行ソースでは `0.1.67`（`tools/packaging/build_cuda_linux_aarch64.sh:20-25`; `engine/CMakeLists.txt:13`） | そのまま `ver` に設定し、`package_engine.py --version` に渡す | `0.2.0` はその文字列のまま。`0anything` も拒否・変換されずそのまま渡る |
| Linux HIP | `0.1.67`（`tools/packaging/build_hip_linux.sh:30`） | そのまま `PKGVER` に設定し、後段の `BUILD.json` と `package_engine.py --version` に使う | `0.2.0` はその文字列のまま。`0anything` も拒否・変換されずそのまま渡る |

`0`、`true`、`false` も特別な意味を持たず、非空文字列として扱われる。空文字は明示しても unset と同じ既定値になる。読み取った文字列を `package_engine.py` が出力ディレクトリ名と package manifest の `version` に記録する（`tools/packaging/package_engine.py:196,214-217`）。manifest 読み込み側は `version` が空でない文字列かだけを検査し、バージョン形式は検査しない（`terminal/strata_control/engine_component.py:304-306`）。HIP スクリプトは同じ値を JSON 文字列へシェル展開するため、JSON の引用符や制御文字を含む値はエスケープされず、不正な JSON になり得る（`tools/packaging/build_hip_linux.sh:88-90`）。

## 有効になる条件

- **CUDA:** `tools/packaging/build_cuda_linux_aarch64.sh` のみ。`uname -s` と `uname -m` が `Linux-aarch64` または `Linux-arm64` の場合に続行し、それ以外は `PKGVER` の展開より前に終了コード 2 で終了する（`tools/packaging/build_cuda_linux_aarch64.sh:20-25`）。
- **HIP:** `tools/packaging/build_hip_linux.sh` のみ。スクリプトが必要とする `VARIANT` 相当の `V` と ROCm root `HP` などの前提を満たして処理が進み、engine package 作成まで到達した場合に package 版として使われる（`tools/packaging/build_hip_linux.sh:21-32,60-70,85-89,131-136`）。`VISION_ONLY` は package 作成前に終了し、`NO_PACKAGE` は stage 作成後に package 化を省略するため、その実行では `PKGVER` は package に反映されない（同 `:85,131`）。
- CUDA aarch64 と HIP Linux 以外のビルドスクリプトでは、`PKGVER` の参照は見つからなかった。CLI 引数や別の環境変数による `PKGVER` の上書き・優先順位もこの二つの読み取り経路にはない。

## 実行時の詳細

これはビルド／パッケージ作成スクリプトの実行時にシェルが一度展開する値であり、Strata engine の起動時には読み直されない。プロセス内 cache や実行中の再読込もない。CUDA スクリプトは `ver` をコマンド引数 `--version "$ver"` として package 作成ツールへ渡す。HIP スクリプトは `PKGVER` を stage の `BUILD.json` に書き、さらに `--version "$PKGVER"` として渡す。したがって後段 Python プロセスは `PKGVER` を自ら環境から読むのではなく、値をファイルまたは明示的な CLI 引数で受け取る（`tools/packaging/build_cuda_linux_aarch64.sh:25,40`; `tools/packaging/build_hip_linux.sh:30,88-90,134`）。

package 化では `package_engine.py` が `version` をディレクトリ名に使い、manifest の `version` フィールドへ保存する（`tools/packaging/package_engine.py:196,214-217`）。HIP の `VISION_ONLY` / `NO_PACKAGE` 経路は前節の通り package 化しない。CUDA 側は `set -eu` のため、パッケージ作成コマンドが失敗すると後続の検証処理へ進まずスクリプトが終了する（`tools/packaging/build_cuda_linux_aarch64.sh:15,40-47`）。HIP 側は package 作成コマンドの出力を `$OUT/package.log` に記録し、失敗時は `chk` が `$OUT/build.status` に失敗と `ABORT packaged failed (rc=...)` を記録して終了する（`tools/packaging/build_hip_linux.sh:45-47,134-140`）。

## ログと測定値

`PKGVER` の既定値選択や値の形式について、専用ログや警告を出す処理はない。CUDA の非対応 OS/architecture では `build_cuda_linux_aarch64.sh:22` のエラー文を stderr に出して終了するが、この判定は `PKGVER` を展開する前に行われる。HIP の package 作成失敗は `$OUT/package.log` と `$OUT/build.status` に記録される（`tools/packaging/build_cuda_linux_aarch64.sh:20-27`; `tools/packaging/build_hip_linux.sh:45-47,134-140`）。性能測定値は該当しない。

## 根拠

- `tools/packaging/build_cuda_linux_aarch64.sh:12-14,20-28,37-47` — 対象・既定値の選択・package version の引き渡し・失敗時の制御。
- `engine/CMakeLists.txt:13` — CUDA aarch64 スクリプトが既定値抽出に使う現行 project version。
- `tools/packaging/build_hip_linux.sh:21-32,45-50,60-90,127-140` — HIP の既定値、前提条件、stage の `BUILD.json`、省略経路、package version の引き渡しと失敗記録。
- `tools/packaging/package_engine.py:166-217,299-375` — `--version` を受け取り、出力フォルダー名と manifest に保存する処理。
- `terminal/strata_control/engine_component.py:304-306` — manifest の `version` フィールドの型と空値チェック。
