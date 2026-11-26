# `STRATA_MTP_BATCH_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプト処理中に drafter（MTP）の K/V をまとめて計算する `Prefill::draft_kv` が、drafter の Q8_0 射影を FP16 入力の GEMM で処理するか、条件がそろえば Q8_1 × Q8_0 MMQ で処理するかを選びます。これはバッチ経路内の射影方式の選択です。変数だけで MTP やバッチ経路を有効化するものではありません。CUDA/HIP 共通の `engine/src/prefill/prefill.cpp` と SYCL の `engine/sycl/src/prefill/prefill.cpp` で判定規則が異なります（それぞれ `:3045-3046`、`:1902-1903`）。

## 値と判定

どちらも文字列を数値や真偽値として parse せず、`getenv` の返す文字列の先頭 1 文字だけを比較します。大文字小文字・空白・残りの文字列は検査しません。空文字は設定済みの文字列ですが、先頭文字が `\0` なので、CUDA/HIP 側では FP16 GEMM、SYCL 側では MMQ を選び得る側になります。

| backend | 未設定 | FP16 GEMM になる設定値 | MMQ を選び得る設定値 |
|---|---|---|---|
| CUDA/HIP (`engine/src`) | FP16 GEMM | 先頭文字が `0` 以外。例: `1`, `true`, ` 0`, 空文字 | 先頭文字が `0`。例: `0`, `0anything` |
| SYCL (`engine/sycl/src`) | MMQ を選び得る | 先頭文字が `1`。例: `1`, `10`, `1anything` | 設定値の先頭文字が `1` 以外。例: `0`, `true`, 空文字, ` 1` |

「MMQ を選び得る」場合も、ビルドに MMQ があり、Q8_0 の射影幅 `Nn` と `KV` の双方が `mmq::fits` を満たす必要があります。条件を満たさなければ `q8` は false となり、同じバッチ経路の FP16 入力 GEMM に進みます（CUDA/HIP: `engine/src/prefill/prefill.cpp:3045-3046,3092-3100`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1902-1903,1950-1958`）。

## 有効になる条件

- MTP drafter が使われ、プロンプト chunk の K/V を処理する必要があります。一 GPU の generate/serve 経路は `use_mtp` のときバッチ経路を試します（CUDA/HIP: `engine/src/program/generate.cpp:14777-14784,24137-24148`; SYCL: `engine/sycl/src/program/generate.cpp:8622-8627,13360-13370`）。
- `STRATA_MTP_BATCH` が先頭文字 `0` でバッチ経路を無効化すると、この変数の読み取り行に到達せず、通常の `mtp.prefill` に戻ります。`STRATA_MTP_BATCH_F16` は `STRATA_MTP_BATCH` や MTP を選ぶ CLI 設定を上書きせず、バッチ経路内の MMQ/FP16 選択だけを行います（CUDA/HIP: `engine/src/prefill/prefill.cpp:3001,3007-3009,3045`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1861,1867-1869,1902`）。
- レイヤー分割（multi-GPU）では CUDA/HIP 側は既定で drafter 自身の prefill を使い、`STRATA_SPLIT_MTP_BATCH` が有効で、最後の stage に GGUF 形式の token embedding がある場合に限ってバッチ経路を試します。SYCL serve の呼び出し箇所は `!multi_gpu` を条件にしています（`engine/include/strata/program/draft_kv_plan.hpp:25-42`; `engine/src/program/generate.cpp:14763-14784`; `engine/sycl/src/program/generate.cpp:8625-8627`）。
- `draft_kv` 内でも、chunk に対象セルがあり、prompt scratch region があり、drafter と prefill が同じ device を使い、対応する K/V 状態・tensor・embedding 条件を満たす必要があります。K/V が hybrid、未対応の mode、参照可能な token embedding でない場合などはバッチ処理を辞退します（CUDA/HIP: `engine/src/prefill/prefill.cpp:3007-3037`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1867-1897`）。
- この変数を読んだ後も、他の MTP 設定や状態によって `draft_kv` が呼ばれない、またはそこで辞退することがあります。その場合は通常の `mtp.prefill` が drafter の K/V を計算します。したがって、この設定は fallback 経路の射影方式を変更しません（CUDA/HIP: `engine/src/program/generate.cpp:14797-14798,24147-24148`; SYCL: `engine/sycl/src/program/generate.cpp:8626-8627,13369-13370`）。

## 実行時の詳細

値は `draft_kv` 内の関数ローカル `static const bool` を初期化するときに読み取られます。初期化行より前に辞退する経路、または必要な対象セルがない経路ではこの変数を読みません（CUDA/HIP: `engine/src/prefill/prefill.cpp:2991-3014,3035-3046`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1857-1873,1895-1903`）。一度初期化されると、そのプロセス内の当該 backend 実装では値が cache され、後から環境を変えても再評価されません。

CUDA/HIP では `f16_only` が true なら Q8_0 重みを使う各 `proj` が `m.gemm.native` を呼びます。false なら MMQ の build/shape 条件を確認し、通れば入力を Q8 に量子化して `mmq::Context::run`、通らなければ `m.gemm.native` を呼びます（`engine/src/prefill/prefill.cpp:3045-3046,3092-3100,3128-3137,3145-3148`）。SYCL も同じ分岐構造で、`engine/sycl/src/prefill/prefill.cpp:1902-1903,1950-1958,1998-2014,2021-2024` にあります。FP16 側でも Q8_0 重み自体を FP16 重みに変換する設定ではなく、native GEMM に FP16 入力と Q8_0 型の重みを渡します。

このバッチ処理は drafter の prompt K/V を作る計算方式を変えます。K/V を計算して drafter の cache に append し、完了後に `mtp.ms_prefill` を加算します（CUDA/HIP: `engine/src/prefill/prefill.cpp:3145-3169`; SYCL: `engine/sycl/src/prefill/prefill.cpp:2021-2057`）。

## ログと測定値

この変数専用のログや無効値警告はありません。バッチ経路が辞退しても通常の経路へ移る場合は、単一 GPU の generate/serve ではこの理由を出力しません。CUDA/HIP の layer split では、バッチ成功時に `strata serve: draft layer prompt K/V batched on CUDA%d (E-9 on the layer split, K/V mode %d)`、辞退時に `strata serve: STRATA_SPLIT_MTP_BATCH=1 declined, the drafter's own pass runs: %s` を stderr に出す経路があります（`engine/src/program/generate.cpp:14785-14795`）。これらは layer split の経路に関するログで、値の parse 結果を直接表示するものではありません。

バッチ処理自体の失敗では、GPU 同期やアップロードなどのエラーが `err` に入り、呼び出し元で prompt 処理失敗になります（CUDA/HIP: `engine/src/prefill/prefill.cpp:3107-3113,3161-3163`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1970-1983,2037-2050`）。この場合は通常の fallback prefill には進みません。

## 根拠

- `engine/src/prefill/prefill.cpp:3040-3046` — CUDA/HIP 側の既定値、先頭文字判定、MMQ 条件。
- `engine/sycl/src/prefill/prefill.cpp:1900-1903` — SYCL 側の既定値、先頭文字判定、MMQ 条件。
- `engine/src/prefill/prefill.cpp:3092-3100,3128-3148`、`engine/sycl/src/prefill/prefill.cpp:1950-1958,1998-2024` — 射影分岐と K/V 作成。
- `engine/include/strata/program/draft_kv_plan.hpp:25-42`、`engine/src/program/generate.cpp:14777-14798,24142-24148`、`engine/sycl/src/program/generate.cpp:8622-8627,13365-13370` — 経路選択と fallback。
