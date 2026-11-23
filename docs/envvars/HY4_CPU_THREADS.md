# `HY4_CPU_THREADS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の CUDA/HIP 実行経路で、ホスト RAM 上に配置した Hy4 expert を計算する CPU worker pool のスレッド数を指定する。`Runner::init` が `g.cpu_mask` が空でない場合にこの変数を読み、`CpuExperts::init` に渡す（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）。worker 数は CPU 側の expert 計算に使われ、GPU resident expert の計算数や CLI の一般 CPU pool worker 設定を直接変更するものではない（同 `hy4_graph.hip.h:2186-2189, 2211-2225, 2640-2670`）。

## 値と判定

読み取りは `getenv(...) != nullptr` で設定有無を見て、設定値を `atoi` で整数化する。文字列全体の妥当性検査、上限 clamp、空文字検査はない。`atoi` が返す値が 0 以下なら `CpuExperts::init` 内で `default_threads()` に置き換える（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1565`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:3059-3061`）。

| 条件 | unset | 有効になる値（例） | 既定値へ戻る値（例） |
|---|---|---|---|
| `g.cpu_mask` が空でない CUDA/HIP `strata-hy4` runner | `CpuExperts::default_threads()` | 正の整数（`1`, `8`） | 空文字、`0`, `-1`, `true`, `abc`, `0anything`。いずれも `atoi` の結果が 0 以下になる |

正の数値の前後にある空白や符号は `atoi` の変換規則に従い、数値の後ろに非数値があっても先頭の整数部分を使う（例: `8threads` は 8）。文字列全体を検査しないため `1.5` は 1 として扱われる。`atoi` で `int` に収まらない値の結果は C/C++ の仕様上保証されない。変換後の正数にはこの経路で上限を設けず、`start_threads` がその数の worker と scratch 領域を準備する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2054-2058, 2087-2094`）。

未設定時の既定値は `CpuExperts::default_threads()` が決める。論理 CPU 数を `host_cpus`、その半分以上を切り捨てて最低 1 とした値を `phys_cap` とし、Linux cgroup CPU quota `cg` が正で `host_cpus` 未満なら `max(1, min(phys_cap, floor(cg)-2))`、そうでなければ `phys_cap >= 28` で `phys_cap-6`、`phys_cap >= 20` で `phys_cap-2`、その他は `phys_cap` を返す（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2856-2864`）。Windows では `cgroup_cpu_limit()` は 0 を返すため quota 分岐を使わない（同 `hy4_cpu_experts.cpp:2022-2026`）。

## 有効になる条件

- `strata-hy4` がビルド対象であること。統合 CMake では `STRATA_BUILD_HY4=ON` が必要で、CUDA または HIP が必須。この環境変数の読み取りは `hy4_graph.hip.h` にあり、Metal/SYCL 実装の設定ではない（`engine/CMakeLists.txt:846-852, 884-908`）。
- モデルの expert 配置結果に CPU resident expert があり、`g.cpu_mask` が空でないこと。`load_experts_tiered` は CPU mode で RAM 配置 expert がある場合に mask を作り、tier 2 の expert をそこへ登録する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235`）。mask が空ならこの変数は読まれず、CPU worker pool もこの初期化経路では開始しない（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）。
- CPU mode は別設定 `HY4_CPU_EXPERTS` と配置条件で選ばれる。`HY4_CPU_EXPERTS` が設定されていれば `atoi(...) != 0`、未設定なら `default_cpu` が使われるため、CPU mode が無効なら本変数だけ設定しても CPU expert pool は有効にならない（`engine/src/hy4flash/run/hy4_graph.hip.h:1489-1499`）。
- CLI からこのスレッド数を上書きする引数は、この読み取り経路にない。`HY4_CPU_THREADS` は Runner 初期化中の `cpu.init(...)` に直接渡される（同 `hy4_graph.hip.h:1564-1565`）。

## 実行時の詳細

環境変数は `Runner::init` 中、CPU expert mask が空でないと確認した後に読み取られる。環境変数自体を保存する cache はないが、選んだ数は `cpu.init` から `Impl::load`、`start_threads` に渡され、初期化時に作られる worker pool の `nth` として保持される。そのため、同一プロセスで初期化後に環境変数を変更しても既存 pool のスレッド数は変わらない（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1863-1867, 2054-2058, 2087-2094`）。

CPU mode の expert 配置と CPU mask があると `cpu.init` が model path と mask を使って resident expert を読み込み、worker を起動する。推論時には hybrid 経路で GPU から expert index などを host に渡し、CPU resident または cold tier expert の候補を処理して GPU 側の結果へ加える（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583, 2186-2225, 2640-2674`）。本変数が変えるのはこの CPU pool の worker 数であり、Hy4 の router が選ぶ expert 自体を変える処理はこの設定の読取部にはない。

worker pool 起動時には `stderr` に `[cpuexp] %d pool threads...` が出て、Runner の初期化が成功すると `[hybrid] ... computed by %d CPU threads` に同じ worker 数が出る（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2087-2094`、`engine/src/hy4flash/run/hy4_graph.hip.h:1581-1583`）。`cpu.init` が失敗を返した場合は Runner の初期化が失敗し、main は `init: <error>` を `stderr` に出して終了コード 1 を返す（同 `hy4_graph.hip.h:1565`、`engine/src/hy4flash/run/hy4_main.hip.cpp:702-705`）。この失敗経路は expert 読み込み等のエラーを伝搬するもので、`HY4_CPU_THREADS` の非数値や非正値をエラーにはせず、既定値へ fallback する。

## ログと測定値

- worker 起動時: `[cpuexp] %d pool threads%s, spin %d us, sched=%d, pf=%d rows, l3_pf=%s`（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2092-2094`）。
- hybrid runner 初期化時: `[hybrid] %llu experts (%.2f GB) in host RAM computed by %d CPU threads`（`engine/src/hy4flash/run/hy4_graph.hip.h:1581-1583`）。
- `docs/DETAILS.md` の「CPU workers and thread placement」は通常 engine の `--pool-workers` の説明であり、`HY4_CPU_THREADS` の値判定や測定結果を記載していない（`docs/DETAILS.md:1348-1360`）。本変数に結び付いた条件付き測定値は確認できなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565, 1581-1583` — CPU mask 条件、環境変数の読み取り、初期化と worker 数ログ。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2856-2864, 3059-3061` — 既定 worker 数と非正値 fallback。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1863-1867, 2054-2058, 2087-2094` — worker 起動、thread 数保持、起動ログ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235` — CPU 配置 mask と tier 2 expert 登録。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1489-1499, 2186-2225, 2640-2674` — CPU mode の条件と hybrid expert 計算への適用。
- `engine/CMakeLists.txt:846-852, 884-908` — CUDA/HIP `strata-hy4` の build 条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:702-705` — Runner 初期化失敗時の表示と終了。
- `docs/DETAILS.md:1348-1360` — 関連資料との照合。
