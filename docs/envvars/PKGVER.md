# `PKGVER`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点）。

## 役割

engine パッケージのバージョン表記を上書きする、パッケージング専用の変数。読むのは `tools/packaging/build_hip_linux.sh` と `tools/packaging/build_cuda_linux_aarch64.sh` だけで、engine バイナリにも Control の実行時コードにも読み取りはない。値はパッケージのフォルダ名、`engine-component.json` の `version`、（HIP のみ）`BUILD.json` の `version`、debug symbol の置き場の名前に使われる。engine が `strata --version` で出す版は CMake の `PROJECT_VERSION` で決まり、PKGVER では変わらない（`engine/CMakeLists.txt:13,34`、`engine/src/program/generate.cpp:3704`）。

## 値と判定

読み取りは shell の `${PKGVER:-...}` で、`getenv` ではない。「設定されているか」ではなく「空でないか」で既定値に落ちる。

| スクリプト | 未設定 | 空文字 | 既定値の出所 | 値の検査 |
|---|---|---|---|---|
| `build_hip_linux.sh` | `0.1.69` | `0.1.69`（`:-` のため未設定と同じ） | スクリプト内の固定値 | なし |
| `build_cuda_linux_aarch64.sh` | `engine/CMakeLists.txt` の `project(... VERSION ...)`（現在 `0.1.69`） | 抽出結果（現在 `0.1.69`） | CMakeLists を `sed` で抽出 | なし |

- trim・数値変換・正規表現検査はない。`0.1.69-debug`、`v1`、`0.1.69 test`、`../x` もそのまま後段へ渡る。空白のみの値も置換されず、そのまま有効な文字列として扱われる。
- 既定値はスクリプトごとに別。HIP は固定値（`tools/packaging/build_hip_linux.sh:30`）、aarch64 CUDA は CMakeLists からの抽出（`tools/packaging/build_cuda_linux_aarch64.sh:25`）。同じ CUDA でも `tools/packaging/build_cuda_linux.sh:63` は常に CMakeLists から取り、PKGVER を読まない。
- aarch64 CUDA で抽出結果が空になると `ver` が空のまま `--version ""` に渡り、`<out>/-<platform>-cuda-cuda13` というフォルダを作ろうとする。manifest の `version` が空になるため、`package_engine.py:231` の検証が `engine-component.json has no version` で失敗する（`terminal/strata_control/engine_component.py:304-306`）。

## 有効になる条件

- 上記 2 スクリプトを手で実行したときだけ意味を持つ。リポジトリ全体で `PKGVER` の参照はこの 2 ファイルのみで、CI workflow からの設定もない。
- HIP: `VARIANT` と `HP` が必須（`build_hip_linux.sh:22,26`、`set -u`）。`VISION_ONLY=1` は `build_hip_linux.sh:86` で終了するため PKGVER は一切使われない。`NO_PACKAGE=1` は `:133` で終了し、`BUILD.json` と symbol 名には使われるがパッケージは作られない。
- aarch64 CUDA: Linux arm64 以外では `exit 2`（`build_cuda_linux_aarch64.sh:20-23`）、`COMMIT` は必須（`:27`）。
- backend・GPU・モデル状態などのランタイム条件は無関係。値が engine の計算や生成結果を変える経路はない。

## 実行時の詳細

HIP の流れ: `:30` でシェル変数に確定 → `:90` で stage の `BUILD.json` の `version` → `:128` で symbol 名 `<engine 名>-$PKGVER-linux-x86_64-hip-<variant>` → `:136` で `package_engine.py --version`。

`package_engine.py` は version をフォルダ名 `<version>-<platform>-<backend>[-<variant>]`（`:196`）と manifest の `version`（`:214-217`）に使い、同じ名前のフォルダがあれば拒否する（`:197-198`）。stage の `BUILD.json` はそのままパッケージに含まれる（`:57-60`）。文字列の正規化は行わない。

aarch64 CUDA の流れ: `:25` で `ver` → `:38` で symbol 名 → `:40` で build id `release-<ver>-cuda13-<cuda>-aarch64-<commit12>` → `:43` で `--version`。version が build id に入るのはこのスクリプトだけ（HIP の build id は `"$COMMIT+rocm"`、`build_hip_linux.sh:137`）。

読み取りはスクリプト開始時の 1 回で、cache はない。スクリプトは `export PKGVER` をしないため、スクリプト内の既定値は子プロセスの環境に現れない（環境で渡した値はそのまま継承されるが、子の Python は argv で受け取る）。

後段での意味: Control は manifest の `version` を engine の版として読み、複数インストール時の「最新」を `_version_key` で決める（`engine_component.py:196-202,264-265`、`engine_library.py:129-130`）。この比較では数字でない要素は 0 として扱われる。feed に載せる際は `component.version` がそのままエントリの `version` になり（`tools/packaging/feed_tool.py:230`）、feed の検証は `\d+\.\d+\.\d+(\.\d+)?` だけを受け付ける（`terminal/strata_control/feed.py:45,69-73`）。

## ログと測定値

- PKGVER 自体を echo する行はない。`build_hip_linux.sh` の `build.status` には `start <variant> (<archs>) commit <commit>` などが入り、version は現れない（`:45,57`）。
- 観測できるのはパス名。`package_engine.py` の成功表示は `<out>/<version>-<platform>-<backend>... (N MiB, ...)`（`:374`）、同名フォルダがある場合は `<folder> already exists; remove it first (packages are immutable)`（`:197-198`）。
- 数字でない値は feed 作成時に `'<value>' is not a version number (expected like 0.1.46 or 0.1.46.1)` で拒否される（`feed.py:70-71`）。
- Strata の資料に PKGVER の測定値や条件付きの記述はない（リポジトリ内の参照は上記 2 スクリプトのみ）。

## 根拠

- `tools/packaging/build_hip_linux.sh:30,90,128,136`（既定値、`BUILD.json`、symbol 名、`--version`）
- `tools/packaging/build_cuda_linux_aarch64.sh:12,20-25,38,40,43`
- `tools/packaging/package_engine.py:196-198,214-217,231,374`
- `terminal/strata_control/engine_component.py:196-202,264-265,304-306`
- `terminal/strata_control/feed.py:45,69-73`、`tools/packaging/feed_tool.py:230`
- `engine/CMakeLists.txt:13,34`、`engine/src/program/generate.cpp:3704`
