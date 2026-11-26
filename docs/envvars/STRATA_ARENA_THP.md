# `STRATA_ARENA_THP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux 側の pinned expert arena で、空き 2 MiB ブロックが arena サイズの半分未満の場合にも `MADV_HUGEPAGE` を要求するための上書きスイッチ。Strata は環境変数の値を解釈せず、設定されているかだけを確認する。設定されていれば空きブロック量による安全判定を飛ばすが、THP の要求そのものを止める別条件は上書きしない。要求先は 2 MiB 境界に整列した匿名 arena であり、Strata が行うのは `madvise(..., MADV_HUGEPAGE)` の呼び出しまでで、実際に THP が割り当てられることは保証しない（`engine/src/core/pinned.cu:486-503`, `engine/src/core/pinned.cu:534-552`）。

## 値と判定

`std::getenv("STRATA_ARENA_THP") == nullptr` かどうかだけを判定する。数値・真偽値への変換、文字列比較、空白除去はない。未設定なら空きブロック量の判定を行い、設定済みならその判定を省略する。

| 条件 | unset | 有効になる値 | この変数による上書き |
|---|---|---|---|
| `STRATA_NO_LARGEPAGES` 未設定で、先行する THP 抑制条件に該当しない場合 | `free_huge_bytes() < bytes / 2` なら `MADV_HUGEPAGE` を見送る。以上なら要求する | 空文字、`0`、`1`、`true`、`false`、任意の文字列 | 設定済みなら空きブロック量が半分未満でも要求を試みる |
| `STRATA_NO_LARGEPAGES` が設定済み、または先行する THP 抑制条件に該当 | この変数の有無にかかわらず要求しない | なし | 上書きしない |

境界は `bytes / 2` との厳密な `<` 比較で、ちょうど半分なら未設定でも要求側になる。空き量は `/proc/buddyinfo` の order 9 以上のブロックから算出する。判定に必要なファイルを読めず合計が 0 になる場合も、未設定なら通常は閾値未満として要求を見送る。CLI 引数や設定ファイルによる同機能の指定はこのコード経路にはない（`engine/src/core/pinned.cu:120-146`, `engine/src/core/pinned.cu:534-546`）。

## 有効になる条件

- Windows の `reserve()` は `#ifdef _WIN32` 側で別の大ページ確保経路を使い、この環境変数を読まない。対象の分岐は非 Windows 側にある。共有 arena は `shared_file` の処理で先に返るため、この THP 分岐に到達しない（`engine/src/core/pinned.cu:159-165`, `engine/src/core/pinned.cu:318-330`, `engine/src/core/pinned.cu:458-486`）。
- 2 MiB hugetlb mapping が成功した場合はその時点で返るため、THP 分岐には進まない。通常ページへの fallback に進んだ場合に限り対象となる（`engine/src/core/pinned.cu:466-485`）。
- `STRATA_NUMA_ARENA` が `numa_placeable` な arena で先頭文字 `1` の値を持つと、`MADV_NOHUGEPAGE` を呼んで先に返る。対象変数はこの条件を覆せない（`engine/src/core/pinned.cu:461-462`, `engine/src/core/pinned.cu:499-502`）。
- `STRATA_NO_LARGEPAGES` は値を問わず、設定されていれば hugetlb 試行を省き、後段でも `MADV_HUGEPAGE` を抑止する。`STRATA_ARENA_THP` では覆せない（`engine/src/core/pinned.cu:462-468`, `engine/src/core/pinned.cu:525-552`）。
- `STRATA_NO_ARENA_THP` が設定され、その先頭文字が `0` 以外（空文字も含む）、THP モードが `always`、または device 既定の `arena_no_thp_flag` が立っている場合、先行分岐で要求を省略する。`STRATA_ARENA_THP` はこれらを覆せない。`STRATA_NO_ARENA_THP=0` はユーザー指定で要求側にするが、THP `always` はなお要求を省略する（`engine/include/strata/core/arch_defaults.hpp:91-98`, `engine/src/core/pinned.cu:508-533`）。
- 残る条件を満たしても `madvise` が失敗すれば、Strata は「要求済み」の note に更新しない（`engine/src/core/pinned.cu:547-552`）。

## 実行時の詳細

arena を予約する `PinnedArena` の各コンストラクターから `reserve()` が呼ばれる時点で評価される。対象環境変数は関数内 cache に保存されず、該当の条件式で `getenv` が実行される。ここで設定有無が変えるのは `free_huge_bytes() < bytes / 2` による見送りだけで、既定の大ページ選択、arena のサイズや内容、GPU 登録の可否を直接変更する処理ではない（`engine/src/core/pinned.cu:159-165`, `engine/src/core/pinned.cu:534-552`, `engine/src/core/pinned.cu:1030-1035`）。

成功して `MADV_HUGEPAGE` を呼んだ場合、arena の note に `transparent huge pages requested (MADV_HUGEPAGE)` が加わる。空き量不足で見送る場合は stderr に `strata: expert arena: ... transparent huge pages NOT requested: only ...` を出し、文面に `STRATA_ARENA_THP=1 requests them anyway` と理由を含める。この診断出力は見送り分岐に限られる。`MADV_HUGEPAGE` の失敗自体について、この箇所に独立した警告や終了処理はない（`engine/src/core/pinned.cu:534-552`）。note は生成側で arena 確保失敗時のエラー理由にも使われる（`engine/src/core/expert_source.cpp:6755-6766`）。

## ログと測定値

空き量不足で要求を見送った場合の stderr 行は `strata: expert arena: %s\n`。`%s` には空きブロック量と arena サイズ（整数 GiB 表示）、`compaction would stall the load`、`STRATA_ARENA_THP=1 requests them anyway` が入る。要求成功時は note に `transparent huge pages requested (MADV_HUGEPAGE)` が入るが、生成経路では通常 note を常時表示するとは限らず、arena 予約失敗時にはエラー理由として付加される（`engine/src/core/pinned.cu:543-552`, `engine/src/core/expert_source.cpp:6760-6766`）。

測定値はこの変数の現行ソース動作を示す根拠として確認できなかったため記載しない。`docs/TROUBLESHOOTING.md:120-121` は THP `always` と `STRATA_NO_ARENA_THP` に触れるが、この変数の説明ではない。対象変数名は `docs/envvars/000_envvers.md` に候補として載る一方、実際のソース読み取りは上記 1 箇所で確認できた。

## 根拠

- `engine/src/core/pinned.cu:120-146` — 空き 2 MiB ブロック量の読み取り。
- `engine/src/core/pinned.cu:458-503` — hugetlb、NUMA、通常ページ fallback の順序。
- `engine/src/core/pinned.cu:508-552` — 先行する THP 抑制条件、安全判定、環境変数による判定の上書き、note と stderr。
- `engine/include/strata/core/arch_defaults.hpp:91-98` — `STRATA_NO_ARENA_THP` の判定。
- `engine/src/core/pinned.cu:1030-1035`, `engine/src/core/expert_source.cpp:6755-6766` — arena 予約呼び出しと失敗時の理由伝播。
