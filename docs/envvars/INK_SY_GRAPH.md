# `INK_SY_GRAPH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 の Intel SYCL runner で、条件を満たす単一 token の forward step を SYCL command graph に記録して再利用するかを選ぶ。通常の kernel enqueue と同じ `enqueue_all` の処理を graph 記録・再生経由にする。設定だけでは graph 使用は保証されず、下記の実行条件と graph API の利用可否に依存する。読み取りと適用判定は `InkSyRunner::sy_graph_enabled` と `InkSyRunner::forward_batch` にある（`engine/src/inkling2/sycl/ink_sy_runner.h:430-433, 515-522`）。

この実装は `STRATA_ENABLE_SYCL=ON` で構成する実験的な独立 SYCL backend に属する。通常の CUDA/HIP/CPU build ではこの runner は使われない（`engine/CMakeLists.txt:23-33`）。Inkling-2 SYCL backend が実際に選択されて forward した場合の設定であり、CLI 引数による上書きはコード上にない（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:140-188`）。

## 値と判定

`std::getenv("INK_SY_GRAPH")` の結果が null でなく、かつ最初の文字 `e[0]` が文字 `'1'` と一致するかだけを判定する。文字列全体の parse、数値変換、trim、大文字小文字変換はしない（`engine/src/inkling2/sycl/ink_sy_runner.h:430-433`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| SYCL runner の初回判定 | `false` | `1`, `1anything`, `10` | 空文字, `0`, `0anything`, `true`, ` 1` |

空文字は環境変数として設定済みでも先頭文字が終端文字なので無効。`1` の後ろの文字は無視される。判定結果は関数内 `static const bool` に保存され、プロセス内で初回評価した値が以後の呼び出しにも使われる。実行中に環境を変更しても再評価されない（`engine/src/inkling2/sycl/ink_sy_runner.h:430-433`）。

## 有効になる条件

`INK_SY_GRAPH` が有効でも、forward step ごとの `graph_ok` が真になる必要がある（`engine/src/inkling2/sycl/ink_sy_runner.h:515-522`）。

- 対象は Inkling-2 の SYCL runner。トップレベル CMake の `STRATA_ENABLE_SYCL` が有効でなければ、この backend は構成されない（`engine/CMakeLists.txt:23-33`）。
- `M == 1`（1 token の step）。複数 token の prompt/prefill や batch step では graph を試さない。
- `INK_SY_DEBUG` の先頭文字が `'1'` である単一 token debug step でないこと。debug 判定にも空文字・先頭文字のみの確認を使う（`engine/src/inkling2/sycl/ink_sy_runner.h:515-519`）。
- SYCL profiler が有効でないこと（`!sy_prof().on`）、hybrid engine が active でないこと、`mod->ep2_active && mod->q_peer` の dual-GPU peer 経路でないこと。
- `logits_mode <= 1` であること。複数 token 分の logits を求める mode 2 は対象外。
- image embedding の入力が渡されていないこと。
- その runner で以前に graph 記録または実行が失敗していないこと（`!graph_failed`）。

CLI/サーバーのどの呼び出し元かだけでは有効性は決まらず、runner に渡された各 chunk の `M`、logits mode、画像入力などで判定される。backend wrapper は batch を `runner_.max_batch` 単位に分割し、各 chunk について `forward_batch` を呼ぶ（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:140-185`）。

## 実行時の詳細

`forward_batch` は上記条件を満たすと `run_graph(graph_key, ...)` を呼び、key ごとの graph がまだなければ queue を待機させ、`enqueue_all(true)` を recording し、finalize して map に保存する。その後は保存済み graph を queue に submit する。graph key は logits mode、出力先、DSpark context と slot などから作られるため、異なる key は別々に記録される（`engine/src/inkling2/sycl/ink_sy_runner.h:438-453, 520-524, 926-935`）。runner の存続中は graph map が保持され、release 時に待機して map を消す（`engine/src/inkling2/sycl/ink_sy_runner.h:165-176`）。

記録時の `enqueue_all(true)` と通常経路の `enqueue_all(false)` は同じ enqueue lambda を使う。capturing 中は logits/argmax の host へのコピーを省き、graph submit 成功後に必要な mode 1 出力をコピーしてから待機する。graph を使わない場合は `enqueue_all(false)` を実行し、いずれも最後に `wait()` して `forward_batch` は true を返す（`engine/src/inkling2/sycl/ink_sy_runner.h:523, 886-896, 926-941`）。

ビルド時に `SYCL_EXT_ONEAPI_GRAPH` が定義されていない場合、`run_graph` は graph を使わず `graph_failed` を立てて false を返すため、その step は通常経路に進み、その runner では以後 graph を試さない（`engine/src/inkling2/sycl/ink_sy_runner.h:438-464, 926-935`）。macro があり graph 作成・記録・submit が `std::exception` を投げた場合も、`graph_failed` を立て、queue 待機を試みて false を返し、通常 enqueue に fallback する（同 `:439-459, 926-935`）。

## ログと測定値

graph が新規記録されたとき stderr に `[ink_sycl] SYCL graph recorded (key %llu)` を出す。graph API の例外時は stderr に `[ink_sycl] SYCL graph off: %s` と例外の `what()` を出す。環境変数が unset/無効、または `graph_ok` の条件を満たさない場合に、この変数を理由とするログはない。`SYCL_EXT_ONEAPI_GRAPH` が未定義の fallback にも、このコードからは graph off のログは出ない（`engine/src/inkling2/sycl/ink_sy_runner.h:438-464, 518-519`）。

runner のコメントには約2,000 kernel launches を1 submissionにするという説明があるが、これは実装コメントであり、条件付きの測定値や比較結果は `docs/DETAILS.md` に確認できないため、性能値としては記載しない（`engine/src/inkling2/sycl/ink_sy_runner.h:516-519`）。この環境変数による明示的な終了・エラー返却はなく、graph 実行失敗時は通常 enqueue へ fallback する。

## 根拠

- `engine/CMakeLists.txt:23-33` — SYCL backend が独立した opt-in build であること。
- `engine/src/inkling2/sycl/ink_sy_runner.h:430-433` — 環境値の読み取り、判定、static cache。
- `engine/src/inkling2/sycl/ink_sy_runner.h:438-464` — graph 記録・submit・失敗時処理と macro 非対応時の fallback。
- `engine/src/inkling2/sycl/ink_sy_runner.h:515-522, 886-896, 926-941` — step ごとの有効条件、出力、通常経路への fallback。
- `engine/src/inkling2/sycl/ink_sycl_backend.cpp:140-188` — backend wrapper から runner への batch/chunk 呼び出し。
- `engine/src/inkling2/sycl/ink_sy_runner.h:165-176` — graph map と runner release 時の破棄。
