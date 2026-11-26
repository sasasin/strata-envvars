# `STRATA_FILE_TIER_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux で `--mmap-experts` のファイル tier をページキャッシュ経由にするか、unbuffered read にするか決める際、メモリ上の余裕だけでキャッシュ可能と判定されたケースに限り、両経路の読み取り速度を測る起動時 probe を有効にする。測定結果は `file_tier_prefers_direct` の判定に使われ、モデル計算や expert の選択結果ではなく I/O 経路だけを変える。`STRATA_FILE_TIER_PROBE=0` はこの追加測定を抑止し、従来の room 判定を使う。読み取りと分岐は `engine/src/core/expert_source.cpp:959-1038`、速度判定は `engine/include/strata/platform/memory.hpp:63-78`。

## 値と判定

`std::getenv` の値の先頭文字が `'0'` かだけを見る。文字列全体の比較、数値変換、空白除去、大文字小文字変換はない。未設定、空文字、先頭が `0` 以外なら probe を許可し、`0` で始まる値は抑止する。したがって `0`、`0anything` は抑止、`1`、`true`、`false`、` 0`、`00` は許可される。設定値の範囲エラーはなく、先頭文字以降は無視される。判定箇所: `engine/src/core/expert_source.cpp:1014-1019`。

| 条件 | unset | probe を許可する値の例 | probe を抑止する値の例 |
|---|---|---|---|
| Linux の通常の file-tier room 判定 | 許可 | 空文字、`1`、`true`、` 0` | `0`、`0anything` |
| Linux の `STRATA_HIP_GFX906` 旧 room rule | probe 判定まで到達しない | 該当なし | 該当なし |
| Windows、SYCL 複製の Linux 経路、その他の OS | この変数を読まない | 該当なし | 該当なし |

## 有効になる条件

- 対象は `engine/src/core/expert_source.cpp` の Linux 実装。Windows は `experts_unbuffered` に委譲し、SYCL の複製 `engine/sycl/src/core/expert_source.cpp:395-422` にはこの変数も drive probe も実装されていない。Linux の `STRATA_HIP_GFX906` build は既定で旧 room rule を使うため probe に進まないが、`STRATA_FILE_CACHE_OLD_RULE` が設定されていれば先頭文字に基づいて `old_rule` を上書きできる（`engine/src/core/expert_source.cpp:995-1002`）。
- `--mmap-experts` と resident RAM budget があるとき、初期判定は `FileExpertSource::set_unbuffered` から呼ばれる。`--ssd-experts` は `set_unbuffered(..., force=true)` の強制経路で先に unbuffered を開くため、この変数の判定を通らない（`engine/src/program/generate.cpp:8648-8658`、`engine/src/core/expert_source.cpp:2842-2858`）。resident budget がなく `--ssd-experts` もない場合、room 判定自体が呼ばれない（`engine/src/program/generate.cpp:8651-8674`）。
- 同じ Linux 判定で、空でない `STRATA_UNBUFFERED_LOAD` は本変数より先に処理される。先頭文字が `0` なら cache、そうでなければ unbuffered を返し、drive probe は行わない（`engine/src/core/expert_source.cpp:963-972`）。
- probe は room 判定が cache 可 (`keepable`)、旧 rule ではなく、`read_bytes > 0` であり、`held < 0.5` のときだけ候補になる。`held` は `max(avail - arena_bytes - 1 GiB, 0) / read_bytes`。それ以外は本変数に関係なく probe をスキップし、元の room rule の結果を使う（`engine/src/core/expert_source.cpp:995-1033`）。
- `avail` は Linux の利用可能 RAM で、既定では `STRATA_FILE_TIER_HONEST` が `0` でない場合に host-memory sampler のより小さい値を採用する。この変数は probe の判定条件に間接的に影響する（`engine/src/core/expert_source.cpp:973-987`）。
- probe 可能なときでも測定不能なら cache を維持する。正常測定時は direct が 4 GB/s 以上で、かつ held が 30% 未満なら cached 経路の 1.3 倍以上、30%以上50%未満なら1.5倍以上の場合だけ unbuffered を選ぶ。それ以外は cache を維持する（`engine/src/core/expert_source.cpp:1022-1032`、`engine/include/strata/platform/memory.hpp:73-78`）。

## 実行時の詳細

設定値は `file_tier_unbuffered` が呼ばれるたびに読み直され、対象値そのものを保存する static cache はない。通常の初期判定に続き、RAM copy の構築後に Linux で `--mmap-experts` かつ resident budget がある場合、`recheck_unbuffered` が実際に残った RAM copy と file tier のサイズで再判定する。この再判定でも他の条件を満たせば設定値が再評価される。probe の測定結果だけは `file_tier_probe` 内の mutex 保護された static memo に成功・失敗とも保存され、同一プロセスで後から条件を満たしても再測定しない（`engine/src/core/expert_source.cpp:853-858`、`963-1033`、`2867-2903`、`engine/src/program/generate.cpp:12219-12229`）。

probe は最大サイズの expert file 1 個を選び、1 MiB のランダム領域を direct 経路（`O_DIRECT`、8 threads）と mapped page-cache 経路（3 threads）で各2 round測る。各経路の最高転送速度を比較し、既存の page-cache resident 領域を避ける。file が見つからない、ファイルが小さすぎる、open/mmap/mincore/read が失敗する、測定バイト数がゼロなどでは測定失敗となり、cache を選ぶ。測定用 read の deadline は各 pass 1.5 秒（`engine/src/core/expert_source.cpp:845-955`）。

選ばれた経路の設定後、`open_direct` が失敗すれば unbuffered 化に失敗し、呼び出し元では mapped/cache 経路が残る。resident copy の構築後の再判定で cache に切り替わる場合は direct handle を閉じ、逆の場合は direct handle を開く（`engine/src/core/expert_source.cpp:2770-2813`、`2842-2903`）。

## ログと測定値

この変数専用の警告やエラー出力はない。generate 経路は初期判定の結果を `strata generate: the file tier reads %s (%s)` で stderr に出す。probe 成功時は理由文字列に cache が保持できる割合と direct/cached の GB/s、倍率、選択結果が付く。測定失敗時は `; the drive probe could not run, the file cache stays` が付く。RAM copy 構築後の再判定も結果と理由を出力する（`engine/src/program/generate.cpp:8654-8658,12224-12229`）。

`docs/release-notes-0.2.1.md:49` は Linux の probe を説明し、96個の1 MiB片を測る旨や報告された drive の性能差を記録している。現行コードでは各 pass が最大96片を選び、2 round測定する（`engine/src/core/expert_source.cpp:865-867,881-895`）。同じ release note は測定値を特定機種・状態の報告として記しており、ここでは一般的な性能保証として扱わない。`docs/DETAILS.md` の mmap 説明（`docs/DETAILS.md:266`）とも照合したが、この変数の probe 判定条件は同資料には記載されていない。

## 根拠

- 候補名の実読み取りと値判定、room 条件、fallback: `engine/src/core/expert_source.cpp:963-1038`
- Linux probe の測定とプロセス内 memo: `engine/src/core/expert_source.cpp:845-957`
- 転送速度の threshold: `engine/include/strata/platform/memory.hpp:63-78`
- 初期適用と `--ssd-experts` 強制経路: `engine/src/core/expert_source.cpp:2842-2858`、`engine/src/program/generate.cpp:8648-8658`
- RAM copy 後の再判定と結果ログ: `engine/src/core/expert_source.cpp:2867-2903`、`engine/src/program/generate.cpp:12219-12229`
- SYCL 実装との差: `engine/sycl/src/core/expert_source.cpp:395-422`
