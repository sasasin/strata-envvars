# `STRATA_HIP_ADAPT_KERNEL_COPY`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（`2026-10-14` 時点）。

## 役割

適応型エキスパートキャッシュの swap/refill で行うホストから GPU へのコピーを、条件が合う場合に通常の非同期 memcpy ではなく GPU カーネルで実行する HIP 向けの切り替えである。ソースコメントでは SDMA（コピーエンジン）を避けるための回避策として説明されている。`strata generate` と `strata serve` の適応型 swap が対象であり、通常のプロンプト読み込みやすべてのホスト・デバイス間コピーを切り替える設定ではない。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 値の先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| それ以外（例: `0`, `true`, ` 1`） | 無効 |

文字列全体の比較や数値変換は行わず、初回評価時に `getenv` が非 null かつ先頭文字が `'1'` かだけを判定する。判定結果は関数内の `static const bool` に保存されるため、同一プロセスでその後に環境変数を変更しても再評価されない。有効と判定された初回呼び出しでは、stderr に `strata: STRATA_HIP_ADAPT_KERNEL_COPY=1: adaptive swaps copy with a kernel, not SDMA (#884)` を出力する。

## 有効になる条件

- 実装は `#if defined(STRATA_USE_HIP)` の範囲内にある。通常の CUDA ビルドではこの環境変数を読まず、通常の `cudaMemcpyAsync` 経路を使う。
- 適応型 swap の各コピーが `adapt_copy_h2d` に到達する必要がある。呼び出し元で `STRATA_DMA_BATCH` のモードが 0 以外の場合、コピーはまとめて `copy_blobs` に送られ、この環境変数によるカーネル経路を通らない。`copy_blobs` の HIP 側実装は通常の `cudaMemcpyAsync` のループである。`--serve` の複数 GPU 経路は `dma_mode` を 0 にする。
- カーネル経路には、コピーサイズが16バイト単位で、送信元と宛先の両ポインターが16バイト境界に揃っていることが必要である。
- さらに `cudaHostGetDevicePointer` で送信元のデバイス可視ポインターを得られる必要がある。取得失敗または null の場合はエラーをクリアし、通常の非同期 memcpy にフォールバックする。したがって設定値が有効でも、これらの条件を満たさないコピーにはカーネル方式は適用されない。

## 実行時の詳細

`adapt_copy_h2d` は条件を満たす場合、送信元のマップ済みホスト領域をデバイス可視ポインターに変換し、`strata::kernels::copy_from_mapped` を同じ refill stream に投入する。CUDA 実装は `float4` 単位でデータを読み書きするカーネルであり、SYCL 実装も同じく16バイト整列と4要素単位を検査してコピー用カーネルを投入する。カーネル呼び出し後はその起動エラーを返す。条件不成立なら、CUDA/HIP 経路は `cudaMemcpyAsync(..., cudaMemcpyHostToDevice, st)`、SYCL 経路は queue の非同期 `memcpy` に戻る。

この helper は、通常の適応型 swap/refill の個別コピーで利用される。CUDA/HIP 共通ソースでは `strata generate` と `strata serve` の両方に呼び出しがあり、SYCL 移植ソースにもそれぞれの呼び出しがある。まとめてコピーする分岐では helper を呼ばない。呼び出し後の swap 完了待ちは既存の適応処理が行う。

## 根拠

- `src/program/generate.cpp:185-208` — 環境変数の読み取り、先頭文字判定、stderr の文言、整列・マップ確認、カーネルまたは通常コピーへの分岐。
- `sycl/src/program/generate.cpp:195-225` — SYCL 側の同じ判定と処理。
- `src/program/generate.cpp:8921-8937, 8957-8961, 13667-13697` — `strata serve` / `strata generate` の個別 swap コピーと、`dma_mode != 0` 時に helper を迂回する分岐。
- `sycl/src/program/generate.cpp:8032-8091, 12420-12453` — SYCL 側の同じ呼び出し条件。
- `include/strata/core/dma_batch.hpp:9-15, 65-111` — `STRATA_DMA_BATCH` のモードと、HIP ビルドでは `copy_blobs` が通常コピーのループになること。
- `src/kernels/cuda/elementwise.cu:229-234, 299-309`、`sycl/src/kernels/cuda/elementwise.dp.cpp:544-560` — マップ済み領域を読むカーネル実装。
- `docs/AMD_HIP.md:206-211` — #884 の回避策として紹介されている。文書は gfx1030 の hang 事例を述べるが、現行ソースが確認できるのは切り替え処理までであり、特定 GPU での再現性や性能効果をこの調査で検証したものではない。
