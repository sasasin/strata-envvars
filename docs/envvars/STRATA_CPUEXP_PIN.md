# `STRATA_CPUEXP_PIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4-Flash の CPU expert pool を初期化するとき、worker thread を CPU affinity で固定するか、固定先をどの順番で並べるかを制御する。pinning が有効な場合、`pin_list()` は Windows では processor group と L3 cache、Linux では実行可能 CPU・SMT sibling・L3 domain を使って固定先候補を作り、`start_threads()` は各 worker の native handle に affinity を設定する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1880-1902,1904-2020,2087-2094`）。

対象は `hy4::CpuExperts` を使う HY4-Flash の CPU expert 経路である。HIP runner は CPU mask が空でないときに `cpu.init()` を呼び（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1566`）、SYCL の共通 expert setup は `ucx.init()` を呼ぶ（`engine/src/hy4flash/sycl/sy_graph.h:118-126,204-215`）。通常の Strata engine 全般の CPU pool pinning を制御する変数ではない。

## 値と判定

`start_threads()` は初期化ごとに `std::getenv` で読み、文字列の先頭文字だけを `'0'` と比較する。文字列全体の parse、数値変換、大文字小文字変換はしない。Linux では cgroup の CPU quota が host の論理 CPU 数より小さい場合を constrained と判定し、未設定時の pinning を省く。Windows では `cgroup_cpu_limit()` が常に 0 を返すため、この自動抑制は該当しない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2022-2050,2074-2079`）。

| 条件 | unset | 設定時に pinning 有効 | pinning 無効 |
|---|---|---|---|
| 全 platform。Linux は cgroup quota 判定あり | quota が host CPU 数未満なら無効。それ以外は有効 | 値の先頭が `'0'` 以外（例: `1`, `true`, `false`, `linear`, 空文字） | 値の先頭が `'0'`（例: `0`, `0anything`, `01`） |

先頭文字の判定は大文字小文字を問わず、空白や値全体の妥当性も検査しない。従って空文字は設定済みとして pinning を有効にする。文字列が完全に小文字の `linear` と一致する場合だけ、通常の topology-aware な分散順ではなく候補 CPU の線形順を使う（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1906-1908,1960-2008`）。`Linear` や `linear-extra` は pinning を有効にするが線形順にはならない。

## 有効になる条件

- `hy4::CpuExperts::init()` から `Impl::load()` が成功し、worker pool の初期化に到達する必要がある。pool 初期化は arena の読み込み後に呼ばれる（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1700-1730,1863-1867,3059-3062`）。
- HIP 経路では runner の CPU mask が空でない必要がある。SYCL 共通 setup は VRAM/CPU/cold の expert 配分後に CPU pool を初期化する（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1566`; `engine/src/hy4flash/sycl/sy_graph.h:173-215`）。
- Linux で quota が host CPU 数未満なら、未設定時は pinning を省く。`STRATA_CPUEXP_PIN` を設定し、先頭文字を `0` 以外にするとこの自動抑制を上書きして pinning を試みる（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2022-2050,2074-2079`）。
- 固定先一覧が空の場合（Linux の `sched_getaffinity()` 失敗、利用可能 CPU 数が `nth` より少ないなど）は affinity を設定しない。候補一覧が空である場合や `want` の件数が足りない場合は `pin_list()` が空 vector を返す（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1960-1964,2017-2020`）。
- `HY4_CPU_THREADS`（HIP runner）などで決まる worker 数は固定先数に影響するが、別の CLI 引数や環境変数がこの変数の判定を上書きする処理は確認できない（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1566, engine/src/hy4flash/run/hy4_cpu_experts.cpp:2054-2056`）。

## 実行時の詳細

環境変数は `CpuExperts::Impl::start_threads()` の各 pool 初期化時に評価され、static cache には保存されない。最初の読み取りで、値が設定されていれば先頭文字が `0` 以外か、未設定なら cgroup quota による抑制がないかを判定する。pinning を試みる場合、`pin_list()` が環境変数をもう一度読み、値が完全一致 `linear` かどうかを確認して順序を選ぶ（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1906-1908,2074-2079`）。

得られた CPU target を worker thread の生成直後に適用する。Windows は `SetThreadGroupAffinity()`、非 Windows は `pthread_setaffinity_np()` を呼ぶが、戻り値は確認しない。そのため、ログ上の `(pinned, physical cores first)` は固定先一覧が空でないことを示すもので、OS API による affinity 設定成功そのものを検証した表示ではない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1880-1893,2087-2094`）。起動後の環境変更を再読する処理はこの pool にない。

## ログと測定値

pool 初期化時に stderr へ `[cpuexp] %d pool threads%s, spin %d us, sched=%d, pf=%d rows, l3_pf=%s` を出す。固定先一覧が空でなければ suffix は ` (pinned, physical cores first)`、空なら通常 ` (not pinned)` で、cgroup quota 制約中は ` (not pinned: cgroup CPU quota)` となる。quota 制約中に pinning を明示的に有効にしても、固定先一覧を作れなかった場合の suffix は同じ quota 表示になる。設定値自体のログや、affinity API 呼び出しの失敗ログはない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2090-2094`）。

`docs/DETAILS.md` にこの変数固有の測定値は見つからなかったため、性能値は記載しない。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1880-1902` — platform ごとの affinity API 呼び出し。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1904-2020` — `linear` 判定、CPU topology からの固定先一覧、空一覧になる条件。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2022-2050,2074-2094` — cgroup quota の判定、環境変数評価、worker への適用、stderr ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1566` — HIP runner の CPU expert pool 初期化条件。
- `engine/src/hy4flash/sycl/sy_graph.h:118-126,173-215` — SYCL の CPU/RAM expert 配分と pool 初期化。
