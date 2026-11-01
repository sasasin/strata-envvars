# `ARCHS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`ARCHS` は Linux 向けの CUDA/HIP エンジンや DGX Spark 用 CUDA エンジンをビルドするとき、ビルド対象 GPU アーキテクチャの一覧を渡す環境変数です。実行時の `strata` が読む環境変数ではありません。読み取り箇所は `packaging/build_cuda_linux.sh:18-19`、`packaging/build_hip_linux.sh:33-38`、`spark/build_engine.sh:18` です。

## 値と判定

| 読み取り箇所 | 未設定または空文字 | 非空値の扱い |
|---|---|---|
| Linux x86_64 CUDA | `VARIANT=cuda12` は `60;61;70;75;80;86;89`、`cuda13` は `75;86;89;120` | `;` または `,` を区切りとして扱い、各値に `-real` を付けた CMake の CUDA arch リストを作ります。最後の値は `-virtual` 用にも使います。数値としての事前検証はありません。 |
| Linux HIP | `rx9070`: `gfx1200;gfx1201`、`rx7900`: `gfx1100;gfx1101;gfx1102`、`rx6000`: `gfx1030;gfx1031`、`halo`: `gfx1151`、`igpu`: `gfx1103;gfx1150` | `;` を空白またはカンマに置換した値を、それぞれビルド用の archs とデータ選択用の archs に使います。値自体の妥当性をこのスクリプトで検証しません。 |
| DGX Spark (Linux aarch64 CUDA) | `121` | CUDA x86_64 スクリプトと同じく `;` / `,` 区切りの値を処理し、各値を real arch、最後の値を virtual arch として CMake に渡します。 |

いずれも `${ARCHS:-default}` 形式なので、未設定と空文字は同じく既定値になります。HIP の既知 variant 以外では `${ARCHS:?...}` を使い、未設定または空文字だと Bash が `ARCHS=gfx...` を要求するエラーを出して停止します（`packaging/build_hip_linux.sh:32-38`）。空白だけの値など非空だが不正な値はこの判定を通過し、明示的な値域チェックはありません。

CUDA スクリプトの `real` / `last` 抽出は `tr ';,' '  '` と `awk '{print $NF}'` によります。HIP スクリプトはセミコロンだけを置換し、カンマ区切りの値は別途正規化しません。したがって、区切りの解釈はスクリプトごとに異なります（`packaging/build_cuda_linux.sh:31-36,60-64`、`packaging/build_hip_linux.sh:42-43`、`spark/build_engine.sh:56-62`）。

## 有効になる条件

- `packaging/build_cuda_linux.sh` は Linux x86_64 の CUDA 12/13 ビルドレシピです。`VARIANT` が `cuda12` または `cuda13` である必要があり、CUDA toolkit の版も variant に対応していなければスクリプトは stderr に `build_cuda_linux.sh: ... needs the matching CUDA toolkit` と出して終了コード 2 で止まります。この判定は `ARCHS` の値によらず先に行われます（`packaging/build_cuda_linux.sh:15-29`）。
- `packaging/build_hip_linux.sh` は Linux HIP ビルドです。既知の `VARIANT` では `ARCHS` が既定値を上書きし、未知の名前では明示した `ARCHS` が必須です。エンジンのビルドを省略する `VISION_ONLY` 経路でも archs は GPU vision reader のビルドに使われます（`packaging/build_hip_linux.sh:32-39,59-90`）。
- `spark/build_engine.sh` は Linux aarch64 / DGX Spark 専用で、別 OS や CPU アーキテクチャでは `build_engine.sh: this builds on arm64 Linux (the DGX Spark)` を stderr に出して終了コード 2 で止まります（`spark/build_engine.sh:27-30`）。CUDA toolkit の版の判定も別途あります（同:36-43）。
- `packaging/build_vision_windows.bat` も `ARCHS` という名前を使いますが、variant に応じてスクリプト内で値を設定し、任意の環境入力としては読みません。上書き入力は `VISION_ARCHS` です（`packaging/build_vision_windows.bat:26-33`）。この経路を `ARCHS` 環境変数の読み取りとして数えていません。

## 実行時の詳細

これらはビルド用 shell script が開始時に変数展開し、同じ実行の中でビルド・パッケージ処理へ値を渡します。Strata の実行プロセスでの読み取りやプロセス内 cache はありません。

- CUDA x86_64 ではアーキテクチャ一覧から `-DCMAKE_CUDA_ARCHITECTURES="<各値>-real;<最後>-virtual"` を組み立て、エンジンと vision reader の両方に渡します。さらに `BUILD.json` の `archs` / `vision_archs` に記録し、`package_engine.py` の `--arch` 引数にも渡します（`packaging/build_cuda_linux.sh:31-45,53-64`）。`cuda12` で必要な `sm_60`, `sm_61`, `sm_70` が package 引数に存在しない場合、packager は `refusing to package the cuda12 engine without ...` を出して停止します（`packaging/package_engine.py:176-182`）。
- HIP では `ARCHS` を `CMAKE_HIP_ARCHITECTURES`、GPU vision reader の `STRATA_VISION_HIP_ARCHS`、`BUILD.json` の `archs` / `vision_archs`、kernel data 選択、package の `--arch` 引数に渡します（`packaging/build_hip_linux.sh:42-43,59-69,83-85,92-100,117-120`）。設定・ビルド・package の各コマンドが失敗した場合、スクリプトは `build.status` に `ABORT ... failed` 等を記録する経路があります（同:45-47,63-74,86-89,112-120）。
- Spark では CUDA x86_64 のスクリプトと同様に実・virtual arch を作り、engine と任意の vision reader の CMake 設定に渡します。生成する `BUILD.json` の `archs` に元の文字列を記録します（`spark/build_engine.sh:56-74,84-91`）。

各スクリプトはアーキテクチャ名の独自 parse・正規化をほぼ行わず、CMake / packager に値を渡します。そこで値が拒否された場合、`set -e` 等により該当コマンドのエラーで停止しますが、すべての不正値に対する共通の Strata 固有エラーメッセージはありません。HIP の package 化には追加の tuning table 整合性チェックがあり、不足時は `refusing to package the AMD engine:` と理由を出して終了します（`packaging/build_hip_linux.sh:112-120`、`packaging/package_engine.py:183-187`）。

## 根拠

- `packaging/build_cuda_linux.sh:14-36,39-65` — Linux CUDA の既定値、区切り処理、toolkit 条件、CMake / package への転送。
- `packaging/build_hip_linux.sh:21-43,59-120` — Linux HIP の既定値、必須条件、エンジン・reader・metadata・package への転送。
- `spark/build_engine.sh:16-18,27-43,56-62,70-91` — DGX Spark 用の既定値、platform/toolkit 条件、CMake と metadata への転送。
- `packaging/build_vision_windows.bat:26-33,51-64` — 同名のローカル変数と、実際に上書きする `VISION_ARCHS`。
- `packaging/package_engine.py:168-187` — package 側の arch 必須条件、CUDA 12 条件、HIP tuning 検査。
- `packaging/README.md:31-33` — レシピが対象とする各 Linux backend / platform の説明。これはビルド実績の記述であり、`ARCHS` の追加の実行時効果を示すものではありません。
