# `STRATA_ARENA_LOCK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena（ホスト側の RAM に置いた expert 重み）を、GPU に page-lock できなかった部分について、OS 側で resident に保つかどうかを決める。Strata は `cudaHostRegister`（HIP では `hipHostRegister`）で arena を page-lock しようとし、それが失敗するか上限で切られた場合、残りの領域を `strata::platform::lock_resident()` で lock する（Windows: プロセスの minimum working set を上げて `VirtualLock`、Linux: `mlock`）。

この lock は DMA を可能にするものではない。GPU が直接読めるのは `registered_bytes`（登録できた prefix）だけで、lock された領域は CPU 側の expert pool が読む分として物理 RAM に留まる。実装注釈は、lock しないと Windows が memory pressure の下で arena を trim し、CPU pool の速度が OS 依存になる、と説明している（`src/core/pinned.cu:439-441`、`include/strata/platform/memory.hpp:3-6`）。

読み取り箇所は `src/core/pinned.cu` の 3 箇所と、その SYCL 移行コピー `sycl/src/core/pinned.dp.cpp` の対応 3 箇所のみ。Python サーバー・setup・同梱ツールはこの名前を読まない。

## 値と判定

`std::getenv("STRATA_ARENA_LOCK")` の結果を、`nullptr` か、文字列全体が `"0"` と等しいかで判定する。`atoi`、先頭文字比較、大小文字の正規化はない。

| 状態 | 判定 |
|---|---|
| 未設定（`nullptr`） | lock を実行（既定） |
| `"0"` | lock をスキップ |
| 空文字 `""` | lock を実行（`std::string("") != "0"`） |
| `"1"`, `"true"`, `"false"`, `"00"`, `"0x"`, `" 0"`, `"0anything"` | lock を実行（`"0"` と完全一致しない） |

判定式は `env == nullptr || std::string(env) != "0"`（`src/core/pinned.cu:417,445,488`）。したがって「`0` だけが無効」で、他のあらゆる文字列は有効（lock 実行）側になる。

値が `"0"` でも、lock 自体が走らない条件（下の「有効になる条件」）がある。

## 有効になる条件

この変数は、arena の登録が不完全だったときだけ参照される。

- `cudaHostRegister` が成功して arena 全体が登録された場合（`registered_bytes == bytes`）、lock 分岐には入らない。変数は読まれない。
- `backing == PageBacking::LargePages` の場合、値に関係なく lock は実行されない。large pages は paging されないため、という注釈がある（`src/core/pinned.cu:415-416,443-444,486-487`）。Linux では `MAP_HUGETLB` が成功したとき、Windows では `MEM_LARGE_PAGES` が成功したときこの backing になる。
- `STRATA_ARENA_MMAP=1`（Linux）で選ばれる file mapping の arena は `PinnedArena` を使わない。その note は "not locked, not pinned" と言い、この変数は効かない（`src/core/expert_source.cpp:4454-4476`）。

読み取り箇所は 3 経路に分かれる。

1. 全体登録の失敗、または cap による sliced fallback の remainder（`src/core/pinned.cu:413-423`）。cap は `max_pinned_bytes`（multi-GPU under WDDM、remote experts）か `STRATA_ARENA_PIN_GIB`（`arena_pin_cap_gib()`、`src/core/pinned.cu:299-305`）。Windows で `STRATA_ARENA_PIN_GIB=auto` の場合、`sliced_pin_limit()` が limit を決める（`src/core/pinned.cu:314-336`）。
2. `bounds.size() < 2` の場合（登録失敗時の "the arena is NOT pinned, so copies will be slow" 分岐、`src/core/pinned.cu:424-452`）。エンジンの arena は layer ごとに bounds を持つので `n_layers >= 1` で常に size >= 2（`src/core/expert_source.cpp:4522-4528`）。この分岐は bounds なしで arena を作る同梱ツール（`strata-load`、`strata-overlap`、`strata-concurrent`）の経路で到達する。
3. `register_slices()` の deferred registration（`src/core/pinned.cu:484-493`）。Windows で `STRATA_DEFERRED_REGISTER` が有効なときだけこの経路が使われる（`src/core/expert_source.cpp:4535-4542`）。

「arena lock disabled (STRATA_ARENA_LOCK=0)」という note が出るのは 2 の分岐だけ。1 と 3 は無効時に note を何も追加しない（lock の結果文字列だけが付く）。

同じ名前の判定は SYCL 移行コピーにもあるが、そのファイルでは `cudaHostRegister` が DPCT により `0 != 0` に置換され、常に「成功」扱いになる。そのため SYCL ビルドで lock 分岐に到達するのは capped 経路（`STRATA_ARENA_PIN_GIB=N` など）のときだけである（`sycl/src/core/pinned.dp.cpp:384-396,418-426,453-463,550-559`）。CUDA/HIP は `src/core/pinned.cu` をそのまま使う（`CMakeLists.txt:293`、`cmake/hip_backend.cmake:114-121`）。

## 実行時の詳細

読み取りは arena の構築時（モデルロード時）に各箇所で `std::getenv` を呼ぶ。`static` cache はなく、arena ごとに判定される。Python サーバーは `dict(os.environ)` を engine 子プロセスへ渡すので、サーバーの環境に設定した値は engine に届く（`serve/server.py:2557,671-672`）。

`lock_resident()` の実装:

- Windows（`src/platform/memory.cpp:23-60`）: `GetProcessWorkingSetSizeEx` で現在の min/max を取り、minimum を `bytes + 512 MiB` に上げて `SetProcessWorkingSetSizeEx`（hard limit flags は DISABLE）。その後 1 GiB chunk で `VirtualLock`。途中で失敗した場合は `locked_bytes` は要求より少ない（partial success を隠さず報告）。`p == nullptr || bytes == 0` は "nothing to lock"。
- Linux（`src/platform/memory.cpp:121-129`）: `mlock(p, bytes)`。失敗時は `locked_bytes = 0`、note は "mlock failed (raise ulimit -l)"。成功時は要求どおり全部。
- 解放は arena destructor で `unlock_resident()`（`src/core/pinned.cu:498-511`）。Windows の `unlock_resident` は `VirtualUnlock` だけで、working set minimum は元に戻さない（`src/platform/memory.cpp:62-67`）。

lock された領域は `PinnedArena::locked_bytes` に記録され、`note` の先頭に lock の結果文字列が前置される（`note = lr.note + "; " + note`）。この note はエンジンの起動時 print に出る: `strata generate: expert arena: <note>`（`src/program/generate.cpp:4723`、`note_ = a->note` は `src/core/expert_source.cpp:4649`）。同梱ツール `strata-load` は `backing: <note>` として出す（`src/core/load_main.cpp:57`）。

この変数は他の lock 使用箇所には影響しない。file tier の complement arena の lock（`src/core/expert_source.cpp:3016-3018`）と PLE table の lock（`src/kernels/ngram.cpp:342-343`）は `lock_resident()` を無条件で呼ぶ。

## 観測できる結果

note に現れる文字列（実装上の文言）。

- lock 実行時（Windows 成功）: `locked <N> MiB via working-set minimum + VirtualLock`
- lock 実行時（Linux 成功）: `mlock`
- lock 失敗（Linux）: `mlock failed (raise ulimit -l)`
- lock 失敗（Windows）: `GetProcessWorkingSetSizeEx failed (error <n>)`、`SetProcessWorkingSetSizeEx(<n> MiB) failed (error <n>)`、`VirtualLock stopped at <x> of <y> MiB (error <n>)`、`nothing to lock`
- 無効（`"0"`）: `arena lock disabled (STRATA_ARENA_LOCK=0); ` — bounds なし経路のみ
- large pages: `large pages are resident without a lock; ` — 値によらずこの文言

エラーや終了は発生しない。判定結果は起動時の arena note として見えるだけで、lock 失敗も警告ではなく note の一部である。

## docs との照合

`docs/` に `STRATA_ARENA_LOCK` の記載はない（リポジトリ全体でこの名前は `src/core/pinned.cu` と `sycl/src/core/pinned.dp.cpp` にしか出現しない）。設計意図はコード注釈にある: plan v0.3 P0.1 の "A/B arm" として `STRATA_ARENA_LOCK=0` が挙げられ、`include/strata/platform/memory.hpp:3-6` に「Windows が 31.6 GiB の arena を register を拒否し、lock していない arena は memory pressure で trim され、CPU pool が run ごとに 2x 振れた」とある。これはヘッダの注釈であり、測定環境（機種・OS・モデル・回数）は示されていない。

## 根拠

- 読み取り: `src/core/pinned.cu:414,442,485`、`sycl/src/core/pinned.dp.cpp:454,494,551`
- 判定式と note 文言: `src/core/pinned.cu:417,445,488`、`src/core/pinned.cu:450`、`src/core/pinned.cu:416,444,487`
- lock の実装（Windows/Linux）: `src/platform/memory.cpp:23-60,121-129`、解放 `src/platform/memory.cpp:62-67,131-133`
- `LockResult` と `locked_bytes` の意味: `include/strata/platform/memory.hpp:14-24`、`include/strata/core/pinned.hpp:36`
- 経路 2 がツール専用になる理由: `src/core/expert_source.cpp:4522-4528`、`src/core/load_main.cpp:52-57`、`src/core/overlap_main.cpp:69`、`src/core/concurrent_main.cpp:82`
- 経路 3 の条件: `src/core/expert_source.cpp:4535-4542,4571-4577`
- cap と `STRATA_ARENA_PIN_GIB` の関係: `src/core/pinned.cu:299-305,314-336,367-375`
- large pages の backing: `src/core/pinned.cu:89-113`（Windows）、`src/core/pinned.cu:205-234`（Linux）
- 起動時 print: `src/program/generate.cpp:4723`、`src/core/expert_source.cpp:4649`
- 影響しない lock 使用箇所: `src/core/expert_source.cpp:3016-3018`、`src/kernels/ngram.cpp:342-343`
- 設計注釈: `src/core/pinned.cu:439-441`、`include/strata/platform/memory.hpp:3-6`
