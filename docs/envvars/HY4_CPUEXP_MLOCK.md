# `HY4_CPUEXP_MLOCK`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の CPU expert 用 arena を確保した後、ページをメモリからスワップアウトされないようロックするかを指定する。`1` で始まる値はロックを要求し、未設定なら空き RAM に余裕がある場合だけ要求する。ロックは best effort で、失敗しても arena の確保や CPU expert の処理を失敗扱いにはしない。読み取りと arena 確保は `hy4::CpuExperts::Impl::alloc_arena` にある（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1583-1629`）。

## 値と判定

`std::getenv` で設定有無を見た後、設定値は文字列全体でなく先頭 1 文字だけを `1` と比較する。数値変換、空白除去、大文字小文字変換、後続文字の検査はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Windows / POSIX 系。arena サイズが 0 ではない場合 | 物理的な空き RAM が arena サイズ + 16 GiB を**超える**場合にロックを要求。それ以外は要求しない | `1`, `10`, `1anything` | 空文字、`0`, `01`, `true`, ` 1` |

設定済みで先頭が `1` 以外なら、自動判定は行わずロック要求を無効にする。したがって空文字も「明示的に無効」として扱われる。値が `1` で始まれば残りの文字列は問わない。POSIX では `/proc/meminfo` の `MemAvailable` を読み、Windows では `GlobalMemoryStatusEx` の `ullAvailPhys` を使う。空き RAM の取得に失敗した場合は比較条件を満たさず、自動ロック要求は無効のままになる（同 `:1591-1609`）。

## 有効になる条件

- `alloc_arena` が呼ばれ、arena サイズが 0 でないこと。モデルと配置で CPU resident expert がない場合も arena サイズは 4096 bytes に補われるため、初期化経路からこの関数が呼ばれれば判定対象になる（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1583-1590,1700-1731`）。
- 実際のロック要求は、Windows では `VirtualLock`、POSIX 系では `mlock` が成功したときだけ成立する。OS の制限などで失敗しても結果は `locked = false` となり、その失敗は無視される（同 `:1611-1629`）。
- HIP の Hy4-Flash 経路では CPU expert mask が空でないときに `CpuExperts::init` を呼ぶ。モデルの expert tier 配置と CPU モードが CPU resident expert の有無を決める（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235`、`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）。
- SYCL の unified expert 構成では `setup_experts_unified` が CPU mask を作り `ucx.init` を呼ぶ。RAM arena のサイズは CLI `--ram-experts-gb` が正ならそれを使い、そうでなければ `HY4S_RAM_BUDGET_GB`、さらに未設定ならシステム RAM から算出した予算で決まるため、自動ロックの 16 GiB 判定にも影響する（引数の読み取り: `engine/src/hy4flash/sycl/sy_main.cpp:103,140-141`; 予算・mask: `engine/src/hy4flash/sycl/sy_graph.h:162-200,214`）。
- `HY4_CPUEXP_MLOCK` はこの arena のページロックだけを切り替える。隣接する `STRATA_CPUEXP_COLLAPSE` は Linux の THP collapse 要求を別途制御し、ロック要求の値判定や失敗処理を上書きしない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1591-1629,1786-1817`）。

## 実行時の詳細

環境変数は `alloc_arena` ごとに一度読み取られる。初期化後にプロセス環境を変更しても、確保済み arena のロック状態は再評価されない。CLI 引数や他の環境変数で `HY4_CPUEXP_MLOCK` の値を上書きする処理は確認できない。unset の場合だけ RAM 余裕の自動判定を使い、何らかの値が設定されていればその先頭文字の結果で自動判定を置き換える（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1591-1609`）。

POSIX 系では arena を `mmap` で確保してから、要求時に `mlock(arena, bytes)` を呼ぶ。Windows では `VirtualAlloc` の後に要求時 `VirtualLock(arena, bytes)` を呼ぶ。ロック成否は `Impl::locked` に保存され、`CpuExperts::arena_locked()` から取得できるが、通常の初期化ログにはこの値を出していない（同 `:1611-1629`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:3080-3083`）。ロックに失敗しても arena は保持され、CPU expert pool の初期化は続く。arena 自体の `mmap` / `VirtualAlloc` が失敗した場合は別経路で初期化が失敗する（同 `:1612-1621`）。

## ログと測定値

この変数の値、ロック要求、`mlock` / `VirtualLock` の成否を示すログはない。HY4 HIP 側は CPU expert 初期化が失敗した場合に呼び出し元へエラーを返し、成功時は arena サイズや thread 数を `[hybrid] ...` 行に出すが、ロック状態は含めない（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1583`）。SYCL 側も初期化失敗時に `experts: ...` を stderr に出し、成功時の `[experts] unified pool ...` 行にはロック状態を含めない（`engine/src/hy4flash/sycl/sy_main.cpp:298-306`、`engine/src/hy4flash/sycl/sy_graph.h:214-235`）。ロックの性能差を示す条件付き測定値は、参照した `docs/DETAILS.md` に見つからなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1583-1629` — 環境変数判定、unset 時の空き RAM 判定、platform ごとのロック呼び出しと失敗の扱い。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1700-1731` — expert mask から arena サイズを計算し、空の場合のサイズ補完と確保呼び出し。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1786-1817` — 同じ arena に対する独立した Linux THP collapse 処理。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235`、`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583` — HIP 経路の CPU expert 条件と初期化・ログ。
- `engine/src/hy4flash/sycl/sy_main.cpp:103,140-141,298-306`、`engine/src/hy4flash/sycl/sy_graph.h:162-200,214-235` — SYCL の CLI 引数、RAM 予算・mask・初期化・ログ。
