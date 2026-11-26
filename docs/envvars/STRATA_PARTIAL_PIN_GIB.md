# `STRATA_PARTIAL_PIN_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

RAM 上に作る expert cache complement のうち、GPU 用に部分登録する先頭範囲の上限を GiB 単位で指定する。CUDA の通常経路では `STRATA_PARTIAL_PIN=1` も必要で、この変数だけでは部分登録を有効化しない。どちらも `FileExpertSource::pin_cache_complement` の pageable fallback 内で読み取られる（`engine/src/core/expert_source.cpp:4431-4449`）。

補完全体を割り当てる `--resident-budget-gib` 等の RAM 予算とは別の上限であり、登録されない残りも RAM に保持される。CUDA では残りを resident lock の対象にする（`engine/src/core/expert_source.cpp:4560-4566`）。

## 値と判定

`std::atof` の結果が正なら、その値に `1073741824.0` を掛けて `uint64_t` に変換する。文字列全体の数値検証、丸め、上限値の制限はない。未設定、空文字、0 以下、数値に変換できない文字列では既定の 24 GiB になる。`atof` は数値の先頭部分を読むため、たとえば `2abc` は 2 GiB として扱われる（`engine/src/core/expert_source.cpp:4446-4449`、SYCL: `engine/sycl/src/core/expert_source.cpp:1953-1956`）。

| 入力例 | `pin_cap` |
|---|---:|
| 未設定、空文字、`0`、`-1`、`abc`、`0anything` | 24 GiB |
| `2`、`2.5`、` 2 `、`2abc` | 2 GiB、2.5 GiB、2 GiB、2 GiB |
| 正の値が 2 GiB 未満 | 指定値。ただし通常の部分登録ループは 2 GiB 以上から試すため、登録範囲は 0 になり得る |
| 正の値が complement より大きい | 通常経路では complement のサイズを上限として使う |

通常経路では候補範囲を 2 GiB ずつ小さくし、expert blob の途中で終わらない境界に切り下げる。したがって実際の登録量は指定値と一致するとは限らない（`engine/src/core/expert_source.cpp:4528-4558`、SYCL: `engine/sycl/src/core/expert_source.cpp:1957-2018`）。

## 有効になる条件

- 補完領域 `bytes` が正で、`pin_cache_complement` が呼ばれること。generate 経路では GPU expert cache を開いた後にこの関数へ `o.resident_pin` と `o.resident_budget` を渡す（`engine/src/program/generate.cpp:12077-12080`、SYCL: `engine/sycl/src/program/generate.cpp:7097-7099`）。
- `pin` が真であること。初回の page-locked allocation に成功すると通常はこの cap を使わず、割り当てに失敗して pageable memory fallback に入ったときだけ以下の判定へ進む（`engine/src/core/expert_source.cpp:4374-4397,4431-4449`、SYCL: `engine/sycl/src/core/expert_source.cpp:1871-1929,1938-1956`）。
- CUDA の通常経路では、さらに `budget_bytes > 0` と `STRATA_PARTIAL_PIN` の `std::atoi` 結果が 0 以外であること。`STRATA_PARTIAL_PIN_GIB` 自体は opt-in ではない。`STRATA_PARTIAL_PIN` が未設定・空・`true`・`0anything` なら無効、`1`・`-1`・`1x` なら有効（`engine/src/core/expert_source.cpp:4440-4449,4528-4558`）。
- CUDA の Linux paced 経路（`STRATA_PIN_GUARD=2` または NUMA placement）では、段階的に得た resident 領域から GPU 登録を試すが、ループは `got` を基にし `pin_cap` を使わない。したがってこの環境変数はその経路の登録上限にならない（`engine/src/core/expert_source.cpp:4328-4354,4450-4527`）。
- SYCL 経路では `budget_bytes > 0` と `STRATA_PARTIAL_PIN` の `atoi != 0` が必要で、`pin_cap` が候補サイズの上限に使われる（`engine/sycl/src/core/expert_source.cpp:1947-1959`）。ただしこのファイルでは既存 host memory の CUDA 登録呼び出しが移植時に `0 == 0` の分岐へ置き換えられており、実際の登録 API は呼ばれない。Strata は alias と `partial_pin` の範囲を設定し、残りを `lock_resident` に渡す（`engine/sycl/src/core/expert_source.cpp:1969-2018`）。

## 実行時の詳細

この変数に CLI 引数による上書きはない。`--resident-budget-gib` などで予算が正であることは通常の CUDA/SYCL 部分登録の別条件だが、予算値がこの cap を置き換えることはない（`engine/src/program/generate.cpp:12077-12080`、SYCL: `engine/sycl/src/program/generate.cpp:7097-7099`）。CUDA の paced 経路は `STRATA_PARTIAL_PIN` と `budget_bytes` による通常経路の条件分岐より先に処理される。

値は関数内 `static const uint64_t` の初期化で初回到達時に一度読み、その後の同一プロセス内の関数呼び出しでは再読込しない。実行中に環境を変更しても反映されない。CUDA/SYCL それぞれ独立した実装である（CUDA: `engine/src/core/expert_source.cpp:4446-4449`、SYCL: `engine/sycl/src/core/expert_source.cpp:1953-1956`）。

CUDA の通常経路は cap から 2 GiB ごとに候補を下げて登録を試み、成功した先頭範囲を GPU alias として記録する。残りの範囲は `lock_resident` に渡される。登録がすべて失敗しても、部分登録量 0 のまま残りを lock し、補完の準備処理を続ける。paced 経路では利用可能 RAM と reserve を見ながら 1 GiB 単位で領域を触り、その後 `got` から expert 境界に合わせて登録を試す（`engine/src/core/expert_source.cpp:4450-4566`）。

## ログと測定値

CUDA 通常経路では最終的な補完準備ログ `FileExpertSource: ... cache complement ready: resident ... GiB, pinned ... GiB in ... s...` に実際の pinned 量と note が出る。部分登録の note は `X.XX GiB of it registered for the GPU (the hottest)`。paced 経路で一部しか page-lock できない場合は `WARNING: only ... could be page-locked (...); the rest is resident but pageable, so its copies to the GPU go through the CPU (#1250)` を stderr に出す（`engine/src/core/expert_source.cpp:4513-4523,4734-4738`）。SYCL は `cache complement ready` の pinned 量と note に記録する（`engine/sycl/src/core/expert_source.cpp:2009-2018,2141-2157`）。

ソースコメントは RTX 5070 / WDDM で 40 GiB の arena に 30 GiB を登録した後、prompt path の小さなバッファを page-lock できなかった事例を挙げている。また RTX 5070 PC では 40 GiB 予算時、24 / 16 GiB 登録の 7.30 / 7.44 tok/s と未登録の 7.05–7.74 tok/s を記録し、部分登録を opt-in としている。これはコメントに記された条件での値である（`engine/src/core/expert_source.cpp:4437-4445`）。

## 根拠

- `engine/src/core/expert_source.cpp:3985-3995` — CUDA `FileExpertSource::pin_cache_complement` の開始位置。
- `engine/src/core/expert_source.cpp:4374-4402,4431-4566` — pinned allocation fallback、値の読み取り、登録経路、残りの resident lock。
- `engine/src/core/expert_source.cpp:4719-4738` — 補完状態の確定と完了ログ。
- `engine/src/program/generate.cpp:12077-12080` — generate からの呼び出し。
- `engine/sycl/src/core/expert_source.cpp:1661-1675,1871-2018,2141-2157` — SYCL 側の呼び出し先、条件、移植された登録経路、完了ログ。
- `engine/sycl/src/program/generate.cpp:7097-7099` — SYCL generate からの呼び出し。
