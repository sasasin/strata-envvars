# `strata-inkling --cpu-threads`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--cpu-threads` |
| 別名 | なし |
| 値 | 整数。parser は `std::atoi` で変換し、値域検証をしない |

## 役割

EP CUDA backend で、GPU VRAM に載らなかった expert の一部を NUMA CPU worker pool で処理する hybrid doorbell 経路を有効にし、NUMA node ごとの CPU worker 数を指定する。CPU worker pool を使うのは、単一 GPU で host expert があり、`--cpu-threads` が正数の場合に限られる。通常の CUDA backend と HIP backend では、このオプション値は現行ソース上で実使用されない。

## 使い方

```sh
# EP CUDA backend の構成で、bench 実行時に NUMA node ごとの worker 数を 4 に指定する
strata-inkling --bench --native MODEL.strata --cpu-threads 4
```

この例で doorbell worker pool が有効になるには、実行ファイルが EP CUDA backend を使い、ロード時に host expert が存在する必要がある。コマンドを実行していないため、モデル構成や実行環境ごとの起動可否は確認していない。

## 値と既定値

- 値は `std::atoi` で `BackendOpts::cpu_threads` に格納される。明示的な範囲検証や値の拒否処理は parser にない（`engine/src/inkling2/ink_main.cpp:441-442`）。
- 未指定時の値は `BackendOpts` の初期値 `0`（`engine/src/inkling2/ink_backend.h:17-28`）。
- 同じオプションを複数回指定した場合は、parser が都度同じフィールドに代入するため最後の指定値が残る（`engine/src/inkling2/ink_main.cpp:379-383,441-442`）。
- 値を省略すると `next()` が `missing value after --cpu-threads` を stderr に出して終了コード `2` で終了する（`engine/src/inkling2/ink_main.cpp:379-383,441-442`）。

## 実行時の動作

EP CUDA backend は、GPU 数が 1、host expert 数が 1 以上、かつ `cpu_threads > 0` の全条件を満たすと doorbell を有効にする。それ以外は無効となる。NUMA node 数に応じて host expert を配置し、doorbell pool の `threads_per_node` に指定値を渡す（`engine/src/inkling2/ep_dual_gpu.cu:970-973,1037-1058`）。

有効時、単一 token の decode で host expert の仕事があり、doorbell が処理できる件数・hidden 幅の条件を満たす場合に、CPU workers に処理を通知し GPU 処理と並行させる。条件を満たさない host job はこの doorbell 経路に入らない（`engine/src/inkling2/ep_dual_gpu.cu:1835-1850`）。正数の指定は node ごとの要求数で、Linux NUMA では node 上の物理 core 数以下、その他の経路では hardware concurrency 以下に制限される。0 以下の場合の要求数は自動値となるが、CLI から起動する doorbell 経路自体は `cpu_threads > 0` を条件に無効となる（`engine/src/inkling2/hybrid_doorbell.cu:604-640`）。

この値を実使用するのは `INKLING_ENABLE_EP_CUDA` を付けた EP CUDA 実装である（`engine/src/inkling2/CMakeLists.txt:172-195`）。通常の CUDA backend は loader に `opts.threads` を渡し（`engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199`）、HIP backend も `opts.threads` を CPU pool 初期化に渡す（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1258-1264`）。したがって、これらの backend では `--cpu-threads` は `BackendOpts::cpu_threads` に格納されるだけで、CPU worker 数を制御しない。`--cpu` で CPU backend を強制する経路も GPU の doorbell pool を使わない（`engine/src/inkling2/ink_backend.h:150-168`）。

## 適用条件と副作用

- EP CUDA backend で単一 GPU かつ host expert がある場合に、CPU worker threads を起動する。複数 GPU、host expert 不在、または 0 以下の値では doorbell pool を起動しない（`engine/src/inkling2/ep_dual_gpu.cu:970-973,1037-1058`）。
- 起動した pool は host expert の一部を NUMA CPU で処理する用途に使われる。単一 token の decode で条件を満たす host job の場合に doorbell 通知が行われる（`engine/src/inkling2/ep_dual_gpu.cu:1835-1857`）。
- `--threads` との連動・優先順位はなく、CUDA loader と HIP pool は `--threads` の値を参照する。`--cpu-threads` による性能向上や最適値は、ソース調査だけでは判断できない。

## 出力とエラー

- `--cpu-threads` の値自体に対する parser の警告・エラーはない。値なしの場合の stderr と終了コード `2` は「値と既定値」を参照。
- EP CUDA backend は初期化時に stderr の `[inkling2-ep] Loaded ...` 行へ `doorbell=on/off`、NUMA node 数、指定された `thr` 値を出力する（`engine/src/inkling2/ep_dual_gpu.cu:1064-1068`）。
- doorbell pool 起動関数は worker を作成し、作成数が 0 の場合に `false` を返すが、呼び出し側は戻り値を検査していない（`engine/src/inkling2/hybrid_doorbell.cu:604-640`、`engine/src/inkling2/ep_dual_gpu.cu:1057-1058`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-383,441-442` — root 引数 parser、整数変換、値なし時の失敗。
- `engine/src/inkling2/ink_backend.h:17-28` — `cpu_threads` の既定値 `0`。
- `engine/src/inkling2/ep_dual_gpu.cu:970-973,1037-1068` — doorbell 有効条件、NUMA 配置、worker 数の転送、診断出力。
- `engine/src/inkling2/hybrid_doorbell.cu:604-640` — node ごとの thread 数選択と pool 起動。
- `engine/src/inkling2/ep_dual_gpu.cu:1835-1857` — host jobs を doorbell CPU worker に渡す条件。
- `engine/src/inkling2/CMakeLists.txt:172-195` — EP CUDA backend の compile definition。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1258-1264` — 通常 CUDA/HIP が `opts.threads` を使う根拠。
- `docs/cli/README.md:1509-1518` — tool ID、root scope、および指定オプションの索引リンク。
