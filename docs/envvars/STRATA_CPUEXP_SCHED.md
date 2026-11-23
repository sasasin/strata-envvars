# `STRATA_CPUEXP_SCHED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の CPU expert worker pool で、gate/up・down projection・combine の実行スケジュールを切り替える。`sched == 1` のときは dataflow 経路、それ以外は gate/up、down、combine の各段で worker 全体を barrier で同期する経路になる。行列計算、slot 順の重み付き combine の式はどちらの経路にもあり、この変数が CPU expert の割り当て自体や GPU 側の expert 配置を変更するものではない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1535,2445-2469,2657-2686`）。

環境変数を読むのは `CpuExperts::Impl::start_threads`。この実装は `strata-hy4` に含まれ、Strata の build 設定に応じて CUDA または HIP の HY4 runner に組み込まれる（`engine/CMakeLists.txt:884-908`）。runner は CPU mask が空でない場合に `cpu.init` を呼び、CPU worker pool を開始する（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）。

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば `std::atoi` の結果を `sched` に代入する。空文字も「設定あり」であり、`atoi("")` は `0` になる。文字列全体の検証、大文字小文字の比較、範囲チェック、clamp は行わない。`atoi` が先頭の空白と符号の後の数字列を変換し、数字が始まらない文字列は `0` になるため、後続の文字は無視される。結果として dataflow を選ぶ条件は変換結果が厳密に `1` であることだけ（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2060-2061,2657`）。

| 条件 | unset | dataflow になる例 | dataflow にならない例 |
| --- | --- | --- | --- |
| `STRATA_CPUEXP_SCHED` が設定済み | 該当なし | `1`, `01`, `+1`, `1anything`（いずれも `atoi` 結果が 1） | 空文字, `0`, `0anything`, `2`, `-1`, `true`, ` 1x` はそれぞれ結果が 0 または 1 以外 |
| `STRATA_CPUEXP_SCHED` が未設定 | `nth >= 8` なら dataflow (`1`)、`nth < 8` なら barriered (`0`) | `nth >= 8` | `nth < 8` |

有効値を設定した場合は worker 数にかかわらず `sched` がその値で上書きされる。`HY4_CPU_THREADS` は runner が `CpuExperts::init` に渡す `nth` を指定し、変数が unset の場合の `nth >= 8` 判定に間接的に影響する。明示された `STRATA_CPUEXP_SCHED` はこの既定判定より優先される。`STRATA_CPUEXP_SCHED` に対応する CLI 引数はこの実装・呼び出し経路にない（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1565`）。

## 有効になる条件

- `strata-hy4` が CUDA または HIP の HY4 runner としてビルドされ、CPU expert 実装が組み込まれていること（`engine/CMakeLists.txt:884-908`）。
- runner の `g.cpu_mask` が空でなく、`cpu.init` が成功して worker pool が起動していること（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）。CPU mask の対象は hybrid 経路で CPU 側に割り当てられた expert で、decode 時にも GPU shared/V-cache 対象を除き tier 2 以上の expert が CPU pair になる（`engine/src/hy4flash/run/hy4_graph.hip.h:2303-2315`）。
- 実際の job に CPU pair があり `CpuExperts::submit` されること。CPU pair がなければ runner は CPU job を submit しない（`engine/src/hy4flash/run/hy4_graph.hip.h:2323-2325`）。
- job が cold expert を含むと `run_job` は `cold_job` 専用の wave/barrier 経路を先に実行して `continue` するため、`sched == 1` の dataflow 分岐はその job では使われない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2195-2202,2247-2255,2616-2655,2657-2663`）。

## 実行時の詳細

設定値は `CpuExperts::Impl::load` の中で `start_threads(n_threads)` が呼ばれたときに読み取られる。runner が `cpu.init` を再度呼べば再読込されるが、通常の job ごとには読み直さず、読み取った値は `Impl::sched` に保持される。したがって同一 pool の起動後にプロセス環境を変更しても既存 pool には反映されず、再初期化後の pool で読み直される（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1863-1867,2054-2063`）。

unset 時の `nth` は `HY4_CPU_THREADS` が設定されていればその `atoi` 値、なければ `CpuExperts::default_threads()` の値。後者はホスト論理 CPU 数と cgroup CPU quota を使って worker 数を決めるため、`nth >= 8` が既定スケジュール選択の境界になる（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1565`; `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2856-2864`）。

dataflow (`sched == 1`) は gate/up unit を全 expert 分処理した後、各 expert の gate/up 完了カウンタを待ってその expert の down unit を処理する。各列 chunk の down 処理を最後に終えた worker が、その chunk の combine を行い、最後に worker barrier を 1 回通る。barriered 経路は gate/up 完了後、down 完了後、combine 完了後にそれぞれ全 worker を barrier で同期する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2445-2469,2657-2686`）。両方の combine は token の slot 順に重み付き和を計算し、`J.accum` に応じて出力へ加算または上書きする（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2409-2424,2426-2442`）。

## ログと測定値

worker pool 起動ごとに stderr に `[cpuexp] %d pool threads%s, spin %d us, sched=%d, pf=%d rows, l3_pf=%s\n` を出力し、設定後の整数 `sched` が表示される。設定値が不正でも専用の警告・エラー・fallback はなく、`sched` が 1 以外なら barriered 経路になる。起動ログ以外にこの変数専用のログはない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2092-2095,2657-2663`）。

Strata の `docs/DETAILS.md` にはこの変数の説明や、このスケジューラの比較測定値は見当たらない。性能差はこの調査では測定していない。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1533-1535` — `sched` の状態と意味。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2054-2063` — worker pool 初期化時の読み取り、`atoi`、unset 時の既定値。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2092-2095` — stderr の起動ログ。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2195-2255,2445-2469,2616-2686` — cold job 分岐、dataflow と barriered の処理。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565,2303-2325` — CPU pool の初期化・worker 数・job submit 条件。
- `engine/CMakeLists.txt:884-908` — HY4 runner が CUDA または HIP でビルドされ CPU expert 実装を含むこと。
