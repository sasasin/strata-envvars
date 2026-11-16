# `STRATA_ARENA_FILE_CACHE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux で専門家 arena の RAM 不足を検出した際、空きページ・破棄可能なファイルキャッシュ・条件を満たす予約 huge page が不足分を賄えるとして arena の読み込みを続ける例外を抑止する。値が `0` ならこの例外を使わず、通常の RAM 不足判定に従う。読み取り箇所は `ArenaExpertSource::open` だけで、メモリを確保するかファイル読み込みへ切り替えるかを選ぶ補助条件である（`src/core/expert_source.cpp:6090-6122`）。

## 値と判定

値全体を数値や真偽値として parse せず、`getenv` が返す文字列の先頭 1 文字だけを比較する。未設定、空文字、先頭文字が `0` 以外なら `file_cache_off == false`。文字列が `0` で始まれば `true`（`src/core/expert_source.cpp:6103-6106`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux の arena RAM 不足時の例外判定 | キャッシュを見込む判定を許可 | `0`, `0anything`, `00` は例外を無効化 | 空文字、`1`, `true`, `false`, ` 0`, `-0` は例外を無効化しない |
| Linux 以外 | この変数をこの分岐では読まない | 該当なし | 該当なし |

大文字小文字や後続文字、数値としての妥当性は検査しない。`0` 以外の値が「機能を有効化」するわけではなく、デフォルトと同じくキャッシュ等を考慮する分岐を許可する。文字列の優先順位や CLI による値の上書きはなく、同じ `open` 呼び出し中に一度ローカル変数へ読み取る。`static` cache はなく、次の `open` では環境を再読する（`src/core/expert_source.cpp:5930-5934,6103`）。

## 有効になる条件

- `ArenaExpertSource::open` が呼ばれ、RAM 判定が `FallBack` になった場合にのみ、値が cache 判定へ影響する。RAM が足りて `Load` になると値に関係なく通常読み込み、fallback が許可されず `Warn` または `Refuse` になる場合も cache の例外判定は行わない（`src/core/expert_source.cpp:6089-6106,6135-6147`; `include/strata/core/ple_residency.hpp:60-64`）。
- 例外判定は Linux の `#if defined(__linux__)` 内だけにある。Windows などではこの分岐を実行しない（`src/core/expert_source.cpp:6090-6106`）。設定登録上の backend は `cuda-hip`（`data/settings-register.json:940-950`）。
- プロセスが `--mmap-experts` を既に選んでいると `ArenaExpertSource::open` を通らず、変数はこの経路に影響しない（`src/program/generate.cpp:8062-8074,8292`）。
- キャッシュ例外を評価するには、プロセスに cgroup のハードメモリ上限が検出されていないこと（`hm.cgroup_limit == ~uint64_t{0}`）と `/proc/meminfo` の読み取り成功が必要。free page または破棄可能 cache が必要量を満たすか、hugetlb を使う経路で予約済みの free huge page が arena 全体を収容できると例外が成立する（`src/core/expert_source.cpp:6106-6122`; `include/strata/core/ple_residency.hpp:87-93`）。
- `STRATA_NO_LARGEPAGES` が設定されていると、その値が空でも huge-page 分の容量を判定から除外する。ただし通常の free page / cache 判定は残る（`src/core/expert_source.cpp:6110-6120`）。
- 通常の file fallback は既定で許可されるが、`STRATA_ARENA_RAM_FALLBACK=0`、明示的な `--ple-io ram`、または `--shared-expert-arena` があると許可されない。これらの場合、対象変数が cache 例外を抑止しても verdict は `Warn`（不足 RAM で読み込み継続）または cgroup 上限不足時の `Refuse` になり得る（`src/program/generate.cpp:8040-8046`; `include/strata/core/ple_residency.hpp:60-74`）。

## 実行時の詳細

通常の起動で arena を開くと、Strata は arena 必要量と RAM 状況から verdict を計算する。Linux で verdict が `FallBack`、cgroup 上限が未検出、かつ `/proc/meminfo` を読めた場合に限り、この変数を `file_cache_off` として確認する。値が unset・空・先頭文字が `0` 以外なら、free memory と破棄可能 cache、または arena 全体を収容する huge-page pool が不足を賄える場合に `file_cache_arena` を立て、arena を読み込む。先頭文字が `0` ならその判定ブロックを飛ばし、verdict に従って fallback に進む（`src/core/expert_source.cpp:6103-6122,6135-6147`）。

例外が成立した場合、専門家は arena に読み込まれ、通常の読み込み経路と同様にロード結果を使う。`0` で例外が抑止され、verdict が `FallBack` なら `open` は RAM 不足を返し、呼び出し側は `--mmap-experts` 相当のファイルソースへ切り替える。既定の fallback 時に静的 expert profile があり `STRATA_ARENA_FALLBACK_RESIDENT` が先頭 `0` でない場合は、さらに RAM copy の resident mode を選ぶ分岐がある（`src/program/generate.cpp:8292-8332`）。ファイルを開けず再試行となれば arena を改めて試す経路もある（`src/program/generate.cpp:8074-8084`）。

## ログと測定値

例外を使って arena を読み込むと、次の警告が `ram_warning_` に保存され、通常実行では stderr に出る。`--serve` では起動時に stderr と stdout の両方へ出す。メッセージ中の `STRATA_ARENA_FILE_CACHE=0 reads them from the file instead.` は設定例を示す（`src/core/expert_source.cpp:6124-6134`; `src/program/generate.cpp:8355-8357`）。

```text
the experts need ... GiB of RAM and ... GiB is free, but free memory, file cache and reserved huge pages can hold them, so they load anyway (same answers). STRATA_ARENA_FILE_CACHE=0 reads them from the file instead.
```

`0` で例外が使われず `FallBack` になった場合、既定の fallback が有効なら stderr に `strata generate: not enough RAM for the expert arena (...)` で始まる案内が出てファイルソースへ切り替わる。`--serve` では同じ案内を stdout にも出す（`src/program/generate.cpp:8297-8309`）。読み込み後には `strata generate: expert arena read ...` が stderr に出る（`src/core/expert_source.cpp:6331`）。この環境変数による性能測定値は、参照した資料にはない。

## 根拠

- 全候補名参照を確認した結果、本番ソースの読み取りは `src/core/expert_source.cpp:6103` の一箇所。ほかの完全一致はコメント（同ファイル 6099, 6127）、説明（`docs/DETAILS.md:744`）、設定登録（`data/settings-register.json:940-950`）。汎用 env helper や動的な名前渡しによる追加読み取りは確認されなかった。
- RAM verdict と fallback の規則: `include/strata/core/ple_residency.hpp:60-74`。
- cache / huge-page 容量の条件: `include/strata/core/ple_residency.hpp:87-103`; Linux 側の適用: `src/core/expert_source.cpp:6090-6137`。
- 呼び出しと stdout/stderr の結果: `src/program/generate.cpp:8040-8048,8062-8089,8292-8332,8355-8359`。
- `docs/DETAILS.md:741-748` は「`STRATA_ARENA_FILE_CACHE=0` は常にファイルから読む」と要約しているが、ソースでこの変数が効くのは Linux の `FallBack` verdict、cgroup 上限なし、`/proc/meminfo` 読み取り成功時に限定される。また fallback 不許可なら `Warn` で arena を読み続ける分岐がある。したがって上記説明はソース上の条件を省略した要約として扱った。
