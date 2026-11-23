# `STRATA_NUMA_ARENA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

主な用途は、resident expert arena のページを NUMA node 0 と 1 に分けて初回 touch し、CUDA host registration より前に配置することです。Linux ではこの配置を行う arena の大ページ経路も避け、4 KiB ページにします。Windows では配置可能なホストと pack の場合に限って大ページを避けます。いずれも生成する token や expert 選択を変える処理ではなく、arena のページ配置を試みます。生成経路は `PinnedArena` の構築後に `arena_src.note()` を stderr に出します（`engine/src/core/pinned.cu:1030-1053`, `engine/src/program/generate.cpp:8863-8868`）。

同じ名前は別の二経路でも読まれます。Windows の CPU expert pool では NUMA pool split を試す許可条件になり、Hy4-Flash CPU expert のロードでは reader thread の pinning を無効にする値として使われます。この二つは arena のページ配置とは別の処理です（`engine/src/kernels/cpu/pool.cpp:671-694`, `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1761-1769`）。

## 値と判定

文字列を数値や真偽値として parse せず、各箇所が `getenv` の結果と先頭文字を見ます。空文字は「設定済み」ですが、先頭文字が `'1'` ではないため arena 配置を有効にしません。空白、大文字小文字、後続文字の妥当性検査もありません。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux resident arena の placement / large-page 選択 | placement 無効。通常のページ選択 | 先頭文字が `1`（`1`, `10`, `1anything`） | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1` |
| Windows resident arena の placement / large-page 選択 | placement 無効 | 先頭文字が `1`。ただし後述の layout と NUMA 条件も必要 | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1` |
| Windows CPU pool の実 NUMA split 許可 | この変数では許可しない | 先頭文字が `1`（または別条件として `STRATA_NUMA_SPLIT=1`） | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1` |
| Hy4-Flash CPU expert body reader の pinning | pinning を行う | この変数が未設定、または設定値の先頭文字が `0` 以外（空文字や `1` を含む） | 先頭文字が `0`（`0`, `0anything`） |

arena では `STRATA_NO_LARGEPAGES` が設定されていても `STRATA_NUMA_ARENA` の判定自体は行われます。Linux の配置可能 arena ではこの変数による 4 KiB 選択が優先されます。Windows は配置可能なとき大ページを試さず、配置できないときは `STRATA_NO_LARGEPAGES` など従来の条件に従います（`engine/src/core/pinned.cu:284-315`, `engine/src/core/pinned.cu:458-485`）。

## 有効になる条件

- **Linux arena 配置:** 通常の resident `PinnedArena` または `Deferred` arena で、shared-file arena ではないことが必要です。arena の予約時に `numa_placeable=true` が渡される必要があります。Linux ではこの予約時判定に native layout や topology の検査が含まれないため、値が有効なら大ページを避けます。一方、実際の slice touch は native expert layout、正の layer/expert 数、許容 CPU affinity、node 0 と node 1 に属する CPU が各 1 個以上あることを追加で必要とします。条件不足で toucher が戻っても、4 KiB ページ選択は取り消されません（`engine/src/core/pinned.cu:1030-1053`, `engine/src/core/pinned.cu:458-502`, `engine/src/core/pinned.cu:915-935`）。
- **Windows arena 配置:** shared-file arena ではなく、native expert layout が予約サイズ内に収まり、topology query が成功して node 0 と node 1 の processor group mask を得られることが必要です。これらの条件を満たさない場合は大ページを維持し、slice placement も行いません（`engine/src/core/pinned.cu:165-263`, `engine/src/core/pinned.cu:284-315`, `engine/src/core/pinned.cu:811-817`, `engine/src/core/pinned.cu:838-852`）。
- **Windows CPU pool:** 2 NUMA node 以上で `STRATA_NUMA_SPLIT` が未設定なら pool は自動 split を試しますが、実 split 判定では `STRATA_NUMA_ARENA` の先頭文字が `1`、または `STRATA_NUMA_SPLIT` が文字列全体で `1` であることが必要です。`STRATA_NUMA_POOL=0` は自動・明示 split を無効化します。実 split には2 thread 以上、両 node に割り当てられる pinned thread など共通条件も必要です。`STRATA_NUMA_SPLIT=test` は test split であり、この変数による実 NUMA split 許可判定は通りません（`engine/include/strata/kernels/cpu/numa_pool.hpp:65-83`, `engine/src/kernels/cpu/pool.cpp:660-694`, `engine/src/kernels/cpu/pool.cpp:803-820`, `engine/src/kernels/cpu/pool.cpp:924-977`）。Linux の pool split 判定ではこの変数を使わず、2 node 以上で自動試行する経路があります（`engine/src/kernels/cpu/pool.cpp:671-678`, `engine/src/kernels/cpu/pool.cpp:883-900`）。
- **Hy4-Flash reader:** Section 4 の expert body を resident arena に読み込む際、隣接 body の read run があると最大4 reader thread を起動します。先頭文字が `0` なら `pin_list` を呼ばず、他の場合は `pin_list` の結果を使って thread を pin します。`STRATA_CPUEXP_PIN=linear` はその pin list の並べ方に別途影響します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1732-1747`, `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1761-1773`, `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1904-1909`）。
- CLI option による `STRATA_NUMA_ARENA` の上書きは見つかりません。関連する独立設定は Windows pool の `STRATA_NUMA_POOL` / `STRATA_NUMA_SPLIT`、reader pin list の `STRATA_CPUEXP_PIN`、arena の大ページ選択に関わる `STRATA_NO_LARGEPAGES` です。

## 実行時の詳細

arena の値は予約時と slice placement 関数内で読み直され、static cache はありません。プロセス環境を読み取りの間に変更すれば判定が変わり得ますが、通常の生成経路では arena 構築時に評価されます。Linux では、値が有効で arena が通常ページで確保された後、最大16 thread が各 expert の `[gate | up | down]` role のページ境界で分けた前半・後半を node 0 / 1 の CPU 上で touch します。各 toucher は自分の affinity を設定し、`MPOL_DEFAULT` を要求します。arena の末尾の spare 領域も呼び出し元 thread が touch してから host registration に進みます（`engine/src/core/pinned.cu:915-976`, `engine/src/core/pinned.cu:1044-1055`）。

Windows では2 node の processor group affinity に toucher を割り当て、同じ role slice の touch を行います。全 toucher の起動または affinity 設定に失敗した場合も placement を試み、登録前に残りの arena pages を touch します。`ByNeed` arena には配置処理を呼ばず、shared arena も `shared_state` がある場合は touch 処理を呼びません（`engine/src/core/pinned.cu:838-909`, `engine/src/core/pinned.cu:1177-1193`, `engine/src/core/pinned.cu:1044-1053`）。

Windows CPU pool 判定は `ExpertPool` 構築時、worker 起動前に行われ、pool の間は再評価しません（`engine/src/kernels/cpu/pool.cpp:803-820`, `engine/src/kernels/cpu/pool.cpp:924-965`）。Hy4-Flash の `STRATA_NUMA_ARENA` 判定は resident expert bodies の reader thread を作るロード処理中に行われます。これは reader affinity の選択だけを変え、読み出す run や body の内容を変更しません（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1732-1779`）。

## ログと測定値

生成経路は stderr に `strata generate: expert arena: ...` と arena の `note` を出します。Linux の placement 完了時は `NUMA slice-placed (STRATA_NUMA_ARENA=1: slice 0 -> node 0, slice 1 -> node 1 in %.2f s)` が note に追加されます。Windows は完了時に同様の note を出し、toucher の pinning または起動が部分失敗した場合は `STRATA_NUMA_ARENA=1: WARNING: slice placement partial (%d toucher(s) off-node%s); the pages the missing workers own stay unpinned`、非対応 layout では `... the switch was ignored`、1 node または topology query 失敗では `... slice placement not needed` を追加します（`engine/src/core/pinned.cu:844-852`, `engine/src/core/pinned.cu:899-908`, `engine/src/core/pinned.cu:973-976`, `engine/src/program/generate.cpp:8863-8868`）。Linux の layout / affinity / node CPU 条件で placement 関数が途中 return した場合、理由 note は追加されません（`engine/src/core/pinned.cu:918-935`）。

arena が CUDA host registration に失敗したときは `cudaHostRegister FAILED (...) - the arena is NOT pinned, so copies will be slow`、全体登録に失敗して slice 登録へ移ると `cudaHostRegister of the whole arena FAILED (...)` を含む note が記録されます。これは NUMA placement の成功を意味せず、placement note と別の結果です（`engine/src/core/pinned.cu:1096-1148`）。Hy4-Flash reader thread の pinning 失敗は呼び出し側で戻り値を捨てるため、この箇所から個別の失敗ログは出ません（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1765-1769`）。

`docs/NVIDIA_V100.md` は dual-socket Linux の resident arena について説明していますが、コードには Windows arena、Windows CPU pool、Hy4-Flash reader pinning の別用途もあります。また、Linux は予約時点の topology / layout 条件では大ページを抑止する一方、実配置関数には追加条件があるため、設定した値だけで placement 完了とは判断できません（`docs/NVIDIA_V100.md:69`, `engine/src/core/pinned.cu:458-502`, `engine/src/core/pinned.cu:915-935`）。測定値は本書では一般化しません。

## 根拠

- `engine/src/core/pinned.cu:284-315`, `engine/src/core/pinned.cu:458-502`, `engine/src/core/pinned.cu:807-852`, `engine/src/core/pinned.cu:915-976`, `engine/src/core/pinned.cu:1030-1055`
- `engine/src/kernels/cpu/pool.cpp:660-694`, `engine/src/kernels/cpu/pool.cpp:803-820`, `engine/src/kernels/cpu/pool.cpp:924-977`
- `engine/include/strata/kernels/cpu/numa_pool.hpp:65-83`
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1732-1779`, `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1904-1909`
- `engine/src/program/generate.cpp:8863-8868`
- `docs/NVIDIA_V100.md:69`
