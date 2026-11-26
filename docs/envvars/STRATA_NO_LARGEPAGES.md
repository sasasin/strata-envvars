# `STRATA_NO_LARGEPAGES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

expert arena の確保時に、大ページの利用を試さないためのスイッチ。値の内容ではなく環境変数が設定されているかを見ている。Windows では `MEM_LARGE_PAGES` の `VirtualAlloc` を省略し、通常ページの `VirtualAlloc` に進む。Linux では `MAP_HUGETLB | MAP_HUGE_2MB` の `mmap` を省略し、通常の匿名 mapping に進む。また Linux では通常 mapping への明示的な `MADV_HUGEPAGE` も要求しない。expert arena の内容やサイズを切り替える設定ではない（`engine/src/core/pinned.cu:284-316,458-471,486-553`、SYCL 実装 `engine/sycl/src/core/pinned.dp.cpp:92-117,207-277`）。

CUDA/HIP 系の `pinned.cu` 内 `reserve` と SYCL 系の同名処理で参照される。Linux の `ArenaExpertSource::open` は、RAM 不足時に hugetlb pool 全体を見込んで続行できるかの判定でもこの変数を参照する（`engine/src/core/expert_source.cpp:6621-6635`）。

## 値と判定

文字列の parse、数値変換、空白除去、大文字小文字変換はない。各箇所は `std::getenv(...) != nullptr` で設定の有無を判定する。そのため空文字を含む任意の値が設定済み扱いになる。未設定なら通常の大ページ試行経路に進むが、実際に大ページになるかは OS の確保結果などに依存する（`engine/src/core/pinned.cu:290,309,462,525,534,547`、`engine/sycl/src/core/pinned.dp.cpp:93,110,209,264,271`）。

| 条件 | unset | 設定ありの例（大ページ試行を抑制） | 値の内容にかかわらず同じ扱いの例 |
|---|---|---|---|
| Windows、CUDA/HIP または SYCL の pinned arena | 大ページ最小値があれば `MEM_LARGE_PAGES` を試す | `1` | 空文字、`0`、`true`、`false`、`0anything` |
| Linux、CUDA/HIP または SYCL の pinned arena | `MAP_HUGETLB` を試し、通常 mapping では条件を満たせば `MADV_HUGEPAGE` を要求 | `1` | 空文字、`0`、`true`、`false`、`0anything` |

CLI 引数や別環境変数がこの値を書き換える処理はない。`STRATA_ARENA_THP` が設定されていても、`STRATA_NO_LARGEPAGES` が設定済みなら Linux の `MADV_HUGEPAGE` 分岐には入らない（`engine/src/core/pinned.cu:522-552`、`engine/sycl/src/core/pinned.dp.cpp:260-276`）。

## 有効になる条件

- Strata が expert arena を process-private な pinned arena として確保する経路で有効。環境変数を確認するのは arena 確保時で、プロセス起動時に値を static cache する実装ではない。reserve 中も複数回 `getenv` を呼ぶ（`engine/src/core/pinned.cu:159-161,290-316,458-553`、`engine/sycl/src/core/pinned.dp.cpp:63-65,93-117,207-277`）。
- Windows では `GetLargePageMinimum()` が 0 なら、未設定でも大ページ試行は行われない。変数が設定されていれば最小値が正でも大ページを飛ばす（`engine/src/core/pinned.cu:283-315`、`engine/sycl/src/core/pinned.dp.cpp:91-117`）。
- Linux では変数が未設定のときに hugetlb mapping を試す。試行失敗時は通常 anonymous mapping に進み、通常 mapping ができた後の `MADV_HUGEPAGE` は `STRATA_NO_ARENA_THP`、THP の `always` 状態、空き huge block の確認などにも左右される（`engine/src/core/pinned.cu:466-553`、`engine/sycl/src/core/pinned.dp.cpp:212-277`）。
- Linux の `STRATA_NUMA_ARENA` による配置が利用可能な場合は、通常 mapping に `MADV_NOHUGEPAGE` を適用する経路がある。この分岐は `STRATA_NO_LARGEPAGES` の設定とは独立している（`engine/src/core/pinned.cu:461-502`）。Windows の配置可能な NUMA arena も通常ページを使う（`engine/src/core/pinned.cu:289-310`）。
- shared arena file を使う場合、`reserve` は大ページ選択より先に shared-file mapping を処理するため、この変数による大ページ判定を通らない。Linux の `STRATA_ARENA_MMAP=1` で既存 `experts.bin` を read-only mapping する経路も、`PinnedArena` を作らず先に return する（`engine/src/core/pinned.cu:318-320,444-455`、`engine/sycl/src/core/pinned.dp.cpp:119-121,193-204`、`engine/src/core/expert_source.cpp:6490-6521,6755-6759`）。
- Linux の RAM 不足判定では、設定済みなら hugetlb pool の空き量を 0 として扱う。これは大ページ試行をしないことを RAM 判定にも反映するためで、arena の backing を直接変更する分岐とは別の読み取りである（`engine/src/core/expert_source.cpp:6621-6635`）。

## 実行時の詳細

CUDA/HIP 系では `PinnedArena` の通常、ByNeed、Deferred constructor が `reserve` を呼ぶ。SYCL 系では Deferred constructor が同じ役割の `reserve` を呼ぶ。どちらも値を parse せず、各 `reserve` 呼び出し内で設定有無を確認する。通常の pinned arena 経路では未設定ならまず OS の大ページ確保を試し、失敗すれば 4 KB pages と記した note を作って通常ページで確保する。設定済みなら大ページ確保を試さず通常ページ確保へ進む。設定は arena の backing 選択に関するもので、確保失敗時には通常の arena 予約失敗経路が残る（`engine/src/core/pinned.cu:290-316,458-492,1030-1035,1177-1191,1274-1292`、`engine/sycl/src/core/pinned.dp.cpp:92-117,207-245,519-527`）。

Linux では大ページ試行が失敗して通常 mapping へ進んだ場合、変数が unset なら条件に応じて `MADV_HUGEPAGE` を要求する。設定済みならその要求分岐もスキップする。ただし `STRATA_NUMA_ARENA` の適用経路では `MADV_NOHUGEPAGE` が実行される。ここで記述しているのは Strata が行う system call の選択であり、その後の OS のページ backing の状態を保証するものではない（`engine/src/core/pinned.cu:486-553`、`engine/sycl/src/core/pinned.dp.cpp:232-277`）。

Linux の RAM 判定で `STRATA_NO_LARGEPAGES` が設定済みだと hugetlb pool を空として扱うため、hugetlb pool を根拠にした file-cache arena の続行判定には使われない。この判定を含む別条件が成立して警告になる場合は、`generate` が `strata generate: WARNING: ...` と stderr に出す。arena note は `strata generate: expert arena: ...` と stderr に出力される（`engine/src/core/expert_source.cpp:6621-6645`、`engine/src/program/generate.cpp:8934-8936`）。通常ページ確保自体が失敗した場合、呼び出し側は note を付けて arena 予約失敗を返す（`engine/src/core/expert_source.cpp:6755-6766`）。

## ログと測定値

大ページをスキップした場合、arena note は `large pages skipped (STRATA_NO_LARGEPAGES); using 4 KB pages` になる。Windows では `STRATA_NUMA_ARENA` が配置を選んだ場合はその理由が優先され、`large pages skipped (STRATA_NUMA_ARENA=1); using 4 KB pages` となる。Linux ではこの note が `strata generate: expert arena: ...` として stderr に出る。Windows/SYCL の note 文字列も `reserve` で設定されるが、一般の note 出力箇所は `generate.cpp` にある（`engine/src/core/pinned.cu:307-312,462-465`、`engine/sycl/src/core/pinned.dp.cpp:110-113,209-211`、`engine/src/program/generate.cpp:8934-8936`）。

未設定時に Windows の大ページ確保が失敗すると、`large pages refused for ...; using 4 KB pages` の note になる。Linux で hugetlb 確保が失敗すると、必要な 2 MiB page 数と `vm.nr_hugepages` を含む `MAP_HUGETLB unavailable (...); using 4 KB pages` の note になる（`engine/src/core/pinned.cu:302-306,473-484`、`engine/sycl/src/core/pinned.dp.cpp:105-109,219-230`）。`docs/DETAILS.md:168-179` は Windows の large pages に権限が必要なことと起動ログで拒否を確認する手順を説明するが、`STRATA_NO_LARGEPAGES` 自体の説明や同変数を使った性能測定値は記載していない。

## 根拠

- 候補一覧の名前だけでなく、実際の読み取り箇所を全参照検索で確認。CUDA/HIP 系と Linux RAM 判定: `engine/src/core/pinned.cu:290,309,462,525,534,547`、`engine/src/core/expert_source.cpp:6634`。
- SYCL 系の Windows/Linux 分岐と THP request 抑制: `engine/sycl/src/core/pinned.dp.cpp:93,110,209,264,271`。
- arena 確保からの呼び出しと失敗経路: `engine/src/core/expert_source.cpp:6755-6766`。
- note の stderr 出力: `engine/src/program/generate.cpp:8934-8936`。
- 設計資料との照合: `docs/DETAILS.md:168-179`。
