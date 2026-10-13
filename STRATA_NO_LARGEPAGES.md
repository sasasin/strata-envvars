# `STRATA_NO_LARGEPAGES`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・ドライバーの動作は対象外。

## 役割

`PinnedArena` の確保時に、大ページ用の割り当てを試さず通常の匿名メモリへ進ませるための切替です。Windows では `VirtualAlloc(MEM_LARGE_PAGES)`、Linux では `mmap(MAP_HUGETLB | MAP_HUGE_2MB)` を飛ばします。Linux では通常ページへのフォールバック時に Strata が呼ぶ `madvise(MADV_HUGEPAGE)` も抑止します。

通常の `strata generate` では `--mmap-experts` を使わず `ArenaExpertSource` を開く経路が対象です。CUDA 実装では `PinnedArena` の予約後に GPU 用 host registration を試みますが、この変数はその登録の有無や登録量を直接変更するものではありません。SYCL 実装では既存メモリの登録箇所が変換時の no-op になっています。確保状況の注記は `strata generate: expert arena: ...` として stderr に出力されます。

## 値と判定

数値や文字列の parse はせず、`std::getenv("STRATA_NO_LARGEPAGES") != nullptr` かどうかだけで判定します。従って `1` だけでなく、空文字、`0`、`false` を含む、設定されているすべての値が大ページ経路を無効にします。

| 値 | 動作 |
|---|---|
| 未設定 | OS ごとの大ページ割り当てを試す。失敗時は通常メモリへ fallback する。 |
| 空文字を含む任意の設定値 | 大ページ割り当てを試さず、通常メモリへ進む。 |

判定は `reserve()` の呼び出し中に行われ、static cache されません。したがって後から環境を変更した場合、その後に行われる予約では新しい設定が参照されます。既に確保済みの領域は変更されません。

## 有効になる条件

- `PinnedArena` が匿名メモリを予約する経路で有効です。Windows では共有ファイル backing は未実装です。Linux では `shared_file` が指定されると `MAP_SHARED` の処理が先に return するため、この変数はその予約に影響しません。
- `strata generate --mmap-experts` は `ArenaExpertSource` ではなくファイル tier を使うため、この大ページ切替の対象となる expert arena を作りません。
- Linux で別変数 `STRATA_NO_ARENA_THP` だけを設定した場合、hugetlb の試行は残り、失敗後の `MADV_HUGEPAGE` 要求だけが抑止されます。`STRATA_NO_LARGEPAGES` が設定されている場合は、両方の処理が抑止されます。
- Linux のシステム設定が THP を `always` にしている場合、カーネルは `MADV_HUGEPAGE` の明示要求なしでも通常の匿名 mapping を透過的大ページで backing する可能性があります。この環境変数はシステム全体の THP 設定を変更しません。

## 実行時の詳細

Windows では、変数の判定前に `SeLockMemoryPrivilege` を process token で有効化しようとします。その後、未設定かつ `GetLargePageMinimum() > 0` のときに限り、サイズを大ページ単位へ切り上げて `VirtualAlloc(..., MEM_LARGE_PAGES, ...)` を試します。変数が設定されていればその割り当て試行を飛ばし、注記を `large pages skipped (STRATA_NO_LARGEPAGES); using 4 KB pages` として通常の `VirtualAlloc` を使います。未設定でも大ページ割り当てに失敗した場合は、失敗サイズと Windows エラー番号を注記して通常ページへ fallback します。

Linux では変数が未設定なら、まず `MAP_HUGETLB | MAP_HUGE_2MB` による anonymous mapping を試します。成功すれば 2 MiB hugetlb pages を使います。失敗時、または変数が設定済みの場合は、2 MiB 境界に揃えた通常の anonymous mapping へ進みます。変数が未設定なら、THP の現在設定と `STRATA_NO_ARENA_THP` を調べて必要に応じて `MADV_HUGEPAGE` を呼びます。変数が設定済みならこの要求も呼びません。変数設定時の注記は `large pages skipped (STRATA_NO_LARGEPAGES); using 4 KB pages` です。ただし THP `always` の場合、この注記はカーネルが実際に使う backing page size を保証しません。

確保に成功した後は、通常の `PinnedArena` 初期化が CUDA の host registration などへ進みます。`STRATA_NO_LARGEPAGES` 自体はログ以外の診断出力、終了、性能保証を行いません。`docs/DETAILS.md` は Windows で大ページに `SeLockMemoryPrivilege` が必要なことを説明していますが、この変数による性能値の比較や保証は記載していません。

## 根拠

- `src/core/pinned.cu:59-113`: Windows の token privilege 処理、大ページ判定、設定時の skip、通常ページ fallback。
- `src/core/pinned.cu:114-201`: Linux shared-file mapping が環境変数の判定より先に return する経路。
- `src/core/pinned.cu:203-270`: Linux hugetlb 試行、通常 mapping、THP 要求と `STRATA_NO_ARENA_THP` の相互作用。
- `sycl/src/core/pinned.dp.cpp:60-113,114-202,204-271`: SYCL 実装にある対応する分岐。
- `src/core/pinned.cu:354-379`: arena 予約後の CUDA host registration。`sycl/src/core/pinned.dp.cpp:360-390,524-548` は同じ予約後の SYCL 実装と、登録箇所が no-op であることを示す。
- `src/core/expert_source.cpp:3446-3450`: `FileExpertSource` が通常または deferred の `PinnedArena` を作成する箇所。
- `src/program/generate.cpp:4620-4637,4700-4726`: `--mmap-experts` の file tier と通常の `ArenaExpertSource` 経路、および arena 注記の stderr 出力。
- `docs/DETAILS.md:515-524`: Windows の起動条件と大ページ権限についての説明。`STRATA_NO_LARGEPAGES` の固有説明や比較測定はない。
