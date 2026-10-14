# `STRATA_ARENA_THP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Linux の pinned expert arena を anonymous mapping で確保したとき、通常の huge page 試行が使えなかった後に `madvise(..., MADV_HUGEPAGE)` を要求するかを制御します。既定では `/proc/buddyinfo` から見積もった空き 2 MiB ブロックが arena サイズの半分未満なら、メモリ断片化時の reclaim/compaction による長い停止を避けるため要求を抑止します。この変数が設定されていると、その空きブロック量による抑止を解除して `MADV_HUGEPAGE` を試します。

これは THP の実際の割り当てや性能を保証する設定ではなく、カーネルへの advice の要求を制御します。

## 値と判定

数値や文字列の parse はなく、`std::getenv("STRATA_ARENA_THP") != nullptr` だけで判定します。従って `1` に限らず、空文字、`0`、`false` を含む設定済みのすべての値が空きブロック量チェックを迂回します。

| 条件 | `MADV_HUGEPAGE` の扱い |
|---|---|
| `STRATA_NO_LARGEPAGES` が設定済み | hugetlb 試行と THP advice の両方を行わない。この変数では覆せない |
| `STRATA_NO_LARGEPAGES` は未設定、`STRATA_NO_ARENA_THP` が設定済み | THP advice を行わない。この変数では覆せない |
| 上記 unset、カーネルの THP mode が `always` | 追加 advice は行わない。この変数でも覆せない |
| それ以外で `STRATA_ARENA_THP` が未設定、空き 2 MiB ブロックが arena の半分未満 | advice を抑止し、理由を stderr に出す |
| それ以外で `STRATA_ARENA_THP` が設定済み、または空きブロックが arena の半分以上 | `madvise(p, bytes, MADV_HUGEPAGE)` を試す |

`madvise` が失敗しても、ここでは専用の警告やエラー終了を行いません。成功時は注記に `transparent huge pages requested (MADV_HUGEPAGE)` を加えますが、これは要求が受理されたことを示す注記であり、個々のページが huge page で backing されたことの確認ではありません。

根拠: `src/core/pinned.cu:289-315`。

## 有効になる条件

- Linux の `PinnedArena::reserve()` が shared-file mapping ではなく通常の anonymous mapping に進み、hugetlb mapping を使わなかった場合が対象です。shared-file mapping は `reserve()` 冒頭で作られ、その経路は THP の環境変数判定より前に戻ります（`src/core/pinned.cu:91-93,147-234`）。
- Windows の `reserve()` は `VirtualAlloc` を使う別分岐で、この変数を参照しません（`src/core/pinned.cu:96-146`）。
- `STRATA_NO_LARGEPAGES` は設定有無で先に hugetlb を飛ばし、通常 mapping にも THP advice を出しません。値が `0` や空文字でも設定済みなら同じです（`src/core/pinned.cu:236-260,289-310`）。
- `STRATA_NO_ARENA_THP` が設定されているか、`/sys/kernel/mm/transparent_hugepage/enabled` の選択中 mode が `always` なら、空きブロック判定や `STRATA_ARENA_THP` の override に進まず advice を抑止します（`src/core/pinned.cu:279-296`）。sysfs を読めないなど mode を取得できないときは空文字のままなので、mode が `always` という理由では抑止されません。
- 空き量は `/proc/buddyinfo` の各 zone について order 9 以上（2 MiB 以上）の空きブロック数を合計して算出します。ファイルが読めないと合計は 0 のままとなり、arena が非ゼロなら未設定時の閾値チェックで抑止されます（`src/core/pinned.cu:58-84,297-308`）。

## 実行時の詳細

通常の arena は `ArenaExpertSource::open()` から `PinnedArena` を生成して予約します。通常、`strata generate` は arena source の注記を stderr に `strata generate: expert arena: ...` と出力します。空きブロック不足で advice を抑止した分岐は `reserve()` 内からも `strata: expert arena: ...` を stderr に出します（`src/core/expert_source.cpp:4658-4669`, `src/program/generate.cpp:5011-5015`, `src/core/pinned.cu:303-309`）。

この環境変数の判定は `reserve()` の各呼び出し中に行われ、static cache されません。後から環境を変更して新しい arena 予約が行われれば、その予約では新しい値を参照します。すでに予約された領域の backing/advice は変更されません（`src/core/pinned.cu:91-93,400-405,502-507,589-598`）。

## 文書との照合

`docs/TROUBLESHOOTING.md:64-67` は、THP mode が `always` の場合に追加の `MADV_HUGEPAGE` を行わないことと、`STRATA_NO_ARENA_THP=1` で要求を抑止できることを説明しています。一方、この commit の `src/core/pinned.cu:297-308` には、空き huge-page ブロックが arena の半分未満なら既定で advice を抑止し、`STRATA_ARENA_THP` が設定されていれば要求する追加の分岐があります。同 troubleshooting 文書にはこの変数と閾値 override の説明がありません。

`docs/DETAILS.md` に、この変数固有の挙動や性能測定は見つかりませんでした。従って性能への効果や THP backing の実績はここでは主張しません。

## 根拠

- `src/core/pinned.cu:58-84`: 空き 2 MiB 以上ブロックの集計。
- `src/core/pinned.cu:91-93,147-234`: `reserve()` の Linux shared-file mapping 経路。
- `src/core/pinned.cu:236-260`: Linux hugetlb 試行と `STRATA_NO_LARGEPAGES`。
- `src/core/pinned.cu:261-316`: anonymous mapping、THP mode、相互作用、advice と警告。
- `src/core/pinned.cu:400-405,502-507,589-598`: `PinnedArena` の予約呼び出し。
- `src/core/expert_source.cpp:4658-4669`: arena expert source から `PinnedArena` を生成する経路。
- `src/program/generate.cpp:5011-5015`: 起動時の arena 注記。
- `docs/TROUBLESHOOTING.md:64-67`: THP `always` と `STRATA_NO_ARENA_THP` の説明。
