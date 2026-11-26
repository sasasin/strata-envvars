# `ROCM_PATH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`ROCM_PATH` は Strata の常駐 inference server の実行設定ではなく、Strata の Python setup と HIP build 補助ツールが ROCm SDK の prefix を探すためのパスとして読む。主な利用箇所は `terminal/setup.py` の `rocm_root()` で、Linux の AMD HIP engine または HIP 画像 engine をソースからビルドするときに使う。システム ROCm が利用可能ならその root と hipBLAS の library directory を build に渡し、利用できなければ TheRock wheel へ進む (`terminal/setup.py:5550-5573`, `5681-5701`, `5934-5939`)。

同じ値は `strata bench run` のレポート作成時に ROCm version ファイルの探索先としても使われる (`terminal/strata_cli/bench_facts.py:288-304`, `371-422`)。別の Strata 所有 build 経路として、Inkling HIP の CMake、`tools/hy4/build_hy4_hip_linux.sh`、画像 gate の `build_sd.py` も値を参照する (`engine/src/inkling2/hip/CMakeLists.txt:10-18,43-63,99-109`, `tools/hy4/build_hy4_hip_linux.sh:1-38`, `terminal/tools/image/gate/build_sd.py:72-85`)。

## 値と判定

| 経路 | unset / 空文字 | 設定時に有効になる値 | 無効・未発見時 |
|---|---|---|---|
| `setup.py` の `rocm_root()` | `os.environ.get("ROCM_PATH") or "/opt/rocm"` により `/opt/rocm` を基点にする。 | 文字列を `Path` にするだけで、文字種・版・絶対パスの parse はしない。空白だけの値も trim されず、その文字列の path として扱われる。 | 基点、その親、その親の親、最後に `PATH` 上の `hipcc` から得た prefix を順に検査する。各候補で `bin/hipcc` と `libhipblas.so*` が必要。条件に合う root がないと wheels 経路へ進む。`terminal/setup.py:5522-5536,5550-5573` |
| `strata bench run` の version probe | 空値は空文字となり、最初の候補を skip。続いて `/opt/rocm` を探す。 | 設定値を path として使い、`<path>/.info/version`、`<path>/core/.info/version` の順に読む。ファイル内容は `.strip()` し、空でない最初の内容を返す。 | ファイルを開けない場合は次の場所へ進み、どちらも値がなければ `amd-smi -h` の出力から `ROCm version: <数字とドット>` を探す。`terminal/strata_cli/bench_facts.py:288-304` |
| `tools/hy4/build_hy4_hip_linux.sh` | `${ROCM_PATH:-/opt/rocm}` により `/opt/rocm`。 | 値を `ROCM` に代入し、compiler、`--rocm-path`、library path の組み立てに使う。 | 別 prefix 探索や値の検証はせず、その prefix の compiler がなければ後続 compiler 呼び出しで失敗する。`tools/hy4/build_hy4_hip_linux.sh:3-19,32-38` |
| Inkling HIP CMake | `ROCM_PATH` は compiler / library の hint として使われない。 | `find_program` の hint (`bin`, `llvm/bin`) と `find_library` の hint (`lib`) に展開される。空値なら `/bin` 等の形の hint が生成され得る。 | compiler 選択では `CMAKE_HIP_COMPILER` が先にあれば環境変数の探索 hint を使わない。ROCm root 用の compiler flag は `STRATA_ROCM_PATH`、次に `CMAKE_HIP_COMPILER_ROCM_ROOT` を使い、`ROCM_PATH` はその root を直接決めない。`engine/src/inkling2/hip/CMakeLists.txt:10-18,43-63,99-109` |
| `terminal/tools/image/gate/build_sd.py` の HIP build | `env.get("ROCM_PATH") or "/data/Strata/.venv/lib/python3.12/site-packages/_rocm_sdk_devel"` により記載の SDK path。 | 指定文字列を `Path` 化し、子プロセス用 `env` の `ROCM_PATH` / `HIP_PATH`、`PATH`、`LD_LIBRARY_PATH` と CMake definitions に使う。 | パスの妥当性確認や別 system prefix 探索はせず、build に進む。`terminal/tools/image/gate/build_sd.py:72-85` |

`setup.py` では受理値が存在するかの判定ではなく、path の候補で `hipcc`、hipBLAS library、および HIP development files を検査する。共有 library の候補は `lib`, `lib64`, `lib/x86_64-linux-gnu`, `lib/x86_64-unknown-linux-gnu`, `lib/aarch64-linux-gnu`。版 header が読めず `rocm_version()` が `None` でも、他条件を満たせば system ROCm を許容する。版が判明して `7.0` 未満なら system ROCm を採用しない (`terminal/setup.py:5494-5509,5512-5519,5560-5573`)。

CLI に `ROCM_PATH` 専用 option はない。`--backend hip` または GPU 判定で選ばれた HIP 経路、`--build`、画像 generation の `--image-backend hip` が処理経路を選ぶ。`STRATA_ROCM_VERSION` は wheels の版選択に関係する別変数で、system root の選択を上書きしない (`terminal/setup.py:4451-4453,9614-9625`; image build `--image-backend` の定義は同 `11470-11485`)。

## 有効になる条件

- 通常の setup では Linux の AMD HIP engine をコンパイルする経路で `rocm_root()` が呼ばれる。既存 engine が有効で再 build が不要なら `build_engine_hip()` は `rocm_root()` より前に戻るため、この setup run では値を使わない (`terminal/setup.py:5656-5677`)。Windows は ready-made HIP engine を使い、通常 setup の同じ system root 選択を通らない (`terminal/setup.py:9606-9615,9624-9629`)。
- HIP image backend の build でも `rocm_root()` を呼ぶ。GPU image reader の再 build が必要な場合は `build_vision_hip()` が HIP compiler / root を組み立てる。vision が `gpu` でなく、engine の build も不要なら、この用途では読まれない (`terminal/setup.py:5750-5780,5900-5940`)。
- `rocm_root()` は指定 root を見つけられないと、親・祖父パスと `PATH` 上の `hipcc` prefix も検査する。候補に `bin/hipcc` と hipBLAS library があり、ROCm version が未知または 7.0 以上で、development files が揃う場合に採用する。候補に compiler/library がない場合は次候補へ進む。一方、compiler/library のある候補が古いか development files 不足なら理由を警告して system 候補探索を打ち切り、wheel 選択へ進む (`terminal/setup.py:5522-5536,5555-5573`)。
- wheel fallback はカード family ごとの TheRock index を使う。対応 wheel のない architecture では setup は終了し、複数 family のカードは system ROCm 7 を要求して終了する (`terminal/setup.py:5574-5582`)。wheel 利用時の `ROCM_PATH` は選択された wheel root で setup 自身が上書きし、`HIP_PATH`、`PATH`、`LD_LIBRARY_PATH` も build 子プロセス向けに設定する (`terminal/setup.py:5601-5615,5681-5701`)。
- Inkling HIP CMake はその HIP target を build する時だけ該当する。明示 CMake cache 値 `CMAKE_HIP_COMPILER` が compiler 探索を先取りし、`STRATA_ROCM_PATH` または `CMAKE_HIP_COMPILER_ROCM_ROOT` が compiler flag 用 root を決めるため、環境変数はそこでは compiler / library の探索 hint に限られる (`engine/src/inkling2/hip/CMakeLists.txt:10-18,43-63,99-109`)。
- `strata bench run` は Linux でカードが検出され、CUDA runtime がない場合のみ `rocm_version()` を呼び、読めた版を benchmark software block の ROCm runtime 値に入れる。GPU 選択や inference backend を変更しない (`terminal/strata_cli/bench_facts.py:371-422`, `terminal/strata_cli/bench_standard.py:881-885`)。
- `terminal/tools/image/gate/build_sd.py` と `tools/hy4/build_hy4_hip_linux.sh` はそれぞれの HIP build tool が実行された時のみに適用される。server mode や各 inference request で `ROCM_PATH` を読む Strata code はこの調査で見つからなかった。

## 実行時の詳細

setup の `rocm_root()` は呼び出しのたびに `os.environ` を読み直し、関数内 static cache はない。プロセス起動後に環境を変更した場合も、その後の呼び出しは変更後の値を見る。system root の検査後、setup は選択 root を `ROCM_PATH` / `HIP_PATH` に設定し、compiler、CMake root、prefix path、library path を build command に渡す (`terminal/setup.py:5550-5566,5681-5701`)。同じ Python setup process の環境は HIP engine / image engine の build subprocess へ渡される。

benchmark 側も `rocm_version()` の呼び出し時に環境を参照し、module global に値を cache しない。hardware report がこの関数を呼ぶのは Linux AMD 判定時だけで、通常は benchmark report の生成中に一度である (`terminal/strata_cli/bench_facts.py:288-304,371-422`; 呼び出し `terminal/strata_cli/bench_standard.py:881-885`)。

## ログと測定値

setup が指定 root 以外の親や `hipcc` prefix を採用した場合は `System ROCm: <prefix> (this distribution keeps hipcc, the libraries and the development files in separate folders)` を表示する。ROCm が古い場合は `the ROCm in <prefix> is <major>.<minor>; Strata needs 7.0 or newer: using AMD's wheels in .venv instead`、development files 不足なら `the ROCm in <prefix> has no HIP development files (...)` で始まる warning を表示する (`terminal/setup.py:5563-5573`)。warning / `say` は標準出力に出る (`terminal/setup.py:997-999,1044-1046`)。

対応 wheel がない architecture や複数 family のカードで system ROCm が必要なのに使えない場合、`fail()` がエラーと hint を出して exit code 1 で setup を終了する (`terminal/setup.py:5574-5582`; `fail()` 実装 `1049-1056`)。選択した system root で engine / image build が失敗する場合の表示は各 build 経路による。GPU picture reader の build 例外は `the GPU picture reader did not compile (<error>): pictures are read on the CPU` と警告され、CPU reader に戻る (`terminal/setup.py:5776-5780`)。

benchmark の version file が読めた場合、結果の `software.runtime` に ROCm version が含まれる。見つからない場合に `ROCM_PATH` 固有の警告はなく、他 runtime もなければ `/software/runtime` の missing reason が記録される (`terminal/strata_cli/bench_facts.py:419-422,478-490`)。この変数に結び付く Strata の測定値は記載されていない。

資料との照合では、`docs/AMD_HIP.md:104-112` が system ROCm 7 と `/opt/rocm` / `ROCM_PATH`、hipcc・hipBLAS・development files、および利用できない場合の TheRock wheels を説明しており、`rocm_root()` の条件と整合する。同資料の概要には親 directory や `PATH` 上の `hipcc` を再探索する詳細はない。`docs/DETAILS.md` には `ROCM_PATH` の記述は見つからなかった。

## 根拠

- `terminal/setup.py:5494-5509,5512-5519,5522-5578` — system ROCm 候補・版・development file の判定。
- `terminal/setup.py:5656-5701,5750-5780,5900-5940,9606-9629` — engine、image reader、image generator の適用経路と build 引き渡し。
- `engine/src/inkling2/hip/CMakeLists.txt:10-18,43-63,99-109` — Inkling HIP CMake の環境値の使い分け。
- `terminal/strata_cli/bench_facts.py:288-304,371-422,478-490`; `terminal/strata_cli/bench_standard.py:881-885` — benchmark report の ROCm version 探索と反映。
- `terminal/tools/image/gate/build_sd.py:72-85`; `tools/hy4/build_hy4_hip_linux.sh:1-38` — 専用 HIP build tool の既定値と引き渡し。
