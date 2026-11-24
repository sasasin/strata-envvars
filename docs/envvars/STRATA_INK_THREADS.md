# `STRATA_INK_THREADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 Inkling2 の `InkHybridEngine` が使う CPU ワーカープールのスレッド数を指定する。`start_workers()` はこの値で `n_threads` を上書きし、ドアベル経由の CPU expert 評価や verify group の処理を並列化する。GPU 上だけで expert を処理する設定では、ホスト側 expert がなくプールが開始されないため、この値は使われない。`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1788,1826-1828`、`engine/src/inkling2/cuda/ink_hybrid.cuh:1731-1752,1880-1889`。

## 値と判定

`start_workers()` の初回プール開始時に `std::getenv` で設定有無を調べる（すでに `active` なら読み取り前に return）。unset の場合、引数 `num_threads` が正ならその値、そうでなければ論理 CPU 数の半分を基準に 2〜16 の範囲で選んだ値を使う。環境変数が設定されていれば `std::atoi` の変換結果を 1〜128 に clamp する。文字列全体の妥当性検査やエラー報告はない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・例 |
|---|---|---|---|
| CUDA Inkling2 の `start_workers()` | `num_threads > 0` ならその値。それ以外は `min(16, max(2, ink_logical_cpus()/2))` | 変換後の値を 1〜128 に clamp。例: `1`→1、`12junk`→12、`999`→128 | `0`、`-4`、`junk`、空文字は `atoi` で 0（または負値）となり 1。`0anything` も 1 |

`atoi` のため、先頭の空白や符号は数値変換で扱われ、数値の後ろの文字列は無視される。`true` / `false` や大文字小文字を判定する仕組みはない。`engine/src/inkling2/cuda/ink_hybrid.cuh:1781-1783`。

## 有効になる条件

- CUDA backend を含む Inkling2 実装であること。該当コードは `engine/src/inkling2/cuda/ink_hybrid.cuh` にあり、CMake では `STRATA_ENABLE_CUDA` のとき CUDA backend を構成する（`engine/src/inkling2/CMakeLists.txt:193-198,220-235`）。HIP、SYCL、Metal の実装にこの名前の読み取りはない。
- `InkHybridEngine::start_workers()` が実行されること。同関数はすでに `active` なら即時 return する（`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1780`）。runner は `n_host_experts > 0` の場合に開始するため、ホスト RAM または SSD 側に置く expert がない構成では値は反映されない（例: `engine/src/inkling2/cuda/ink_runner.cuh:497-503,622-624`）。別の runner 経路にも同じ条件で呼び出しがある（`engine/src/inkling2/cuda/ink_runner.cuh:1374-1380,1588-1595`）。
- unset 時は runner から渡される `cpu_threads` が正ならそちらが既定を決めるが、環境変数が設定されると常にその値が優先する（`engine/src/inkling2/cuda/ink_hybrid.cuh:1782-1783`）。

## 実行時の詳細

`start_workers()` はプール開始時に環境変数を読み、以後 `n_threads` をプールのスケジューリングに使う。`active` が true の後の呼び出しは読み直さないため、同一 engine の起動後にプロセス環境を変更しても反映されない。ソースに子プロセスへの転送処理はない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1788,1826-1828,1978-1979`）。

`n_threads` はワーカースレッドを `n_threads - 1` 本作成し、別途 master thread を起動する。従ってプールは合計 `n_threads` 本のスレッドで構成される。CPU expert の doorbell job は worker と master が分担し、複数 job があるときに並列化する。verify group も `n_threads > 1` かつ group が複数ある場合に worker と分担する（`engine/src/inkling2/cuda/ink_hybrid.cuh:1826-1828,1896-1897,1880-1889,1944-1955,1731-1752`）。この変数が直接変えるのはプールサイズと分担方法であり、ソース上で生成 token や router の選択値を変更する処理は確認できない。

## ログと測定値

この変数の値や選択されたスレッド数を表示するログは `start_workers()` にない。runner のホスト expert 用 GPU staging allocation が失敗すると、別要因の初期化エラーとして `not enough free VRAM for the 2x prefill staging buffers required by host experts; close other GPU apps or use a smaller pack`（または quant 用文言）を `err` に設定するが、このエラーをスレッド数の不正値に結び付けるコードはない（`engine/src/inkling2/cuda/ink_runner.cuh:497-502,1374-1380`）。この調査では実行・測定をしていない。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1788` — 初期値、環境変数の読み取り、変換と clamp、関連する環境設定の読み込み。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1826-1828,1896-1897,1978-1979` — worker/master thread 作成とプール開始状態。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1731-1752,1880-1889,1944-1955` — verify と doorbell job の並列分担。
- `engine/src/inkling2/cuda/ink_runner.cuh:497-503,622-624,1374-1380,1588-1595` — ホスト expert がある経路でのプール開始。
- `engine/src/inkling2/CMakeLists.txt:193-198,220-235` — CUDA backend の構成条件。
