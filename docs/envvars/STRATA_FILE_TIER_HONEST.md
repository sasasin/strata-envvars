# `STRATA_FILE_TIER_HONEST`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の file tier が buffered / unbuffered I/O のどちらを使うか決める際、page cache に使える RAM の見積もりに会話メモリ sampler の値を加えるかを制御します。既定では sampler を使い、`STRATA_FILE_TIER_HONEST=0` で使わない設定です。これはメモリ見積もりを通じて I/O 経路を選ぶだけで、sampler の値や file tier のデータ自体を変更しません（`src/core/expert_source.cpp:927-936`）。

## 値と判定

変数全体を parse せず、`getenv()` の結果が未設定か、先頭文字が `'0'` かだけを見ます。

| 値 | sampler を使うか |
|---|---|
| 未設定 | 使う |
| 空文字 | 使う（設定値は非 null で先頭文字は `\0`） |
| `0`、`0anything` | 使わない |
| `1`、`true`、`false`、その他 `'0'` 以外で始まる文字列 | 使う |

大文字小文字、数値としての妥当性、後続文字は検査しません。読み取りは static cache されず、`file_tier_unbuffered()` の呼び出しごとに判定します（`src/core/expert_source.cpp:934-936`）。

## 有効になる条件

- Linux ビルドで `FileExpertSource` を `--mmap-experts` 経路に使い、`--resident-budget-gib`（`o.resident_budget > 0`）を指定した場合、file tier の I/O 経路判定で参照されます。初回は `src.set_unbuffered()` から呼び出されます（`src/program/generate.cpp:7444-7445,7477-7481`; `src/core/expert_source.cpp:2532-2543`）。
- RAM copy 構築後、起動時 unbuffered 状態を保持していない場合は再判定されます。再判定では実際に RAM に保持された complement と、ファイルから読む残りの expert bytes を使います（`src/program/generate.cpp:10484-10494`; `src/core/expert_source.cpp:2551-2577`）。
- `STRATA_UNBUFFERED_LOAD` が空でない値で設定されている場合は、それが優先され、file tier 判定はそこで返るため `STRATA_FILE_TIER_HONEST` は読まれません。`STRATA_UNBUFFERED_LOAD` の先頭文字が `0` なら buffered、そうでなければ unbuffered を要求します（`src/core/expert_source.cpp:918-921,2551-2555`）。
- `--resident-budget-gib` は判定に渡す RAM copy サイズを決めます。`--memory-limit-mib` の operator cap はこの sampler 呼び出しに渡されず、見積もりに適用されません（`src/core/expert_source.cpp:932-935`; `src/program/generate.cpp:7477-7481`）。`STRATA_FILE_CACHE_OLD_RULE` は後段の page-cache 判定式を切り替え、`STRATA_FILE_TIER_PROBE` は条件付き drive probe を無効化できます（`src/core/expert_source.cpp:937-968`）。
- Windows では別の `experts_unbuffered()` 判定、Linux 以外では buffered 読み取り固定の分岐を使うため、この変数は判定に使われません（`src/core/expert_source.cpp:914-916,983-986`）。GPU backend の種類による本変数の分岐はありません。

## 実行時の詳細

Linux の通常の見積もり `avail` は `MemAvailable` を読み、見える cgroup v1/v2 の制限・使用量も考慮します（`src/core/expert_source.cpp:414-490,516-522`）。変数が有効（unset または先頭文字が `0` 以外）なら、`sample_host_memory(..., 0)` の成功値 `honest->available` と比較し、小さい方を `avail` に採用します。sampler が値を返さない場合は元の `avail` のままです。`explicit_limit=0` なので、sampler のこの呼び出しには `--memory-limit-mib` の明示上限を適用しません（`src/core/expert_source.cpp:934-936`; `src/core/conversation_memory.cpp:261-280`）。

調整後の `avail` を file-cache room 判定に渡します。通常ルールでは 1 GiB の余白、read bytes の 5%（最低 512 MiB、最大 read bytes）を cache が保持可能かで buffered を選びます。gfx906 HIP build または `STRATA_FILE_CACHE_OLD_RULE` による旧ルールでは read bytes 全量と既定 4 GiB 余白の判定になります。通常ルールで cache が保持可能でも、held 比率が 50% 未満などの条件を満たし drive probe が成功して十分速い場合は unbuffered が選ばれることがあります（`src/core/expert_source.cpp:937-982`; `include/strata/platform/memory.hpp:54-60,73-78`）。従って `STRATA_FILE_TIER_HONEST=0` は unbuffered を直接指定する値ではなく、後段判定に使う `avail` の数値を変える場合があります。

unbuffered が選ばれた場合、Linux では expert ファイルを `O_DIRECT` で開きます。open に失敗すると direct handle を閉じ、buffered 経路を使う理由を `why` に付けて戻ります（`src/core/expert_source.cpp:2487-2498,2532-2543`）。初回判定の結果は `strata generate: the file tier reads unbuffered (...)` または `... through the file cache (...)` と stderr に出ます（`src/program/generate.cpp:7477-7481`）。RAM copy 後に結果が変われば再判定のログも出て、buffered へ切り替わった場合は `strata: expert reads now go through the file cache (...)` と出ます（`src/program/generate.cpp:10488-10507`）。本変数専用のログや終了・失敗経路はありません。

## 根拠

- `src/core/expert_source.cpp:912-936` — Linux 判定、`STRATA_UNBUFFERED_LOAD` 優先、sampler 値との最小値。
- `src/core/expert_source.cpp:937-982` — メモリ見積もりから buffered / unbuffered 経路を選ぶ条件。
- `src/core/expert_source.cpp:2532-2543,2551-2577` — 初回選択・RAM copy 後の再判定と経路切替。
- `src/core/expert_source.cpp:2487-2498` — Linux direct open と失敗時 fallback の理由。
- `src/core/conversation_memory.cpp:261-280` — sampler の読み取りと明示上限が 0 の場合の処理。
- `src/program/generate.cpp:7477-7481,10484-10507` — 判定の呼び出し条件と観測できるログ。
