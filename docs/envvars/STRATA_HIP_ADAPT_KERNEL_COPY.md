# `STRATA_HIP_ADAPT_KERNEL_COPY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP ビルドで adaptive tier が expert を VRAM cache に refill するとき、条件を満たす host-to-device 転送を `cudaMemcpyAsync` ではなく Strata の `copy_from_mapped` GPU kernel に置き換える opt-in です。コピー先の slot と内容は同じで、変わるのはこの refill の転送方法です。対象名を読む実装は通常 engine と SYCL engine の `adapt_copy_h2d` にあります。`STRATA_USE_HIP` が定義されたビルドでだけ値を読みます（`engine/src/program/generate.cpp:608-625`、`engine/sycl/src/program/generate.cpp:230-255`）。

## 値と判定

`adapt_copy_h2d` 内の関数ローカル `static const bool` 初期化で `std::getenv` を一度呼び、値が存在し、先頭 1 byte が文字 `'1'` のときだけ on です。文字列全体の比較や数値変換はしません。

| ビルド・呼出し条件 | unset | on になる値 | off になる値 |
|---|---|---|---|
| `STRATA_USE_HIP` 定義あり、`adapt_copy_h2d` が呼ばれた場合 | off | `1`, `10`, `1abc`, `1 ` | 空文字、`0`, `01`, `true`, ` 1`, `2` |
| `STRATA_USE_HIP` 定義なし | 読み取りなし | 該当なし | この変数による kernel 選択なし |

大文字小文字の変換、前後空白の除去、無効文字列のエラー処理はありません。unset・空文字・先頭文字が `'1'` でない値は通常コピーに進みます。`STRATA_HIP_GFX906` だけが定義された互換ビルドも、この変数の読み取り条件には含まれません（`engine/src/program/generate.cpp:608-625`、`engine/sycl/src/program/generate.cpp:230-255`）。

## 有効になる条件

- HIP 用に `STRATA_USE_HIP` を定義してビルドされていること。OS や GPU 世代による明示的な追加判定はこの関数にありません。
- adaptive refill の呼出し経路に入り、かつ `STRATA_DMA_BATCH` の判定結果が 0 であること。通常 engine の serve 経路では layer split 時は `dma_mode=0`、それ以外は `strata::core::dma_batch_mode()` の値です。非 serve の経路も同 helper の値を使います（`engine/src/program/generate.cpp:15426-15461,24760-24781`）。helper は `STRATA_DMA_BATCH` が空でなければ `atoi` した値を返し、既定値は 0 です（`engine/include/strata/core/dma_batch.hpp:28-35`）。
- `STRATA_DMA_BATCH` が非ゼロだと専用関数を通りません。HIP では `copy_blobs` 側も batch API を使わず個別の `cudaMemcpyAsync` に戻るため、この変数が on でも kernel copy は選ばれません（`engine/include/strata/core/dma_batch.hpp:65-103`）。SYCL 側も同様に `STRATA_USE_HIP` では batch 分岐を通らず個別コピーです（`engine/sycl/include/strata/core/dma_batch.hpp:81-135`）。
- `adapt_copy_h2d` に到達しても、`bytes` が 16 の倍数で、コピー元・コピー先の両方が 16-byte aligned であり、`cudaHostGetDevicePointer` が成功して非 null の device-visible source pointer を返すことが必要です。どれかを満たさなければ通常の host-to-device `cudaMemcpyAsync`（SYCL engine では `st->memcpy`）を使います（`engine/src/program/generate.cpp:616-625`、`engine/sycl/src/program/generate.cpp:239-255`）。
- 呼出し元は serve の adaptive swap と、speculative generate の adaptive refill です。serve の swap は `adapt_every` と `adapt_swaps` が正で、adaptive tier が有効な場合に組み立てられます（`engine/src/program/generate.cpp:11796-11811,15392-15461`）。speculative generate の refill も adaptive round の swap ごとに呼び出されます（`engine/src/program/generate.cpp:24701-24703,24760-24798`）。この環境変数自体は CLI option ではなく、CLI 引数による値の上書き処理もありません。

## 実行時の詳細

値はプロセス起動時ではなく、いずれかの呼出し経路が初めて `adapt_copy_h2d` に到達したときに評価され、関数内 `static` に保持されます。同じバイナリ内でこの値を変えても、そのプロセスでは再評価されません。読み取り・設定のための子プロセス起動や転送処理はありません（`engine/src/program/generate.cpp:608-615`、`engine/sycl/src/program/generate.cpp:230-238`）。

on で alignment と byte 数の条件を満たす場合、Strata は `cudaHostGetDevicePointer` でコピー元の device-visible pointer を取得し、`strata::kernels::copy_from_mapped` を refill stream 上で呼びます。通常 engine の CUDA/HIP 実装では `copy_from_mapped` が launch error を確認し、失敗時は `copy_from_mapped launch: %s` を出して終了します（`engine/src/program/generate.cpp:616-625`、`engine/src/kernels/cuda/elementwise.cu:299-308,122-129`）。SYCL engine の `check_launch` は移植 placeholder で常に成功を返す実装です。`adapt_copy_h2d` は SYCL exception を捕捉した場合、exception 文と場所を stderr に出して終了します（`engine/sycl/src/program/generate.cpp:230-259`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:196-205,554-579`）。どちらも device pointer の取得が失敗または null の場合はエラー状態を消費して通常コピーへ fallback します（`engine/src/program/generate.cpp:616-625`、`engine/sycl/src/program/generate.cpp:239-255`）。

kernel 経路に入らない場合、または変数が off の場合は同じ refill stream 上の通常の `cudaMemcpyAsync` / SYCL `memcpy` が使われます。serve 側はコピー完了 event を記録し、次の窓で pending swap を適用します（`engine/src/program/generate.cpp:15458-15470,15489-15495`）。

## ログと測定値

変数が on で `adapt_copy_h2d` が初めて実行されると、stderr に次の行を出します。値が off の場合はこの行を出しません。

```text
strata: STRATA_HIP_ADAPT_KERNEL_COPY=1: adaptive swaps copy with a kernel, not SDMA (#884)
```

このログは値の parse が on であることを示すもので、各コピーが kernel 経路を通ったことまでは示しません。alignment / byte 数の不一致、`cudaHostGetDevicePointer` の失敗、または `STRATA_DMA_BATCH` の非ゼロ指定では通常コピーに fallback または迂回します（`engine/src/program/generate.cpp:610-625,15447-15463,24776-24798`）。

専用コピーがエラーを返した場合、serve 経路は `strata serve: adaptive swap copy failed (layer %d, slot %d, pinned %d): %s` を stderr に出してその処理を失敗させます。speculative generate 経路は `strata generate: an adaptive refill failed` を出して失敗を返します。CUDA kernel の launch error は `copy_from_mapped launch: %s` を stderr に出してプロセスを終了します（`engine/src/program/generate.cpp:15458-15464,24772-24783`、`engine/src/kernels/cuda/elementwise.cu:122-129`）。

## 根拠

- `engine/src/program/generate.cpp:603-625` — HIP guard、値の判定、ログ、kernel 条件と通常コピーへの fallback。
- `engine/sycl/src/program/generate.cpp:225-255` — SYCL engine 側の同等実装。
- `engine/src/program/generate.cpp:15426-15470,15489-15495,24760-24798` — serve / speculative generate の呼出し、`STRATA_DMA_BATCH` 分岐、pending refill。
- `engine/sycl/src/program/generate.cpp:8941-9000,13910-13945` — SYCL engine の呼出しと同じ batch 判定。
- `engine/include/strata/core/dma_batch.hpp:28-35,65-103`、`engine/sycl/include/strata/core/dma_batch.hpp:31-39,81-135` — `STRATA_DMA_BATCH` の値取得と HIP での個別コピー fallback。
- `engine/src/kernels/cuda/elementwise.cu:229-234,299-308,122-129`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:429-440,554-579` — mapped source を読む kernel と launch error 処理。
