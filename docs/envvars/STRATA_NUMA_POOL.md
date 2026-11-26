# `STRATA_NUMA_POOL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU expert pool の NUMA 分割を、Linux で NUMA node が 2 個以上あり `STRATA_NUMA_SPLIT` が未設定のときに自動で試す既定動作を止めるスイッチです。pool の構築時に `pick_numa_pool` が値を判定し、`0`、`off`、`false`、`no` のいずれかなら自動分割を選ばず、既存の pool 配置・worker 数に戻します。値を「有効」にして分割を強制する機能ではありません。`engine/include/strata/kernels/cpu/numa_pool.hpp:29-35,65-83`、`engine/src/kernels/cpu/pool.cpp:803-820,883-907`。

NUMA split が成立すると worker は node ごとの slice に割り当てられ、native expert の gate/up と down の行タスクを slice ごとに分けます。自動 split は既定 worker 数の計算を全 socket に広げる場合がありますが、明示 `--pool-workers` はその指定を維持します。補完領域を持つ実ファイル expert source では、実 node split が有効な場合に slice ごとの first-touch placement も試みます。対象は CPU expert pool の処理で、全演算や GPU pool を一律に NUMA 分割する設定ではありません。`engine/src/kernels/cpu/pool.cpp:865-881,924-977,1176-1189,1585-1597`、`engine/src/core/expert_source.cpp:624-628,669-712`。

同名は Inkling2 CUDA hybrid doorbell にも参照されますが、そこでは別の狭い判定です。`STRATA_NUMA_POOL` が文字列として厳密に `"0"` のときだけ NUMA node 数を 1 と扱い、node 別の worker CPU 選択も通常の全 CPU リストに切り替えます。`off`、`false`、`no` はこの経路では無効化値ではありません。`engine/src/inkling2/hybrid_doorbell.cu:63-84,534-543,604-627`。

## 値と判定

| 条件（build / 実行経路） | unset | 無効化する値 | その他の設定値 |
|---|---|---|---|
| CPU `ExpertPool` の自動 NUMA split 判定 | 2 node 以上かつ `STRATA_NUMA_SPLIT` 未設定なら自動で試行。node が 1 個なら従来どおり | 大文字小文字を無視した完全一致 `0`、`off`、`false`、`no` | split の強制指定にはならない。分割の自動選択条件を満たさない値は通常自動判定を妨げない |
| Inkling2 CUDA hybrid doorbell | NUMA node を検出 | 完全一致 `0` のみ | `off`、`false`、`no`、`0 `、`00` などは通常どおり node を検出 |

CPU pool 経路は `std::getenv` の null 判定後、値全体を `std::string` 化して各文字を `std::tolower` し、4 つの文字列と完全一致させます。数値変換はしません。空文字、前後の空白、`0anything`、`00`、`1`、`true` は無効化値ではありません。例えば `OFF` と `False` は無効化値ですが、` off` と `no ` はそうではありません。`engine/include/strata/kernels/cpu/numa_pool.hpp:29-35`。

pool 判定では `STRATA_NUMA_SPLIT` が null でなく空文字でもないことを「設定あり」とします。無効化値は、NUMA node が 2 個以上ある場合、または `STRATA_NUMA_SPLIT` に非空値がある場合に `Off` となり、後者では `STRATA_NUMA_SPLIT` を無効化して優先します。1 node で `STRATA_NUMA_SPLIT` も未設定なら、`STRATA_NUMA_POOL=0` であっても pool 判定は `Unchanged` となり、ログも出ません。`engine/include/strata/kernels/cpu/numa_pool.hpp:65-83`。

Inkling2 CUDA hybrid doorbell は `std::string(e) == "0"` のみを判定するため、大小文字変換・数値変換・空白除去はありません。空文字は未設定と同じ扱いです。`engine/src/inkling2/hybrid_doorbell.cu:63-66`。

## 有効になる条件

- **CPU pool の自動 split**: `STRATA_NUMA_POOL` が無効化値でなく、`STRATA_NUMA_SPLIT` が未設定または空で、検出 node 数が 2 以上であること。`STRATA_NUMA_SPLIT` に非空値があると自動選択は行われません。`engine/include/strata/kernels/cpu/numa_pool.hpp:71-83`。
- 自動試行は node 間へ worker core を交互配置してから判定します。pool は pin され、worker と（参加する場合）host を合わせて 2 thread 以上、各 thread の core / NUMA node が判明し、配置がちょうど 2 node にまたがり、slice 数が均衡している必要があります。`STRATA_EXCHANGE_ROTATE=1` も split を拒否する条件です。失敗時は自動試行前の topology に戻して従来の pool を使います。`engine/src/kernels/cpu/pool.cpp:841-903`、`engine/include/strata/kernels/cpu/numa_pool.hpp:94-149`。
- **Linux** では node 数は `/sys/devices/system/node` の CPU を持つ `nodeN/cpulist` から数えます。Linux 以外ではこの helper は node 数を 1 とし、自動 split を開始しません。Windows は別途 `STRATA_NUMA_SPLIT` / `STRATA_NUMA_ARENA` 条件の明示 split 経路を持ちますが、`STRATA_NUMA_POOL` の自動選択だけで成功する条件ではありません。`engine/src/kernels/cpu/pool.cpp:658-695`。
- 明示 `STRATA_NUMA_SPLIT=1` または `test` は既存の明示 split 経路です。`STRATA_NUMA_POOL` が無効化値であればそれを止めます。`test` は実 node placement ではなく test slice を作ります。`engine/src/kernels/cpu/pool.cpp:813-820,927-977`。
- 自動 NUMA split が有効でも、`--pool-cores` による指定が node をまたがない、pool が pin されない、slice が空になる、または実際の配置が 2 個を超える node にまたがる場合は自動試行を取り消します。`engine/src/kernels/cpu/pool.cpp:823-839,883-900`。
- Linux の `generate` は pool 構築前に `STRATA_NUMA_CARD` に基づいて process の CPU affinity を制限することがあります。また同じ初期化処理でこの変数と `STRATA_NUMA_SPLIT` を使って、card node の worker 数推定（`span_packages`）を行います。設定により pool topology や試行可能な core が変わることがあります。明示的な `--pool-workers` は worker 数の決定で優先されます。`engine/src/program/generate.cpp:4615-4625,4655-4675`、`engine/src/kernels/cpu/pool.cpp:865-881`。
- Inkling2 CUDA doorbell 側ではこの変数は doorbell が稼働する場合に影響します。条件は CUDA EP の 1 GPU、host expert が 1 個以上、`opts.cpu_threads > 0` です。該当時に node 数を決め、host expert を `key % n_numa` で node に割り当て、node pool worker を起動します。`engine/src/inkling2/ep_dual_gpu.cu:970-972,1010-1018,1037-1058`。

## 実行時の詳細

CPU pool の `ExpertPool` constructor が環境を読むたびに評価し、設定値を独自の static cache には保存しません。判定結果はその pool の構成と `g_numa_plan` に反映され、worker を起動する前に確定します。動作中に環境を書き換えても、すでに構築済みの pool / split plan は再評価されません。通常の generate 経路では `generate.cpp` が `ExpertPool` を構築します。`engine/src/kernels/cpu/pool.cpp:803-820,924-1003`、`engine/src/program/generate.cpp:9001-9008`。

自動 split が成立すると CPU pool は 2 つの `NodeSync` slice を作ります。native expert の gate/up と down の処理では各 slice に対応する行範囲と task counter を使います。実 file expert source は plan が実 node split であり test plan でない場合に限り、complement の各 slice を node-local first-touch する処理を有効にします。`STRATA_NUMA_POOL` 自体は model 選択、生成 token、CLI の worker 数を強制変更しません。`engine/src/kernels/cpu/pool.cpp:960-975,1176-1189,1585-1597`、`engine/src/core/expert_source.cpp:669-712`。

別経路の Inkling2 CUDA doorbell では同変数は helper 呼び出しごとに読み直されます。doorbell pool の開始時に node 数を計算し、各 node の worker 用 CPU を選びます。モデルの CUDA EP 初期化時に host expert を node に振り分けて doorbell pool を開始します。`engine/src/inkling2/hybrid_doorbell.cu:63-84,534-543,604-635`、`engine/src/inkling2/ep_dual_gpu.cu:970-972,1010-1018,1037-1058`。

## ログと測定値

CPU pool で無効化値が認識され、node 数が 2 以上なら stderr に `strata cpu pool: NUMA pool off (STRATA_NUMA_POOL=0): <node count> NUMA nodes found, the pool runs as before` を出します。1 node でも非空の `STRATA_NUMA_SPLIT` があるときは末尾が `one NUMA node` になります。自動 split が成立すれば `strata cpu pool: NUMA pool on: %d NUMA nodes found, one slice of the pool per node (STRATA_NUMA_POOL=0 turns it off)` を出します。自動試行が条件不足で失敗した場合は `strata cpu pool: NUMA pool off: %s (%d NUMA nodes found), the pool runs as before` を出します。1 node で特に split を選ばない経路はこの変数に関するログを出しません。`engine/include/strata/kernels/cpu/numa_pool.hpp:74-79`、`engine/src/kernels/cpu/pool.cpp:815-816,893-899,967-969`。

明示 `STRATA_NUMA_SPLIT` が有効なら後続の `NUMA split on/off` ログが出ます。Inkling2 CUDA EP は初期化要約に `doorbell=...` と `numa=%d` を出しますが、`STRATA_NUMA_POOL` の無効化理由を示す専用ログは確認できません。`engine/src/kernels/cpu/pool.cpp:927-977`、`engine/src/inkling2/ep_dual_gpu.cu:1064-1069`。

`docs/DETAILS.md` の「Two sockets and NUMA」も Linux で 2 node 以上の pool split と無効化値を説明しており、現行コードの自動 split 条件と一致します。そこにある測定値は本調査で再測定していません。`docs/DETAILS.md:1389-1407`。

## 根拠

- `engine/include/strata/kernels/cpu/numa_pool.hpp:29-35,65-83` — 値の変換・無効化値・既定選択。
- `engine/src/kernels/cpu/pool.cpp:658-695,803-820,841-907,924-1003` — node 判定、pool での読み取りと条件・ログ・worker 起動。
- `engine/src/kernels/cpu/pool.cpp:1176-1189,1585-1597` — slice task 分割の適用箇所。
- `engine/src/core/expert_source.cpp:624-712` — 実 node plan に連動する complement の配置。
- `engine/src/program/generate.cpp:4615-4675,9001-9008` — Linux の pool 前処理、値の別参照、pool 構築。
- `engine/src/inkling2/hybrid_doorbell.cu:63-84,534-543,604-635` — CUDA doorbell 経路の別判定と worker 配置。
- `engine/src/inkling2/ep_dual_gpu.cu:970-972,1010-1018,1037-1069` — doorbell 適用条件、expert node 配置と起動。
- `engine/cmake/backends/cpu.cmake:241-247`、`engine/src/inkling2/CMakeLists.txt:212-221` — CPU pool / CUDA EP の build target。
