# `STRATA_ARENA_PIN_GIB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena（ホスト RAM 上の expert 重み）を `cudaHostRegister`（HIP では `hipHostRegister`）で page-lock する量の上限（GiB）を決める。#243 の設定。

arena 全体が登録できるか、何 GiB まで登録されるかで、GPU が直接読める領域（`registered_bytes` の prefix）が決まる。登録された prefix 内の expert だけが arena から直接 DMA でき、prefix の外は staging ring 経由のコピーになる（`src/prefill/prefill.cpp:3649,3669-3675`、`src/core/expert_source.cpp:4707-4720`）。登録されなかった残りは `STRATA_ARENA_LOCK` の lock 対象になる（`src/core/pinned.cu:413-422`）。

読み取り箇所は `src/core/pinned.cu` の `arena_pin_cap_gib()`（`src/core/pinned.cu:299-305`）と `src/program/generate.cpp:4707`、その SYCL 移行コピー `sycl/src/core/pinned.dp.cpp:305-311` と `sycl/src/program/generate.cpp:4208`。Python サーバー・setup・同梱ツールはこの名前を直接読まない（サーバーは `dict(os.environ)` を engine 子プロセスへ渡すので、サーバー環境の値は engine に届く: `serve/server.py:2554-2565,671-672`）。

## 値と判定

`std::getenv` の結果を int に変換する。判定順は次のとおり。

| 状態 | `arena_pin_cap_gib()` の返り値 | 意味 |
|---|---|---|
| 未設定（`nullptr`） | `-1` | 上限なし（engine が決める） |
| 空文字 `""` | `-1` | 未設定と同じ |
| 文字列全体が `auto`（大小文字区別あり） | `-2` | Windows の shared-memory budget で sliced pin を上限（後述） |
| `atoi` が負を返す値（例 `-5`） | `-1` | 未設定と同じ |
| `atoi` が 0 を返す値（`0`、`abc`、`0x10`、`0.7`） | `0` | 明示的な「上限なし」＝ arena 全体を pin |
| `atoi` が正を返す値（`5`、`5x`、` 5`、`+5`、`5.7`） | その整数 | 最大 N GiB |

- 変換は `std::atoi`（`src/core/pinned.cu:303`）。`auto` は `std::string(e) == "auto"` の完全一致で、`atoi` より前に検査される（`src/core/pinned.cu:302`）。
- 数値の後ろの文字は無視される（`atoi` は最初の非数字で止まる）。先頭空白は skip される。
- clamp・範囲検査はない。`v < 0 ? -1 : v` だけで、`INT_MAX` を超える文字列の `atoi` 結果は実装依存（このコードは特別扱いしない）。
- 未設定・空・負の parse 結果は `-1`（「engine が決める」）で、`0` は「上限なし＝全体 pin」として明示的に区別される（`src/core/pinned.cu:301`、`src/program/generate.cpp:4712`）。

## 有効になる条件

値が正でも、arena 構築時に `max_pinned_bytes`（呼び出し側の cap）が 0 のときだけこの env が cap として使われる。

- `src/core/pinned.cu:369-374`: `cap = max_pinned_bytes`、`if (cap == 0 && env_gib > 0) cap = env_gib << 30`。
- engine の arena 経路では `max_pinned_bytes` が `src/program/generate.cpp:4709` の `pin_limit` で、`pin_env >= 0` のとき `pin_env << 30`、`pin_env < 0` のとき `pin_wddm_cap ? 8 GiB : 0`。したがって engine 経路では env の値は `max_pinned_bytes` として渡される。
- `capped = cap > 0 && cap < bytes && bounds.size() >= 2`（`src/core/pinned.cu:375`）。`bytes` は arena の capacity（`want + blob`、ファイルサイズより 1 blob 大きい: `src/core/expert_source.cpp:4543`）。cap が arena 以上なら `capped` は false になり、arena 全体の登録が試みられる。
- `bounds.size() >= 2` を満たさない呼び出し（同梱ツール `strata-load`・`strata-overlap`・`strata-concurrent` は bounds なしで arena を作る: `src/core/load_main.cpp:56`、`src/core/overlap_main.cpp:69`、`src/core/concurrent_main.cpp:82`）では `capped` が常に false。エンジンの arena は layer ごとに bounds を持つので `n_layers >= 1` で常に size >= 2（`src/core/expert_source.cpp:4522-4528`）。
- `--mmap-experts`（`FileExpertSource`）は `PinnedArena` を使わない。この env は効かない（`src/program/generate.cpp:4622`、`src/core/expert_source.cpp:4451-4482`）。
- `STRATA_ARENA_MMAP=1`（Linux）で file mapping を選んだ arena も `PinnedArena` を使わない（`src/core/expert_source.cpp:4454-4476`）。

`auto`（`-2`）は Windows 専用で、しかも engine cap が無いときだけ参照される（`src/core/pinned.cu:388-393` の `#ifdef _WIN32` と `if (!capped && env_gib == -2)`）。Linux では `sliced_pin_limit()` がコンパイルされず、`gpu_shared_memory_budget()` は "DXGI is Windows-only" で false を返す（`src/platform/memory.cpp:135-139`）。`auto` は `pin_env < 0` 側なので、multi-GPU/remote experts で WDDM の 8 GiB cap が成立する状況では `capped` が true になり、`auto` の budget 判定は走らない。

## 実行時の詳細

`arena_pin_cap_gib()` は arena 構築時に呼ばれる。関数内に `static` cache はなく、呼び出しごとに `std::getenv` を読む。`src/program/generate.cpp:4707` は起動時（arena 分岐）に一度読む。プロセス起動後の環境変更は、その後に作られる arena には反映されるが、すでに構築済みの arena には反映されない。

engine での流れ:

1. `src/program/generate.cpp:4708-4709` で `pin_wddm_cap`（`pin_env < 0` かつ `o.expert_cache_remote[0] > 0 || multi_gpu` かつ `under_wddm()`）と `pin_limit` を決める。`under_wddm()` は Windows では常に true、Linux では `/dev/dxg` の存在で判定（static cache）（`src/program/generate.cpp:132-139`）。
2. `pin_env >= 0` なら stderr に print（後述）。
3. `pin_limit` を `ArenaExpertSource::open(..., max_pinned_bytes, ...)`（`src/program/generate.cpp:4716`、`include/strata/core/expert_source.hpp:920`）へ渡す。
4. `PinnedArena` 構築（`src/core/pinned.cu:354-454`）。`capped` が true なら arena 全体の `cudaHostRegister` は最初から試みられず、bounds（layer ごと）を順に slice 登録し、`off > limit || n > limit - off` で止まる（`src/core/pinned.cu:394-404`）。`registered_bytes` は登録できた prefix。
5. `registered_bytes < bytes` のとき、残りは `STRATA_ARENA_LOCK` の判定に従って lock される（`src/core/pinned.cu:413-422`）。
6. `src/core/expert_source.cpp:4630-4645` が `pinned_bytes_` と `dev_slice_`（device alias）を作る。`pinned(layer, expert)` は blob が `pinned_bytes_` 内か只看る（`src/core/expert_source.cpp:4707-4711`）。

`#285` の deferred registration 経路（`STRATA_DEFERRED_REGISTER`）は `max_pinned_bytes == 0 && arena_pin_cap_gib() == -1` のときだけ選ばれる（`src/core/expert_source.cpp:4535-4541`）。つまりこの env が cap として有効な値（正の整数）のときは deferred 経路に入らず、`register_slices()` 内には cap 判定が存在しない（`src/core/pinned.cu:467-496`）。

CUDA/HIP ビルドは `src/core/pinned.cu` をそのまま使う（`CMakeLists.txt:293`、`cmake/hip_backend.cmake:114-121`、`include/strata/hip_compat/cuda_runtime.h:76-78`）。SYCL ビルドは `sycl/CMakeLists.txt:88-103,195` により `sycl/src/core/pinned.dp.cpp` を使う。そのファイルでは `cudaHostRegister` が DPCT1027 で `0` に置換され、capped でない限り常に「成功」扱いになる（`sycl/src/core/pinned.dp.cpp:384-396`）。よって SYCL ビルドで sliced 経路に到達するのは cap が成立したときだけで、`STRATA_ARENA_PIN_GIB=N` が note と registered prefix を決める唯一の入口になる。

## 観測できる結果

起動時の print（arena 分岐のみ、`--mmap-experts` では出ない）:

- `pin_env >= 0`（`atoi` が 0 以上を返すあらゆる値を含む）:
  `strata generate: STRATA_ARENA_PIN_GIB=%d: %s`（`src/program/generate.cpp:4710-4712`）。`%d` は parse 後の整数なので、`abc` や `0.7` は `=0` として表示され、文言は `the whole expert arena is pinned`。
- `pin_env < 0`（未設定・空・負・`auto`）で `pin_wddm_cap` が成立:
  `strata generate: multi-GPU under WDDM: at most 8 GiB of the expert arena is pinned (STRATA_ARENA_PIN_GIB changes it)`（`src/program/generate.cpp:4713-4715`）。`auto` のときはこの文言が出る（`pin_env < 0` 側だから）。

arena note（`src/program/generate.cpp:4723` の `strata generate: expert arena: <note>`、同梱ツール `strata-load` は `backing: <note>`、`src/core/load_main.cpp:57`）:

- cap が成立したとき（`capped`）:
  `cudaHostRegister limited to <cap >> 30> GiB <cap_why>; <n> slices pinned (<m> GiB); <backing note>`（`src/core/pinned.cu:407-412`）。`cap >> 30` は整数 GiB（切り捨て）。
  engine 経路では `cap` が `max_pinned_bytes`（= `pin_limit`）から来るので、`cap_why` は `by the engine (multi-GPU under WDDM, or remote experts)` になる。`by STRATA_ARENA_PIN_GIB` の文字列（`src/core/pinned.cu:373`）は `cap == 0 && env_gib > 0` のときだけ代入され、その条件は bounds を持つ呼び出しで engine 経路から到達しない（bounds なしツールでは `capped` が false で `cap_why` は note に出ない）。
- cap が成立せず sliced fallback に入り、かつ Windows で `auto` のとき:
  `cudaHostRegister of the whole arena FAILED (<error string>); slices capped at <%.1f> GiB (<limit_why>; STRATA_ARENA_PIN_GIB=auto; N sets a cap; #243); <n> slices pinned (<m> GiB); <backing note>`（`src/core/pinned.cu:408-412`）。`limit_why` は DXGI 成功時 `the GPU's shared-memory budget <B> GiB - <U> GiB in use - 4 GiB`、DXGI 失敗時 `<err>: RAM/2 - 8 GiB of <R> GiB`（`src/core/pinned.cu:324-326,333`）。
- cap が成立せず、`auto` でもない（または Linux）: `slices capped at ...` の部分が無い。note は `cudaHostRegister of the whole arena FAILED (...); <n> slices pinned (<m> GiB); ...`。
- cap が arena 以上、または `0`/未設定で全体登録成功: `cudaHostRegister PORTABLE ok; <backing note>`（`src/core/pinned.cu:379`）。このとき `capped` は false で、cap の文言は出ない。

エラー・終了は発生しない。判定結果は起動時の print と note として見えるだけ。

## docs との照合

- `docs/MULTI_GPU.md:217-220`: WDDM 下では arena の 8 GiB だけ pin、`STRATA_ARENA_PIN_GIB=N` は最大 N GiB、`0` は arena 全体、"on any OS"。コードの `pin_limit`（`src/program/generate.cpp:4709`）と一致する。
- `docs/SECOND_GPU.md:37-42`: WDDM 下で registration は 8 GiB 上限、`STRATA_ARENA_PIN_GIB` がそれを override、Linux では全体 registered。一致。
- 資料中の測定主張（条件付き）: `docs/MULTI_GPU.md:219` は 8 GiB cap が 4090 + 3060 split の prompt speed を 2/3 失わせた（#253）とする。`src/program/generate.cpp:131` の注釈は同じ #253 を "3x of its prompt speed" と書く。`src/core/pinned.cu:390-391` の注釈は、64 GB PC では budget を 30 GiB 超え pin しても問題なく、26 GiB に cap すると prompt speed が約 20% 落ちた、と書く（`auto` が既定でない理由）。いずれも機種・OS・モデル・回数が示されていない主張であり、こちらで再確認した事実としては書かない。
- `auto` が `docs/` に記載されていない: `docs/MULTI_GPU.md` と `docs/SECOND_GPU.md` は `N` と `0` だけを書き、`auto`（返り値 `-2`）はコード注釈（`src/core/pinned.cu:302,389-391`、`include/strata/core/pinned.hpp:26-28`）にしか現れない。

## 根拠

- 読み取りと parse: `src/core/pinned.cu:299-305`、`src/program/generate.cpp:4707`、`sycl/src/core/pinned.dp.cpp:305-311`、`sycl/src/program/generate.cpp:4208`
- 宣言と意味（-1/-2/0/N）: `include/strata/core/pinned.hpp:26-29`
- cap の適用と `capped` 判定: `src/core/pinned.cu:367-383`、`sycl/src/core/pinned.dp.cpp:375-383`
- sliced 登録と limit break: `src/core/pinned.cu:394-404`、`sycl/src/core/pinned.dp.cpp:409-430`
- `auto` の Windows 限定: `src/core/pinned.cu:388-393`、`sycl/src/core/pinned.dp.cpp:403-408`
- `sliced_pin_limit()` と DXGI: `src/core/pinned.cu:314-336`、`src/platform/memory.cpp:69-109,111-115,135-139`
- bounds（layer ごと）と capacity: `src/core/expert_source.cpp:4520-4528,4543`、`src/core/pinned.cu:341-352`
- deferred 経路の条件: `src/core/expert_source.cpp:4535-4541`、`sycl/src/core/expert_source.cpp:3442`
- registered prefix の効果（device alias / pinned）: `src/core/expert_source.cpp:4630-4645,4707-4720`、`src/prefill/prefill.cpp:3649,3669-3675`
- `STRATA_ARENA_LOCK` との接続: `src/core/pinned.cu:413-422`
- 起動時 print: `src/program/generate.cpp:4702-4715,4723`、`src/core/load_main.cpp:57`
- 子プロセスへの継承: `serve/server.py:2554-2565,671-672`
- backend 選択: `CMakeLists.txt:293`、`cmake/hip_backend.cmake:114-121`、`include/strata/hip_compat/cuda_runtime.h:76-78`、`sycl/CMakeLists.txt:88-103,195`
- docs: `docs/MULTI_GPU.md:217-220`、`docs/SECOND_GPU.md:37-42`
