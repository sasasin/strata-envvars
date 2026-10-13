# `STRATA_DMA_BATCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

独立した host-to-device の expert blob copy を、1 回ずつ送る（`cudaMemcpyAsync`）か、1 回の `cudaMemcpyBatchAsync` でまとめて送るかを決めます。midhatn の PR #807（CUDA 13+ の pinned expert upload）と eddoursul の fork（F12、適応層と prefetch の copies）が使う経路です。WDDM では単独の copy が land 時に割り込みを上げますが、batch は 1 回で済みます。

判定結果は `dma_batch_mode()` 内の `static const int` に保存され、最初に呼ばれたとき一度だけ read されます。

## 値と判定

`getenv()` が non-null かつ先頭文字が `\0` でないとき `std::atoi` で整数に変換し、そうでなければ `default_mode`（呼び出し箇所の既定、常に 0）を使います。

| 入力 | `atoi` | mode | 動作 |
|---|---|---|---|
| 未設定 | — | 0（既定） | blob ごとに `cudaMemcpyAsync`（engine が常に走っていた loop） |
| 空文字 | — | 0 | loop |
| `0` | 0 | 0 | loop |
| `1` | 1 | 1 | `cudaMemcpyBatchAsync`（CUDA 13+、group 2..128） |
| `2` | 2 | 2 | 1 に加え CUDA 13.4 の `cudaMemcpyFlagPreferOverlapWithCompute`（hint） |
| `3` 以上の整数 | 3.. | 非 0 | batch を試みる。flag は `== 2` のときだけなので mode 1 と同じ |
| 負数（例 `-1`） | -1 | 非 0 | batch を試みる（mode 1 と同じ） |
| 非数字（例 `abc`, `true`） | 0 | 0 | loop |

mode は clamp されません。0 以外の任意の整数が batch 経路に入り、overlap hint は値が正確に `2` のときだけ設定されます。CUDA 13.0–13.3 では mode 2 も hint が設定されず mode 1 と同じ挙動です（`include/strata/core/dma_batch.hpp:78-80` の `#if CUDART_VERSION >= 13040`）。

## 有効になる条件

- `--pcie-mode dma` の DMA copy 経路（`Verifier::fetch_dma`）でのみ効きます。`--pcie-mode` の既定 `auto` は呼び出し箇所で copy kernel（mode 2）にマップされ、kernel-copy 経路は変わりません（`src/program/generate.cpp:7587,7607`、`src/core/verify.cpp:643`）。
- CUDA 13+（`CUDART_VERSION >= 13000`）または SYCL の compat runtime 13+（`DPCT_COMPAT_RT_VERSION >= 13000`）。HIP、CUDA 13 未満、`STRATA_HIP_GFX906` は常に loop（`include/strata/core/dma_batch.hpp:68`、`sycl/include/strata/core/dma_batch.hpp:85-86`）。
- group の blob 数 `n` が 2..128。`n == 1` や `n > 128` は loop（`dma_batch.hpp:70,111`）。
- serve の適応層 copies では multi-GPU（layer split）のとき mode が 0 に強制されます（`src/program/generate.cpp:8408`）。
- runtime が batch を拒否した場合、1 回だけ警告して loop でやり直し、drop しません（`dma_batch.hpp:87-92`）。

## 実行時の詳細

- verifier の DMA upload: `src/core/verify.cpp:2414-2424`。mode 0 は errors をチェックしない loop（engine を止めない）。batch mode で upload が submit できなければ flag B が stale weight を consumer に渡さないため engine を停止します（`std::abort`）。
- serve の適応層 copies: `src/program/generate.cpp:8461-8465`（batch 失敗時 `strata serve: adaptive swap copy failed (batched): ...`）。
- generate の適応層 copies: `src/program/generate.cpp:12923,12937-12941`（mode 0 は `adapt_copy_h2d` の loop、非 0 は batch 用の vector に積む）。
- Windows の registered host pointer は device-visible alias と異なることがあるため `host_alias` で解決します（`dma_batch.hpp:40-57`）。blob は固定なので各 pointer は一度だけ lookup されます。

警告文字列: `strata: cudaMemcpyBatchAsync failed (%s); the uploads go one copy at a time`（`dma_batch.hpp:90-91`）。abort 時: `strata DMA: expert upload failed: %s`（`src/core/verify.cpp:2420`）。

## 測定値

`docs/BATCHED_DMA.md` は experimental として、host submission overhead 削減の実験であり model tokens/s の増加は実証されていないと明記します。記載された測定（RTX 4070 Laptop 8 GB、Ryzen 9 7940HS、64 GB DDR5-5600、Windows、CUDA 13.4、16 upload × 2 MiB、warmup 後 5 回、mode 順交替）で batch submission latency が 82.7% 減、total transfer latency が 1.3% 減。full-model screen（Swift 1.5 IQ3_XXS、64K context）では coding request が individual DMA 30.3 tok/s、batch 30.0 tok/s で、生成長が異なるため transfer 変化を分離できず、既定を変える根拠にならないとされています。A-B-B-A 比較（v0.1.39、`--pcie-mode dma`）の 4 run は control 間でも出力が異なり model speedup を分離しません。Linux と HIP runtime の validation は未テストです。

## 根拠

- parse と既定: `include/strata/core/dma_batch.hpp:30-36`、mode 注釈 `9-15`。SYCL `sycl/include/strata/core/dma_batch.hpp:33-39`。
- build / group / flag / fallback: `include/strata/core/dma_batch.hpp:68,70,78-80,87-92,111`。
- DMA 経路の限定: `src/core/verify.cpp:643,2404-2424`、`src/program/generate.cpp:7587,7607`。
- serve/generate の copies 呼び出し: `src/program/generate.cpp:8408,8461-8465,12923,12937-12941`。
- docs 照合: `docs/BATCHED_DMA.md`、`docs/DETAILS.md:1704`。
