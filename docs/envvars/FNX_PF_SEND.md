# `FNX_PF_SEND`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata-split` の Flash-Next prompt path がカード間のチャンク和を host memory 経由の ring で送る際、送信元カードの device buffer から次カードの host receive buffer へのコピー方法を切り替える。値が `kernel` のときは `k_pfr_copy` カーネルがコピーし、それ以外は `cudaMemcpyAsync(..., cudaMemcpyDefault, ...)` を使う。ring の計算や和の算術自体を切り替える設定ではない（`engine/src/split/src/engine.cu:1-2`、`engine/src/split/src/pf_common.cuh:261-281, 338`、`engine/src/split/src/prefill.cu:311-313, 1222-1223`）。

## 値と判定

`Engine::prefill_alloc` の初期化中、各カードの `PfRing` に対して `std::getenv` を呼び、値全体を `std::strcmp(sk, "kernel") == 0` で比較する。大文字小文字を区別し、前後の空白を除去せず、数値や真偽値として parse しない。無効値でもエラーや警告は出さず、通常の非同期コピーを使う（`engine/src/split/src/prefill.cu:854-860, 1169-1176, 1222`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA / HIP の `strata-split` prompt ring | `send_kernel` は `false` | `kernel` | 空文字、`0`、`1`、`true`、`Kernel`、` kernel`、`kernel `、`kernel-anything` |

## 有効になる条件

- この設定を読むのは `engine/src/split/src/prefill.cu` の `Engine::prefill_alloc` である。CMake は `strata-split-2/3/4` を CUDA または HIP 用に構成し、両方でこの実装をコンパイルする（`engine/src/split/CMakeLists.txt:116-145`）。
- prompt chunk の和が `pf_ring` から `pf_ring_run` に進み、ring plan に `SEND` 操作がある場合に送信方式が使われる（`engine/src/split/src/prefill.cu:723-755`、`engine/src/split/src/pf_common.cuh:261-281, 338`）。
- HIP では、RCCL の all-reduce が選ばれると `pf_ring` が先に return する。また小チャンク all-to-all が有効で `C <= p.a2a_rows` の場合も ring を通らない。この場合 `FNX_PF_SEND` の設定は使われない（`engine/src/split/src/prefill.cu:726-755`）。
- 同じ ring 経路でも、`FNX_PF_SEND` が変えるのは `SEND` 操作の device-to-host コピーだけである。ring の `PASS` 操作で host buffer 間を転送するコピーには影響しない（`engine/src/split/src/pf_common.cuh:275-281, 338-347`）。
- CLI 引数、設定ファイル、別の環境変数による上書きや優先順位は、この読み取り箇所にはない。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が prompt path の buffer を初期化し、カードごとの `PfRing::send_kernel` に判定結果を格納する（`engine/src/split/src/engine.cu:317-319`、`engine/src/split/src/prefill.cu:854-860, 1169-1223`）。そのため値はリクエストごとには読み直されず、構築後の環境変更はその engine の `send_kernel` に反映されない。

ring の `SEND` 操作では、`send_kernel` が true なら行数が 0 より大きいとき `k_pfr_copy` を現在の stream に enqueue し、直ちに分岐を返る。このカーネルは `uint4` 単位で `src` から `dst` にコピーする。false なら同じ送信箇所で `cudaMemcpyAsync` を enqueue する（`engine/src/split/src/pf_common.cuh:124-129, 261-281, 338`）。通常の ring 操作は `pf_ring_run` の後に `cudaGetLastError` を `"ring"` のラベルで確認する（`engine/src/split/src/prefill.cu:754-755`）。prefill pass の stream 完了待ちは最大 120 秒で、ring flag が進まない場合は `prefill: a pass did not finish in 120 s (a ring step's flag never came?)` を投げる。完了後に検出された ring error も `prefill: ring error <値>` として投げる（`engine/src/split/src/prefill.cu:1788-1803`）。

## ログと測定値

この変数の値や選択されたコピー方式を示す専用ログは見つからない。通常の prefill timing 表示は別の `FNX_PF_TIMING` 条件であり、この変数の値によって出力されるものではない（`engine/src/split/src/prefill.cu:1831-1841`）。ソース内コメントには `FNX_PF_SEND` の性能測定値がないため、性能差は記載しない。

## 根拠

- `engine/src/split/src/prefill.cu:301-315, 854-860, 1169-1223` — `PfRing` の状態、prompt buffer 初期化、環境変数の読み取り。
- `engine/src/split/src/pf_common.cuh:121-129, 261-281, 338-347` — ring のコピー kernel、送信分岐、他の host-to-host 転送。
- `engine/src/split/src/prefill.cu:723-755, 1788-1803` — ring 呼び出しと観測可能な完了・失敗経路。
- `engine/src/split/CMakeLists.txt:116-145` — CUDA/HIP の `strata-split` target。
