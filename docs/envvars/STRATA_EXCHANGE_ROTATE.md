# `STRATA_EXCHANGE_ROTATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU の expert cache を adaptive swap するとき、RAM の resident complement と交換バッファ間で expert の所有位置を更新し、通常経路で行う host 側の commit memcpy を省く rotation を要求する。CUDA/HIP 系の `engine/src/core/expert_source.cpp` と SYCL 系の `engine/sycl/src/core/expert_source.cpp` が、交換バッファを確保する時に値を読む。rotation が有効な場合、`commit_exchanges` / `commit_flip` は `ExchangeStorage` の所有権表を更新し、通常の complement への memcpy 経路を通らない（`engine/src/core/expert_source.cpp:4806-4851,4903-4925,5122-5140`; SYCL: `engine/sycl/src/core/expert_source.cpp:2219-2279,2302-2326,2329-2362`）。

同じ名前を CPU pool も独立して読む。ここでは rotation を有効化せず、rotation 中に expert slot が固定されないため NUMA split を拒否する判定に使う（Linux/Windows: `engine/src/kernels/cpu/pool.cpp:671-694`; 判定: `engine/include/strata/kernels/cpu/numa_pool.hpp:94-109`）。

## 値と判定

GPU 側は環境変数の文字列全体を `strcmp(value, "1")` で比較する。未設定・空文字・`0`・`true`・`01`・`1anything` は要求扱いにならず、`1` だけが要求となる。空白除去、数値変換、大文字小文字変換はしない。CPU pool の抑止判定も同じ完全一致である。

| 実行経路 | unset | rotation / 抑止が要求される値 | 要求されない値 |
|---|---|---|---|
| CUDA/HIP 系 `FileExpertSource` | off。通常の copy path | `1` | 空文字、`0`、`true`、`01`、`1anything` など |
| SYCL `FileExpertSource` | off。通常の copy path | `1` | 空文字、`0`、`true`、`01`、`1anything` など |
| Linux/Windows CPU pool の NUMA split 判定 | rotation を理由とする拒否なし | `1` なら split を拒否 | 上記以外 |

GPU 側の読み取りは `reserve_exchanges` が容量不足を処理する時だけ行われる。既に確保済み容量以下の要求は関数冒頭で成功を返すため、環境変数を再評価しない（CUDA/HIP: `engine/src/core/expert_source.cpp:4786-4807`; SYCL: `engine/sycl/src/core/expert_source.cpp:2198-2220`）。

## 有効になる条件

- GPU 側では resident RAM complement が利用可能で、適応型 expert swap の交換バッファを `reserve_exchanges` する実行経路に入る必要がある。例えば generate 側では `resident_ok` の後、`--adapt-async` 時または `--adapt-every` と正の `--adapt-swaps` の時に確保を試みる（`engine/src/program/generate.cpp:12166-12188`）。SYCL 側にも同様の確保条件がある（`engine/sycl/src/program/generate.cpp:7117-7129`）。この変数自体は CLI 引数を設定・上書きしない。
- CUDA/HIP 系は、expert の各層サイズから算出した rotation 用サイズが有効で `size_t` に収まり、complement が全体として page-locked かつ mapped で、partial でなく、host/device pointer と正の complement byte 数を持つことが必要。交換バッファも mapped/page-locked として確保でき、device alias の取得と `ExchangeStorage::initialize_sized` が成功する必要がある（`engine/src/core/expert_source.cpp:4808-4849`）。
- SYCL 系は上記に加えて全層の expert block サイズが同一であることを要求する。交換バッファの host allocation、device pointer と `ExchangeStorage::initialize` が必要（`engine/sycl/src/core/expert_source.cpp:2221-2277`）。
- 条件を満たさない場合、通常の交換バッファを確保して copy path を維持する。`1` が設定されているときは stderr に `FileExpertSource: exchange rotation unavailable; retaining copy path: <reason>` を出す。条件を満たす場合は stderr に `FileExpertSource: exchange buffer rotation enabled: ...; no host commit memcpy` を出す（CUDA/HIP: `engine/src/core/expert_source.cpp:4814-4850`; SYCL: `engine/sycl/src/core/expert_source.cpp:2225-2277`）。
- CPU pool では、Linux の自動 NUMA pool の split 判定、または Windows で `STRATA_NUMA_ARENA=1` / `STRATA_NUMA_SPLIT=1` により multi-node split 判定を行う場合に、値 `1` が split を拒否する理由となる。拒否理由は `STRATA_EXCHANGE_ROTATE=1 moves experts between slots, the split needs fixed slots`。他の split 条件も必要で、Linux/Windows 以外ではこの split 判定自体が使われない（`engine/src/kernels/cpu/pool.cpp:671-694`; `engine/include/strata/kernels/cpu/numa_pool.hpp:97-109`）。

## 実行時の詳細

GPU 側では環境をプロセス起動時に一括 cache するのではなく、`reserve_exchanges` 内で交換容量を初めて（または既存容量を超えて）確保するときに読み取る。通常の初期化ではこれが適応型交換設定に応じた準備時の評価となる。いったん必要量を確保すると、後の容量以下の呼び出しは早期 return するため、プロセス実行中に環境を変更してもその容量では反映されない。rotation が初期化済みの場合、既存領域に resident expert が入り得るので後から容量を増やす要求は失敗し、`FileExpertSource: reserve maximum exchange capacity before enabling rotation` を返す（`engine/src/core/expert_source.cpp:4786-4793`; SYCL: `engine/sycl/src/core/expert_source.cpp:2198-2205`）。

rotation が有効なら、交換対象 expert の新しいデータは交換バッファに stage され、commit 時に `ExchangeStorage::commit` で slot の所有関係を移す。generate の非 arena adaptive path は RAM copy 段階を飛ばし、flip を行う（`engine/src/program/generate.cpp:15900-15917`）。有効でない場合は従来どおり complement へ `memcpy` してから cache の対応を入れ替える（`engine/src/core/expert_source.cpp:4903-4925`; SYCL: `engine/sycl/src/core/expert_source.cpp:2302-2326`）。rotation commit の整合性検査に失敗すると stderr に `FileExpertSource: invalid exchange rotation commit; refusing corrupt residency` を出して `abort` する（CUDA/HIP: `engine/src/core/expert_source.cpp:4910-4915`; SYCL: `engine/sycl/src/core/expert_source.cpp:2306-2311`）。

CPU pool の値は NUMA split の判定時に `getenv` で読み取られ、split plan を作る段階で使われる。これは GPU 側の読み取りとは別経路である（`engine/src/kernels/cpu/pool.cpp:673-694,883-899,924-977`）。

## ログと測定値

GPU 側は未設定または `1` 以外なら rotation 関連ログを出さない。値 `1` で有効になると初期化成功ログ、条件不成立なら前節の unavailable ログを stderr に出す。serve の終了時には rotation が active の場合に限り、累積値を `strata serve: exchange rotation: %llu blocks, %llu host memcpy bytes avoided (cumulative payload)` と stderr に出す（`engine/src/program/generate.cpp:23821-23824`; SYCL serve: `engine/sycl/src/program/generate.cpp:13227`）。CPU pool の split が拒否された場合は `strata cpu pool: NUMA split off: <reason>` または自動 pool では `strata cpu pool: NUMA pool off: <reason> (<n> NUMA nodes found), the pool runs as before` を stderr に出す（`engine/src/kernels/cpu/pool.cpp:893-899,944-977`）。

この文書では性能値を記載しない。既存の測定資料は実装条件の根拠にはせず、ここでは調査時に build や GPU 実行を行っていない。

## 根拠

- CUDA/HIP 系の値判定、eligibility、allocation、診断: `engine/src/core/expert_source.cpp:4786-4852`
- CUDA/HIP 系の stage / commit と通常 copy fallback: `engine/src/core/expert_source.cpp:4863-4875,4903-4929`
- SYCL 系の値判定、サイズ制約、eligibility、allocation、診断: `engine/sycl/src/core/expert_source.cpp:2198-2279`
- SYCL 系の stage / commit と通常 copy fallback: `engine/sycl/src/core/expert_source.cpp:2288-2327,2340-2362`
- adaptive exchange の確保条件: `engine/src/program/generate.cpp:12166-12188`; `engine/sycl/src/program/generate.cpp:7117-7129`
- Linux/Windows CPU pool の独立した読み取りと条件: `engine/src/kernels/cpu/pool.cpp:671-694`; `engine/include/strata/kernels/cpu/numa_pool.hpp:94-109`
