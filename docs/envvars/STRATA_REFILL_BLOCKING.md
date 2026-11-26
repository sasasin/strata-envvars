# `STRATA_REFILL_BLOCKING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプト処理のため一時的に借りた expert-cache slot を返す際に使う refill API を切り替える。CUDA/HIP 実装では unset 時に queued copy、設定時に blocking copy を選ぶ。SYCL 実装でも `fill_slot_queued` と `fill_slot_blocking` の選択を切り替えるが、現行の `fill_slot_queued` 自体も各 copy の `.wait()` を呼ぶ。設定値は数値や真偽値として解釈されない。`engine/src/program/generate.cpp:674-677,20502-20516,24184-24199`、`engine/sycl/src/program/generate.cpp:318-321,11345-11353,13394-13413`、`engine/sycl/src/core/expert_cache.cpp:914-987`。

## 値と判定

両実装とも `std::getenv(...) != nullptr` だけを見ており、文字列を parse しない。変数が存在すれば値が空文字でも有効となり、値の文字・数値としての妥当性は判定しない。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP（`engine/src`）・SYCL（`engine/sycl/src`） | `false`。借用 slot の refill は queued 経路 | `1`、`true`、空文字を含む、環境変数が存在するすべての値 | なし。`0`、`false`、任意文字列も「設定あり」として有効 |

関数内 `static const bool` に初回評価結果を保存する。したがって最初の `refill_blocking()` 呼び出し後にプロセス環境を変更しても、そのプロセス内では反映されない。CLI 引数や設定ファイルによる上書き処理はこの変数の読み取り経路にはない。`engine/src/program/generate.cpp:674-677`、`engine/sycl/src/program/generate.cpp:318-321`。

## 有効になる条件

- 環境変数が設定され、かつ prompt prefill が cache slot を借りて使用し、その slot を返すための refill が発生する必要がある。slot を借りない実行では切替箇所に到達しない。CUDA/HIP の単一 prompt 経路では `--no-prefill-borrow`、slot が不要・不足する場合、または Metal で `k` を 0 にする場合など、借用しない経路がある。`engine/src/program/generate.cpp:24055-24075,24184-24199`。
- CUDA/HIP の段階分割 prompt 経路と単一 prompt 経路、ならびに SYCL の段階分割・単一 prompt 経路に分岐がある。`STRATA_REFILL_BLOCKING` はこれら refill の各 slot 転送を選ぶ。CUDA/HIP の段階分割経路で `STRATA_REFILL_PARTS` が有効でも、この変数が有効なら blob-parts の queued 転送を選ばず、通常 blob の blocking refill に進む。`engine/src/program/generate.cpp:20502-20516,24186-24195`、`engine/sycl/src/program/generate.cpp:11345-11353,13394-13409`。
- `--no-prefill-borrow` などにより slot が借用されなければ、この変数単独では prompt buffer の割当方法を変更しない。`engine/src/program/generate.cpp:1001-1002,4035,24067-24075`。

## 実行時の詳細

未設定時は各 lent slot に `fill_slot_queued` を呼び、設定時は各 slot ごとに `fill_slot_blocking` を呼ぶ。CUDA/HIP の blocking 実装は `cudaMemcpy`、queued 実装は `cudaMemcpyAsync` を使い、段階分割経路では unset 時に複数 stage の queued copy を発行してから `sync_queued` する。SYCL 側では両 API が queue の `memcpy(...).wait()` を呼ぶため、変数 unset 時も copy ごとに wait する。SYCL の単一 prompt 経路は unset 時に最大256件ごとの追加 `sync_queued` も行い、設定時はその追加同期を省く。CUDA/HIP では blocking 時に async 読み込み通知 `note_async_read` を行わない。完了後の residency table 更新・slot の返却は同じ refill 処理に残る。`engine/src/core/expert_cache.cpp:864-897,900-919`、`engine/sycl/src/core/expert_cache.cpp:914-969,971-1000`、`engine/src/program/generate.cpp:20502-20529,20543-20565`、`engine/sycl/src/program/generate.cpp:11341-11371,11377-11398,13394-13413`。

CUDA/HIP の単一 prompt 経路では、設定時に各 slot を `fill_slot_blocking` で戻し、未設定時に queued copy 後 `sync_queued` を呼ぶ。SYCL の単一経路では同じ設定により呼ぶ API が変わるが、unset 時の `fill_slot_queued` も各 copy で wait する。unset 時にだけ最大256件ごとの追加 `sync_queued` がある。`engine/src/program/generate.cpp:24184-24205`、`engine/sycl/src/program/generate.cpp:13391-13421`、`engine/sycl/src/core/expert_cache.cpp:971-1000`。

## ログと測定値

この変数専用の有効・無効ログはない。単一 prompt 経路では refill 成功時に `strata generate: %zu lent slots refilled in %.1f ms` を stderr に出す。転送失敗時は `strata generate: refilling a lent slot failed: %s`、queued 同期失敗時は `strata generate: refilling the lent slots failed: %s` を出して `return 1` する。SYCL の単一経路も同じ失敗文言で `return 1` する。段階分割経路は `STRATA_TRACE` が設定されている場合に限り、成功後 `strata trace: refilled %lld slots on %lld stage(s) in %.1f ms` を stderr に出す。`engine/src/program/generate.cpp:24189-24207,20561-20567`、`engine/sycl/src/program/generate.cpp:11391-11395,13397-13420`。

## 根拠

- 読み取りと static cache: `engine/src/program/generate.cpp:674-677`、`engine/sycl/src/program/generate.cpp:318-321`。
- CUDA/HIP 段階分割 refill: `engine/src/program/generate.cpp:20502-20529`。
- CUDA/HIP 単一 prompt refill と借用抑止条件: `engine/src/program/generate.cpp:24055-24075,24184-24207`。
- SYCL 段階分割 refill: `engine/sycl/src/program/generate.cpp:11341-11371`。
- SYCL 単一 prompt refill: `engine/sycl/src/program/generate.cpp:13391-13421`。
- cache の blocking / queued 実装: `engine/src/core/expert_cache.cpp:864-919`、`engine/sycl/src/core/expert_cache.cpp:914-987`。
