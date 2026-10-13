# `STRATA_ARENA_RELEASE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

ファイル-backed の expert arena（`STRATA_ARENA_MMAP` の mapped arena）で、**GPU cache が保持している expert のページを起動時に OS へ返す処理（`MADV_DONTNEED`）を、返さない方向へ切り替える开关**です。既定では返します。この変数を `0` で始まる値にすると、その起動時の release をスキップしてページを残します。

読み取りは `src/program/generate.cpp:6127` の 1 箇所だけで、SYCL に同一ロジックのミラーがあります（`sycl/src/program/generate.cpp:5784`）。CUDA/HIP/SYCL のビルドでこの判定箇所は共通です（backend による分岐なし）。

効果の範囲は**起動時の 1 回の release だけ**です。decode 中の入れ替え（adaptive swap）で GPU に載った expert のページを返す呼び出しは、この変数を見ません（`src/program/generate.cpp:8330`、`8783`、`11350` は無条件、`10734`、`12512` は Windows 限定）。したがって `=0` は「decode 中の release を止める」意味ではありません。

## 値と判定

文字列全体を parse しません。`std::getenv()` が非 null のとき、**先頭文字 `e[0]` だけが `'0'` と等しいか**を比較します。

| 状態 | `keep`（`src/program/generate.cpp:6127`） | 起動時の release |
|---|---|---|
| 未設定（`nullptr`） | false | 実行する（既定） |
| 空文字 `""` | false（`e[0]` は `\0`） | 実行する |
| `0` | true | しない |
| `0anything`（先頭が `0`） | true | しない |
| `1`、`true`、`on` など | false | 実行する |
| ` 0`（先頭が空白）、`0` 以外で始まる値 | false | 実行する |

大文字小文字・数値としての妥当性・末尾は検査しません。有効な値は「先頭文字 `0`」だけで、それ以外はすべて release 実行側です。

判定結果は `static const bool` に入るため、このブロックが最初に実行されたときの環境の値で固定され、プロセス起動後の変更は反映されません。

## 有効になる条件

値が `0` で始まっても、次の条件が揃わなければこの判定は実行されません（ブロック自体に入らない）。

- `--mmap-experts` を**使っていない**。使っている場合は `srcp` が `FileExpertSource` になり、その `release()` は Linux で常に 0 を返します（`src/core/expert_source.cpp:2591-2594`）。Windows での file tier の trim は別変数 `STRATA_FILE_RELEASE` の仕事で、意味が逆です（`src/core/expert_source.cpp:2547-2550`）。
- `STRATA_ARENA_MMAP=1`（Linux）で arena が実際に mapped である。`ArenaExpertSource::release()` は `map_ == nullptr` なら 0 を返します（`src/core/expert_source.cpp:4697`）。`map_` が set されるのは `open()` の `arena_mmap` 分岐（`src/core/expert_source.cpp:4454-4467`）だけで、通常の pinned arena 経路では `map_` は nullptr のままです。Windows では `arena_mmap` が `false` に固定（`src/core/expert_source.cpp:4451-4452`）で、`release()` も `_WIN32` で 0 を返す（`4693-4695`）。
- device-hit 経路のブロックが実行される: `hit_fn != nullptr`（`o.no_pool` でない、`o.expert_cache > 0`、`src/program/generate.cpp:5629-5630`）、`profile` が空でない（`--expert-profile` で読む、`3492`）、`!o.no_pool`、`!o.no_capture`、`!o.no_token_graph`、`--dump-layers`/`--dump-halves` でファイルが開けている（`layer_dump == nullptr && half_dump == nullptr`）。条件は `src/program/generate.cpp:6103-6104`。

条件が揃ったとき、release は residency table（`host_res`）を構築した直後、token graph の capture 前（`6147` 以降）で 1 回走ります。対象は `host_res[i] != kNotResident` の expert、つまり GPU cache が slot を持っている pair です（`6131-6133`）。

## 実行時の詳細

`keep` が false のとき、resident expert ごとに `ArenaExpertSource::release(layer, expert)` を呼びます（`src/program/generate.cpp:6131-6133`）。

- 範囲は blob の**内側に収まる完全ページだけ**です。`off = (blob_offset + 4095) & ~4095`（切り上げ）、`end = (blob_offset + blob_bytes) & ~4095`（切り下げ）。境界を共有するページ（隣の expert が読む可能性のあるページ）は残します（`src/core/expert_source.cpp:4699-4701`、注釈 `4686-4691`）。丸めに使う値は 4095 で、`sysconf(_SC_PAGESIZE)` は使っていません。
- `end <= off`（blob が 1 ページに満たない、または境界共有のみ）なら 0 を返して何もしません（`4701`）。
- `madvise(..., MADV_DONTNEED)` が失敗しても 0 を返します（`4702`）。
- 返される値は **advice したバイト数**であり、OS が実際に回収した物理 RAM の測定値ではありません。注釈によると、これらのページはプロセスのアドレス空間から外れるだけで、page cache には clean な unmapped ページとして残り、圧力があったときに最初に返される分になります。CPU がその expert を再び読んだときは minor fault 1 回で済みます（`src/core/expert_source.cpp:4686-4691`）。
- release の直後、GPU が保持していない expert に対して `prefetch`（`MADV_WILLNEED`）が走ります。これはこの変数の判定とは無関係に常に実行されます（`src/program/generate.cpp:6138-6143`、`src/core/expert_source.cpp:4674-4684`）。

## 観測できる結果

- release したバイト数が 0 より大きいときだけ stderr に出ます（`src/program/generate.cpp:6134-6136`）:

  ```
  strata generate: expert arena: %.2f GiB of VRAM-held experts handed back to the OS
  ```

  `=0` のときこの行は出ません（`released` が 0）。
- `STRATA_RSS_TRACE` が設定されていると、このブロックは `before the release` / `after the release` / `after the prefetch hints` の 3 点で `RssFile` を stderr に出します（`src/program/generate.cpp:6128,6137,6145`、`rss_probe` の定義 `230-242`）。`rss_probe` は `/proc/self/status` を開くので、Linux 以外では何も出ません。この gate は `getenv(...) != nullptr`（空文字でも有効）で、`STRATA_ARENA_RELEASE` の判定とは別です。

## 資料との照合

`docs/DETAILS.md:199-204` は `STRATA_ARENA_MMAP` の説明の中で「the pages of the experts a GPU holds are handed back to the OS」と書き、この起動時の release を既定の動作として述べています。`STRATA_ARENA_RELEASE` 自体の名前は `docs/` に現れません。ソースにこの名前の値域・効果の追加条件はなく、上の一覧がコードから確認できる範囲です。

## 根拠

- 読み取り（唯一）: `src/program/generate.cpp:6127`、SYCL ミラー `sycl/src/program/generate.cpp:5784`。
- 効果（release 呼び出しとログ）: `src/program/generate.cpp:6128-6146`、`sycl/src/program/generate.cpp:5785-5803`。
- 実装（Linux の madvise、Windows は 0）: `src/core/expert_source.cpp:4686-4705`、`sycl/src/core/expert_source.cpp:3600-3619`。
- mapped arena の条件: `src/core/expert_source.cpp:4445-4482`（`map_` の set）、`include/strata/core/expert_source.hpp:950`。
- ブロックに入る条件: `src/program/generate.cpp:6103-6104`、`5629-5630`、`3492`。
- decode 中の release はこの変数を見ない: `src/program/generate.cpp:8330`、`8783`、`11350`、`10734`、`12512`。
- 別名前の混同: `--mmap-experts`（`FileExpertSource`）側の trim は `STRATA_FILE_RELEASE` で制御され、`src/core/expert_source.cpp:2547-2550`。
