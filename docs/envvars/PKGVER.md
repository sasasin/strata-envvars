# `PKGVER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux 向け HIP または ARM64 CUDA の engine package を作る Strata packaging script が、package version を決めるために読む値です。Strata の実行時エンジンやモデル動作を変える環境変数ではありません。HIP script は stage の `BUILD.json` と package manifest に、CUDA script は package directory 名と manifest に値を渡します（`tools/packaging/build_hip_linux.sh:30,88-90,134-135`; `tools/packaging/build_cuda_linux_aarch64.sh:25,37,40-41`; `tools/packaging/package_engine.py:196,214-217`）。

## 値と判定

どちらの script も `${PKGVER:-...}` を使うため、未設定と空文字は既定値に置き換わります。空白だけの値は空ではないのでそのまま採用されます。値の形式・大文字小文字・数値性の検証や変換は各 shell script にありません。値は引用して `BUILD.json` または `package_engine.py --version` に渡されます。package_engine は `--version` を文字列 option として受け、未指定 (`None`) のみを必須エラーにします。空文字や version 形式自体は検査せず、出力ディレクトリ名と manifest の `version` に使います（`tools/packaging/package_engine.py:196,214-217,300-305,357-359`）。

| 実行経路 | unset / 空文字 | 非空の設定値 | 変換・検証 |
|---|---|---|---|
| Linux HIP package (`build_hip_linux.sh`) | `0.1.66` | その文字列を採用 | shell による値変換なし。`BUILD.json` 内では JSON string に直接埋め込まれ、package_engine にも `--version` として渡る（`:30,88-90,134-135`） |
| Linux ARM64 CUDA package (`build_cuda_linux_aarch64.sh`) | `engine/CMakeLists.txt` の最初の `project(... VERSION 数字とドット)` に一致した値 | その文字列を採用 | `sed` の正規表現に一致する数字・ドット部分を既定値として抽出。設定値には形式検証なし（`:25,40-41`） |

HIP の `${PKGVER:-0.1.66}` と CUDA の `${PKGVER:-$(...)}` は shell parameter expansion です。従って未設定だけでなく明示的な空文字も fallback します。例えば `0`, `1`, `true`, `false`, `0anything`, 空白を含む文字列は、非空なら区別なくそのまま選択されます（`tools/packaging/build_hip_linux.sh:30`; `tools/packaging/build_cuda_linux_aarch64.sh:25`）。

## 有効になる条件

- HIP 経路では `tools/packaging/build_hip_linux.sh` を実行し、`VISION_ONLY` が空でなく早期終了する経路を通らず、stage 作成まで到達する必要があります。`NO_PACKAGE` が空でない場合は `BUILD.json` に値を記録した後、package_engine 呼び出し前に終了します（`tools/packaging/build_hip_linux.sh:60,85-90,127-135`）。
- ARM64 CUDA 経路では Linux arm64/aarch64 で `tools/packaging/build_cuda_linux_aarch64.sh` を実行する必要があります。それ以外の OS/architecture は PKGVER を使う前に終了します（`tools/packaging/build_cuda_linux_aarch64.sh:20-25`）。
- 両経路とも、ビルド・stage 処理と package_engine 呼び出しが成功したとき package manifest に反映されます。値によるビルド backend や生成バイナリの選択はありません（HIP: `tools/packaging/build_hip_linux.sh:63-69,131-136`; CUDA: `tools/packaging/build_cuda_linux_aarch64.sh:34-42`）。
- script 実行中に環境を変更しても、冒頭で shell 変数 `PKGVER` / `ver` に取り込んだ後の値は再読込されません。後段では `--version` 引数として明示的に渡され、package_engine 側の PKGVER 環境読取はありません（`tools/packaging/build_hip_linux.sh:30,134`; `tools/packaging/build_cuda_linux_aarch64.sh:25,40`）。

## 実行時の詳細

これは build/package script の開始時に一度評価されます。HIP では起動後すぐ既定値 `0.1.66` を代入し、stage の `BUILD.json` の `version` と `package_engine.py --version` の両方へ渡します。CUDA では OS/architecture guard と `cd` の後に評価し、未設定または空なら `engine/CMakeLists.txt` から値を抽出します。その値は build ID にも含められ、最終的に package_engine の `--version` に渡されます（`tools/packaging/build_hip_linux.sh:21-32,88-90,134-135`; `tools/packaging/build_cuda_linux_aarch64.sh:20-28,37,40-41`）。

package_engine は version を出力 folder 名 `<version>-<platform>-<backend>[-<variant>]` と manifest の `version` に設定します。既に同名 folder があると `SystemExit` で拒否します（`tools/packaging/package_engine.py:196-198,214-217`）。CUDA 側で CMake から既定値が抽出できず `ver` が空になった場合、script 自身の値検査はなく空文字が渡ります。package_engine の必須判定は `None` のみなので、version は空文字のまま folder 名と manifest に使われ得ます（`tools/packaging/build_cuda_linux_aarch64.sh:25,40`; `tools/packaging/package_engine.py:304,357-359,196,214-217`）。

## ログと測定値

PKGVER 専用の有効化ログや警告はありません。HIP では package_engine の出力を `$OUT/package.log` にリダイレクトし、終了コードを `build.status` に `packaged rc=...`、失敗時は `ABORT packaged failed (rc=...)` と記録します（`tools/packaging/build_hip_linux.sh:46-47,134-137`）。CUDA は package_engine を直接実行するため、その診断が script の標準出力・標準エラーに出ます。同名 folder が存在する場合のエラーは `... already exists; remove it first (packages are immutable)` です（`tools/packaging/build_cuda_linux_aarch64.sh:40-46`; `tools/packaging/package_engine.py:196-198`）。測定値は該当しません。

## 根拠

- `tools/packaging/build_hip_linux.sh:30,88-90,131-137` — HIP 経路の既定値、manifest 記録、package 呼び出しと失敗記録。
- `tools/packaging/build_cuda_linux_aarch64.sh:20-27,37-42` — Linux arm64 条件、既定値抽出、build ID と package への引き渡し。
- `tools/packaging/package_engine.py:196-198,214-217,300-305,357-359` — version を使う出力先・manifest と CLI 引数の必須判定。
