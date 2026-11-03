# `COMMIT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata の作業ツリーは `main...origin/main` で変更なし。

## 役割

Linux 向けビルド・パッケージ用シェルスクリプトが、ソースツリーに `.git` がない場合などに、ビルド対象の commit 識別子を受け取るための環境変数です。主にビルド ID やパッケージの `--build-id` に使われます。実行時の `strata` / `strata-dsv41` がこの名前の環境変数を読む箇所は確認できません。

値は commit ハッシュとして形式検証されません。いくつかの DeepSeek-V4.1 ビルドでは先頭 9 文字を `BUILD_ID` に書き、`strata-dsv41 --version` と verbose 起動時に表示される ID にします。SYCL/CUDA/HIP のパッケージでは、別途、引数や JSON の build metadata に使われます。

## 値と判定

各スクリプトは Bash/POSIX shell の parameter expansion で扱い、数値変換やハッシュ形式・長さの検査はしません。`${COMMIT:-fallback}` は未設定と空文字の両方で fallback します。

| ビルド経路 | 未設定または空文字 | 設定値の扱い |
|---|---|---|
| Linux SYCL | `git rev-parse --short=12 HEAD` の結果。git 情報もなければ `unknown` | その文字列を package `--build-id` の `${commit}-oneapi${iccver}` に含める |
| Linux CUDA aarch64 (DGX Spark) | `git rev-parse HEAD` の結果。得られなければ stderr に `build_cuda_linux_aarch64.sh: set COMMIT=<hex> (no .git here)` を出して exit 2 | 文字列全体を子の `spark/build_engine.sh` に export し、12 文字までを Qwen package build ID に使う |
| Linux HIP engine package | `unknown` | 先頭 9 文字を `BUILD_ID` に書く場合がある。package build ID は `${COMMIT}+rocm` |
| Linux HIP DeepSeek-V4.1 package | `unknown` | 先頭 9 文字を `BUILD_ID` に書く場合がある。値が `unknown` でなければバイナリ内の先頭 9 文字を照合し、package build ID にも全体を含める |
| CUDA DeepSeek-V4.1 helper / Spark engine helper | unset/空は、ソースに `.git` も `BUILD_ID` もない状態で DeepSeek-V4.1 をビルドするとエラー | `.git` と `BUILD_ID` がない場合、先頭 9 文字を `BUILD_ID` に書く。CUDA helper は設定値が非空なら、ビルド後もバイナリに同じ先頭 9 文字があるか確認 |

## 有効になる条件

これは実行エンジンの設定ではなく、対象のビルド・パッケージスクリプトが起動されたときだけ参照される値です。OS/backend そのものを切り替えません。確認できた対象は Linux 向けの SYCL、CUDA、HIP ビルドスクリプトです。

- `packaging/build_cuda_linux_aarch64.sh` は `COMMIT` が空なら checkout の HEAD を代用し、どちらも得られない場合に終了します。その値を `export` して `spark/build_engine.sh` に渡します。同 helper は `BUILD_DSV41=1`（既定）かつソースに `.git` と `BUILD_ID` がないときだけ `COMMIT` を必須にします。`BUILD_DSV41=0` ならこの helper 内での COMMIT 要求は発生しません（`build_cuda_linux_aarch64.sh` 自体は別途 commit 値を必須にします）。`packaging/build_cuda_linux_aarch64.sh:27-34`, `spark/build_engine.sh:49-54`。
- `packaging/build_dsv41_cuda.sh` はソースに `.git` も `BUILD_ID` もない場合だけ `COMMIT` を必須とします。`packaging/build_dsv41_hip_linux.sh` と `packaging/build_hip_linux.sh` は値が `unknown` でなく、`.git` と `BUILD_ID` がない場合にだけ `BUILD_ID` を作ります。既存の `BUILD_ID` はこれらのスクリプトから上書きされません。`packaging/build_dsv41_cuda.sh:21-25`, `packaging/build_dsv41_hip_linux.sh:23-37`, `packaging/build_hip_linux.sh:30-51`。
- `packaging/build_sycl_linux.sh` は commit 値をパッケージ作成時に決めます。未設定/空なら checkout の短縮 ID（12 文字）を使い、git 情報がなければ `unknown` になります。`packaging/build_sycl_linux.sh:48-50,68-69`。

## 実行時の詳細

各ビルドスクリプトの実行中に shell が環境から読みます。プロセス起動後の変更を監視・再読込する仕組みや、ビルド済み `strata` の実行時に `COMMIT` を読む仕組みはありません。

DeepSeek-V4.1 の CMake 設定は、`STRATA_BUILD_ID` が未指定ならソースの `BUILD_ID` ファイル、次に git の短縮 HEAD、最後に `unknown` を採用して `DS4_BUILD_ID` compile definition に設定します（`CMakeLists.txt:946-957`）。ビルドスクリプトから `COMMIT` が `BUILD_ID` へ書かれた場合は、このビルド ID の入力になります。`strata-dsv41 --version` は `strata-dsv41 <version> build <id>` を stdout に出して終了し、`--verbose` は同じ ID を stderr に表示します（`src/dsv41/ds4_main.cpp:2567-2572`）。

明示的な失敗経路は以下です。

- CUDA DeepSeek helper: tarball 相当（`.git` なし）で `BUILD_ID` も `COMMIT` もなければ、stderr に `build_dsv41_cuda.sh: ... set COMMIT=<hex> so the engine can print its commit` を出し exit 2。値が設定されていても、生成バイナリにその先頭 9 文字がなければ exit 1。`packaging/build_dsv41_cuda.sh:23-25,34-36`。
- CUDA aarch64 package: `COMMIT` も checkout HEAD も得られなければ、stderr に `build_cuda_linux_aarch64.sh: set COMMIT=<hex> (no .git here)` を出し exit 2。`packaging/build_cuda_linux_aarch64.sh:27-29`。
- Spark helper: DeepSeek-V4.1 をビルドする条件で値が必要なのに unset/空なら stderr に `build_engine.sh: ... set COMMIT=<hex> so the DeepSeek engine can print its commit` を出し exit 2。`spark/build_engine.sh:50-53`。
- HIP DeepSeek helper: `COMMIT` が `unknown` 以外ならバイナリ内に先頭 9 文字があるかを確認し、なければ build status に `ABORT strata-dsv41 does not carry the build id ...` を記録して exit 1。`packaging/build_dsv41_hip_linux.sh:36-37,53`。

HIP engine package の build status には開始時の commit 値が記録されます。HIP の package metadata には `COMMIT` 由来の文字列も記録されます。これらはビルド時の記録であり、Strata の実行時設定としての効果を示すものではありません（`packaging/build_hip_linux.sh:58,94-95,122-125`）。

## 根拠

- 候補一覧に `COMMIT` が含まれます（`docs/envvars/000_envvers.md:116`）。同名の全参照を検索し、環境値として使う参照は上記のビルド用シェルスクリプトに限られることを確認しました。その他には `.git` のサンプル hook、Windows の `MEM_COMMIT`、識別子名・コメント、ディスク上の `COMMIT` ファイルの読み取りがありますが、環境変数 `COMMIT` の読み取りではありません。
- ビルドスクリプトでの読み取りと転送: `packaging/build_dsv41_cuda.sh:21-36`, `packaging/build_sycl_linux.sh:48-50,68-69`, `packaging/build_cuda_linux_aarch64.sh:27-39`, `packaging/build_dsv41_hip_linux.sh:23-37,43,53,63-80`, `packaging/build_hip_linux.sh:30-51,58,94-95,122-125`, `spark/build_engine.sh:49-54`。
- `BUILD_ID` から compile definition への設定と、実行時の表示箇所: `CMakeLists.txt:946-957`, `src/dsv41/ds4_main.cpp:2567-2572`。
