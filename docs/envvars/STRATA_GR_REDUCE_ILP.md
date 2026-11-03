# `STRATA_GR_REDUCE_ILP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Intel SYCL 版の fused hyper-connection down-reduce で、cached low-rank SiLU 値を再利用する経路の部分和ロードを 8 件ずつ発行する分岐を選びます。環境変数は `sycl/src/kernels/cuda/fused_gr.dp.cpp` にだけ実装されています。CUDA/HIP の通常実装を制御する参照は見つかりませんでした。

## 値と判定

`strata::bm_default_on(name, device, false)` が環境値を判定します。環境値が空でないときは先頭文字だけを見て、`'0'` なら OFF、それ以外なら ON です。文字列全体の解析、空白除去、大文字小文字変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | 第3引数 `false` により OFF（未設定と同じ） |
| 空でない値の先頭が `0` | OFF（例: `0`, `0abc`） |
| 空でない値の先頭が `0` 以外 | ON（例: `1`, `true`, `false`, ` 0`） |

この判定は環境変数に対するものです。ON でも、後述の cached-lo 経路に入らなければ効果はありません。

## 有効になる条件

この分岐は SYCL の `fused_gr_read_multi()` が実行する sliced down-reduce で、`m.cached_lo` が真の場合に限って評価されます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1830-1831,2055-2073`）。`m.cached_lo` が真になるには、low-rank 再利用 `STRATA_GR_LO_REUSE` が有効で、次の条件をすべて満たす必要があります。

- デバイスが Battlemage と判定される。
- `gr_norm_split()` と `gr_down_sliced()` が有効。
- `gr_more_groups(st)`、`gr_large_grf(st)`、`gr_up_ilp()` が無効。
- `gr_up_cols()` が既定の `UPM_COLS` と一致する。
- `gr_reuse_safe(a, n_tok, xn_scratch)` が真。これは `xn_scratch` と各 token の `lo`、入力・出力・重み・各種作業バッファとのメモリ範囲の重なりを調べ、重なる場合は再利用を無効にします。

この条件は `sycl/src/kernels/cuda/fused_gr.dp.cpp:1981-1988` にあります。重なり検査は `sycl/src/kernels/cuda/fused_gr.dp.cpp:260-285` です。`STRATA_GR_LO_REUSE` は helper の既定値が Battlemage で ON、明示値は同 helper の規則で ON/OFF になります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1981-1982`, `sycl/include/strata/sycl_queue.hpp:159-166`）。ただし、対象変数を明示的に ON にしても `m.cached_lo` の条件を迂回しません。`STRATA_GR_CACHED_NORM` だけが有効で `m.cached_lo` が偽の場合、この変数の分岐には入りません。

## 実行時の詳細

`m.cached_lo` が真でこの分岐に初めて到達すると、関数内の `static const bool reduce_ilp` が helper の結果を保存します。以後の呼び出しでは再読込されないため、実行中の環境変更は反映されません。また、この static はデバイスごとではなく関数内で 1 個なので、最初に当該分岐へ到達したデバイスの判定結果がプロセス内で共有されます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2058-2069`）。

ON の場合は `gr_down_reduce_kernel<true, true>`、OFF の場合は `gr_down_reduce_kernel<false, true>` を起動します。第1 template 引数 `MORE` が true の実装は、各ステップで 8 個の部分和を先にロードしてから順番に加算します。false の実装は部分和を 1 個ずつ読み加算します。加算順序は同じです（`sycl/src/kernels/cuda/fused_gr.dp.cpp:635-667`）。ここで変わるのは cached-lo 経路の reduce kernel であり、その他の reduce 経路にはこの環境変数の判定がありません。

この変数自体を報告するログや専用のエラー・終了経路はありません。low-rank 再利用条件を通ったときは別途 `strata: GR reuse enabled: normalized activation %d, low-rank SiLU %d` が stderr に出ますが、ILP の ON/OFF 値はそのログに表示されません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1989-1994`）。

## 根拠

- 候補一覧にある名前と実装参照: `docs/INTEL.md:543`, `sycl/src/kernels/cuda/fused_gr.dp.cpp:2059`。
- 値の判定と Battlemage 既定: `sycl/include/strata/sycl_queue.hpp:119-166`。
- cached-lo の設定条件と補助ログ: `sycl/src/kernels/cuda/fused_gr.dp.cpp:1981-1994`。
- scratch と入力・出力バッファの重なり検査: `sycl/src/kernels/cuda/fused_gr.dp.cpp:260-285`。
- 対象分岐・static cache・起動 kernel: `sycl/src/kernels/cuda/fused_gr.dp.cpp:2055-2073`。
- 8 load 先行と逐次加算: `sycl/src/kernels/cuda/fused_gr.dp.cpp:635-667`。
- fused read の通常 layer 呼び出し: `sycl/src/core/layer.cpp:1620-1632,1643-1655`。
