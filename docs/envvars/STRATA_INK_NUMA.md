# `STRATA_INK_NUMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Linux で Inkling CUDA エンジンがホスト側 expert arena を割り当てるとき、オンライン NUMA node が複数あれば、その arena のページ配置に `MPOL_INTERLEAVE` を指定します。未設定時はこの NUMA 指定をしません。GPU 上の expert 配置や CPU worker の node 分割を選ぶ変数ではありません。実装は `InkHybridEngine::numa_all_nodes_mask` と `alloc_host_arena` です（`engine/src/inkling2/cuda/ink_hybrid.cuh:1489-1532`）。

## 値と判定

Linux ビルドでは `std::getenv` の結果を `nullptr` かどうか確認した後、文字列の先頭 1 文字だけを `'1'` と比較します。文字列全体の数値変換・真偽値変換はなく、大文字小文字や後続文字は判定に関係しません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1493-1498`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux | 無効 | `1`, `1anything`（先頭が文字 `1`） | 空文字、`0`, `01`, `true`, ` 1` |
| Linux 以外 | 無効 | なし | すべて（環境変数を読むコードがコンパイルされない） |

Linux で先頭が `1` でも、`/sys/devices/system/node/online` を開けない、node 番号を読み取れない、または有効な node が 1 個以下なら mask は 0 となり NUMA 指定は行いません。読み取った node list は node 62 まで mask に含め、mask が複数 bit のときだけ返します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1498-1521`）。

## 有効になる条件

- Inkling の CUDA エンジンを使う経路であること。この環境変数の参照は `engine/src/inkling2/cuda/ink_hybrid.cuh` に 1 箇所だけあり、他 backend に同名の読み取りはありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1495-1497`）。
- モデル読み込み時にホスト側 expert arena の割り当てが必要であること。native Strata loader は `n_host_experts > 0` かつ `host_used > 0` のとき、もう一方のモデル loader は `uh > 0` のとき `alloc_host_arena` を呼びます（`engine/src/inkling2/cuda/ink_runner.cuh:497-529`, `1420-1429`）。expert が VRAM に収まり arena が不要なら読み取りません。
- Linux で先頭文字が `1` で、オンライン node mask に複数 node があること（`engine/src/inkling2/cuda/ink_hybrid.cuh:1495-1521`）。条件を満たさない場合は通常の arena 割り当てへ進みます。
- `STRATA_INK_PIN_GB` は同じ arena の page-locked allocation 判定に別途使われます。`STRATA_INK_NUMA` の文字判定を上書きする分岐はありません。NUMA mask ができると、pinned allocation を試す前に `set_mempolicy` を呼びます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1524-1547`）。

## 実行時の詳細

変数はリクエストごとではなく、`alloc_host_arena` が呼ばれるモデル読み込み時に評価されます。`numa_all_nodes_mask` 自体は `static` 関数ですが、環境値や mask を保存する static cache はありません。arena を割り当てるたびに環境変数と sysfs node list を読み直すため、同一プロセスで後から別モデルを読み込む場合、その呼び出し時点の値が使われます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1493-1529`）。

複数 node の mask ができると、まず `syscall(SYS_set_mempolicy, MPOL_INTERLEAVE, ...)` を呼び、その戻り値を確認せずに続行します。pinned allocation に成功すればそのポインタを返し、RAII destructor が thread の policy を `MPOL_DEFAULT` に戻します。pinned allocation を使わず pageable arena を `mmap` した場合は、最初の page access より前に `SYS_mbind` でも interleave を指定します。両 syscall の失敗は検査されず、失敗時の fallback 分岐や専用エラーはありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1527-1532`, `1541-1568`）。

この変数は arena のメモリ配置指定だけに使われます。読み取り値を子プロセスへ転送する処理やリクエスト単位の変更はありません。arena 自体を確保できずポインタが null の場合、loader は `cannot allocate host expert arena` をエラーとして返しますが、NUMA syscall の成否とは別の経路です（`engine/src/inkling2/cuda/ink_runner.cuh:526-530`, `1420-1429`）。

## ログと測定値

mask が複数 node から得られた場合、syscall 成功の確認前に stderr へ次の行を出します（mask は小文字 hex 表記です）。そのため、このログは syscall 成功を示しません。

```text
[InkHybrid] host expert arena: pages interleaved over the NUMA nodes (mask 0x%lx)
```

mask が 0 の場合、この NUMA 用ログは出ません。arena 割り当て後には pinned / pageable 経路それぞれの通常ログも出ます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1530-1533`, `1543-1554`, `1571-1572`）。ソースコメントには 2-socket EPYC で `21.7 vs 21.4 tok/s` とありますが、モデル、backend、設定、測定方法の条件が示されていないため、性能値としては扱いません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1497`）。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:1489-1521` — 対象機能、Linux guard、先頭文字判定、online node list の読み取りと mask 作成。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1524-1573` — mask の評価、NUMA policy syscall、ログ、pinned / pageable arena の割り当て。
- `engine/src/inkling2/cuda/ink_runner.cuh:497-529` — native Strata loader で host expert arena が必要になる条件。
- `engine/src/inkling2/cuda/ink_runner.cuh:1420-1429` — 別 loader 経路で arena を割り当てる条件と allocation failure。
