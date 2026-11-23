# `--threads`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（ルート） |
| オプション | `--threads` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 |

## 役割

CPU backend では OpenMP の thread 数を指定する。CUDA/HIP backend では host 側に配置された expert を処理する worker pool の thread 数として渡される。いずれも worker pool または OpenMP が使われる実行経路でのみ作用する。

## 使い方

```sh
# 通常の CUDA/HIP 実行で、host expert pool の worker 数を 4 に指定
strata-inkling --native model.strata --threads 4

# CPU backend を強制し、OpenMP が有効なビルドで thread 数を 4 に指定
strata-inkling --cpu --native model.strata --threads 4
```

## 値と既定値

値は次の引数を `std::atoi` に渡して整数化する。parser に正の範囲の検証はなく、数値として先頭を解釈できない文字列は `atoi` の結果である `0` になる。値を省略すると、次の argv が `--threads` の値として消費される。引数自体がない場合は `missing value after --threads` を stderr に出して終了コード 2 で終了する。複数回指定した場合は設定値への代入が繰り返され、最後の値が残る（`engine/src/inkling2/ink_main.cpp:380-383,474-475`）。

`BackendOpts::threads` の初期値は `0` で、ソースコメントでは `0 = auto` とされる（`engine/src/inkling2/ink_backend.h:28`）。CUDA/HIP worker pool は値が正ならその値、0 以下なら backend ごとの自動値を使う。CPU backend は値が正のときだけ `omp_set_num_threads` を呼ぶため、0 以下は OpenMP の既定設定を変えない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1177-1181`、`engine/src/inkling2/hip/ink_hip_hybrid.hpp:45-49`、`engine/src/inkling2/ink_cpu_backend.cpp:160-162`）。

## 実行時の動作

parser は値を `cfg.bopts.threads` に格納し、通常のモデル実行では backend 初期化へ渡す（`engine/src/inkling2/ink_main.cpp:474-475,556-568`）。

- `--cpu` で CPU backend が選ばれ、ビルドに `_OPENMP` が定義されている場合、正の値を `omp_set_num_threads` に渡す。それ以降の OpenMP 並列処理の thread 数に影響する。`_OPENMP` がないビルドではこの設定呼び出し自体がコンパイルされない（`engine/src/inkling2/ink_cpu_backend.cpp:153-162`）。
- CUDA backend は値をモデル loader の `cpu_threads` 引数に渡す（`engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199`）。CUDA の hybrid 処理で host expert がある場合に worker pool を開始し、正の値を thread 数として使う。0 以下なら論理 CPU 数の半分を基準に 2〜16 threads の範囲で自動決定する（`engine/src/inkling2/cuda/ink_runner.cuh:459-466,558-564,1277-1284,1462-1468`、`engine/src/inkling2/cuda/ink_hybrid.cuh:1177-1181`）。
- HIP backend も hybrid controller 初期化へ値を渡す。GPU 側に残らない expert があり、hybrid 初期化まで進む経路で CPU expert pool を初期化する。正の値が指定 thread 数になり、0 以下は hardware concurrency から 2〜24 を上限とする自動値（hardware concurrency が 4 以下ならその値、最後に最低 1）になる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1258-1264`、`engine/src/inkling2/hip/ink_hip_hybrid.hpp:235-279`、`engine/src/inkling2/hip/ink_hip_hybrid.hpp:45-55`）。

索引上の対象は CUDA/HIP の `strata-inkling` である（`docs/cli/README.md:1509-1547`）。parser は CPU 実行でも同じ option を受理するが、Metal/SYCL 側で `BackendOpts::threads` の利用箇所は確認できなかった。したがって Metal/SYCL での効果はこの調査範囲では裏付けられない。

## 適用条件と副作用

CUDA/HIP では host expert の処理が必要な場合にのみ worker pool が起動し、VRAM 内に全 expert が収まるなど host pool を使わない経路では `--threads` による worker 数の変更は起きない。CUDA の worker pool 起動時には mapped pinned host memory、GPU buffer、CUDA stream 等を確保する処理があり、開始・割り当てに失敗すると backend 初期化が失敗し得る（`engine/src/inkling2/cuda/ink_runner.cuh:461-466,1177-1205`）。HIP でも hybrid init は DMA stream、GPU staging、coherent host buffer と CPU worker を確保し、失敗時は `false` を返す（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:235-279`）。

`--threads` 自体には正の値の上限検証がないため、大きな正数は worker 数として渡される。実機における適切な値や性能上の効果は、このソース調査からは判断できない。

## 出力とエラー

parser が値なしを検出すると stderr にエラーを出し、終了コード 2 で終了する。非数値文字列や負数を明示した場合に `--threads` 固有の validation error はなく、それぞれ `atoi` の値（通常は 0、または負数）が後段へ渡る（`engine/src/inkling2/ink_main.cpp:380-383,474-475`）。backend 初期化に失敗した場合、通常実行は `init: <理由>` を stderr に出して終了コード 1 となる（`engine/src/inkling2/ink_main.cpp:564-568`）。

同 revision の `--help` 実装（`engine/src/inkling2/ink_main.cpp:488-497`）は各モードの概要を表示するが、`--threads` を列挙していない。これは parser が当該 option を受理しないことを意味せず、受理は `engine/src/inkling2/ink_main.cpp:474-475` で確認できる。

## 根拠

- `engine/src/inkling2/ink_main.cpp:380-383,474-475` — 引数取得、整数変換、値不足時のエラー。
- `engine/src/inkling2/ink_backend.h:17-38` — `BackendOpts::threads` の既定値。
- `engine/src/inkling2/ink_main.cpp:556-568` — option 値を含む backend 初期化と初期化失敗時の出力・終了。
- `engine/src/inkling2/ink_cpu_backend.cpp:153-162` — OpenMP が有効な CPU backend での設定。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199`、`engine/src/inkling2/cuda/ink_runner.cuh:459-466,558-564,773-794,1277-1284,1462-1468`、`engine/src/inkling2/cuda/ink_hybrid.cuh:1177-1181` — CUDA での値の転送、host expert 条件の worker 起動、自動値。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1258-1264`、`engine/src/inkling2/hip/ink_hip_hybrid.hpp:235-279,45-55` — HIP hybrid pool の条件、初期化、自動値。
- `engine/src/inkling2/ink_main.cpp:488-497` — help 表示に `--threads` が含まれないこと。
- `docs/cli/README.md:1509-1547` — 対象 tool ID、CUDA/HIP scope、索引上の option identity。
