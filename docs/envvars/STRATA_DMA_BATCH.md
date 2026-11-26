# `STRATA_DMA_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

エキスパート重み blob をホストから GPU へ送るとき、複数コピーを一括で投入する経路を選びます。モード `0` は既存の blob ごとのコピー、非 `0` は batch の候補です。実際に一括投入できるかは backend、CUDA runtime build、コピー数にも依存し、条件を満たさない経路は個別コピーに戻ります。値が変えるのは転送の投入方法で、エキスパートの選択や重みの変換ではありません（`engine/include/strata/core/dma_batch.hpp:61-103`）。

読み取り helper は CUDA と SYCL の各 `dma_batch.hpp` にあります。主な利用箇所は verifier の PCIe DMA upload（`engine/src/core/verify.cpp:4390-4412`）と、adaptive tier の入れ替え・refill（`engine/src/program/generate.cpp:15425-15428`, `15447-15455`, `15489-15494`, `24760-24762`, `24776-24797`。SYCL 側は `engine/sycl/src/core/verify.cpp:3042-3091`, `engine/sycl/src/program/generate.cpp:8941-8943`, `8997-9017`, `13910-13912`, `13925-13943`）。

## 値と判定

helper は `std::getenv` で値を取り、未設定または空文字なら引数の既定値を使います。全呼び出し箇所は引数を省略しており、既定値は `0` です。空でない値は `std::atoi` に渡され、全体の構文検査、許容範囲チェック、clamp、無効値の警告はありません（`engine/include/strata/core/dma_batch.hpp:28-35`, `engine/sycl/include/strata/core/dma_batch.hpp:31-39`）。

| 条件 | unset / 空文字 | `atoi` 結果が 0 | `atoi` 結果が非 0 |
|---|---|---|---|
| CUDA batch API を使える build | モード 0、個別コピー | 個別コピー。例: `0`, `0anything`, `true`, `false` | 2 件以上かつ 128 件以下なら batch を試行。例: `1`, `2`, `-1`, `1tail`。ちょうど `2` のときだけ CUDA 13.4 以降で overlap hint も指定 |
| HIP / gfx906 または CUDA runtime 13.0 未満 | モード 0、個別コピー | 個別コピー | batch API の build 分岐に入らず個別コピー。verifier では非 0 が helper 経由になるため、コピー失敗の扱いはモード 0 の直接ループと異なる |
| SYCL | モード 0、個別コピー | 個別コピー | この checkout の SYCL helper は `DPCT_COMPAT_RT_VERSION` を `12080` と定義し、batch 分岐の条件 `>= 13000` を満たさないため個別コピー |

`atoi` は数値の先頭部分を変換するため、`1tail` は 1、`0anything` は 0 になります。先頭の空白や符号も数値変換に従います。`true` / `false` は数値として読めず 0 です。大文字小文字の判定はありません。`2` 以外の非 0 値も batch を試みますが、mode 2 専用の hint は付きません（CUDA helper: `engine/include/strata/core/dma_batch.hpp:68-85`; SYCL の互換値と条件: `engine/sycl/include/strata/core/dma_batch.hpp:1`, `85-98`）。

## 有効になる条件

- verifier の PCIe share を batch 化するには `--pcie-mode dma` が必要です。引数は `dma` のとき verifier に mode 0 として渡され、`auto` / `kernel` や `direct` では DMA callback にコピー件数 0 が渡ります。さらに、その layer で PCIe share が選ばれ、PCIe 対応 layer と pinned host blob がある場合にコピー群ができます（`engine/src/program/generate.cpp:1041-1044`, `13682-13707`, `24543-24551`; `engine/src/core/expert_source.cpp:5543-5557`, `5564-5568`, `5597-5605`, `5681-5696`; SYCL: `engine/sycl/src/program/generate.cpp:7966-7987`, `engine/sycl/src/core/expert_source.cpp:2688-2696`）。この CLI 引数は環境変数を設定・上書きせず、`STRATA_DMA_BATCH` だけでは PCIe DMA 経路を有効にしません。
- verifier では一回の group が 1 件、または 128 件を超える場合は個別コピーです。CUDA batch build で host alias の解決に失敗した場合も個別コピーへ戻ります（`engine/include/strata/core/dma_batch.hpp:68-75`, `99-103`, `107-122`）。
- CUDA の一括投入は `STRATA_USE_HIP` と `STRATA_HIP_GFX906` が未定義で、`CUDART_VERSION >= 13000` のときだけコンパイルされます。mode 2 の overlap hint はさらに `CUDART_VERSION >= 13040` のときだけ付き、それ未満では mode 1 と同じ batch API 呼び出しです（`engine/include/strata/core/dma_batch.hpp:68-85`）。
- adaptive refill は別経路で、swap があり、コピー元 blob と destination slot が有効な場合に使います。`strata serve` の multi-GPU 経路は main device の `dma_mode` を 0 に固定します。単一 GPU では非 0 のとき候補コピーを集め、同じ helper に渡します（`engine/src/program/generate.cpp:15425-15428`, `15440-15461`, `15489-15494`; 非 serve の generate: `24746-24797`）。SYCL にも対応する refill 経路がありますが、その helper は上記の互換値 gate により個別コピーです（`engine/sycl/src/program/generate.cpp:8941-8970`, `8997-9017`, `13910-13943`）。
- CUDA `strata serve` では `STRATA_DMA_BATCH` の判定結果が非 0 だと `STRATA_ADAPT_OVERLAP` は併用できません。`STRATA_ADAPT_OVERLAP` が設定されている場合、理由 `not with STRATA_DMA_BATCH` を含む off ログを出します（`engine/src/program/generate.cpp:15122-15136`, `15175-15186`）。この判定は CUDA serve の adaptive-overlap gate に限られます。

## 実行時の詳細

`dma_batch_mode()` の関数内 `static const` が最初の呼び出しで値を取得し、プロセス内で cache します。以後の環境変更は反映されません。最初に呼ばれる場所は実行経路によって異なり、serve の adaptive-overlap 判定、manifest 記録、verifier の最初の非空 DMA group、または adaptive refill などです（helper: `engine/include/strata/core/dma_batch.hpp:30-35`; 呼び出し例: `engine/src/program/generate.cpp:15122-15129`, `16253-16258`, `15425-15428`, `24760-24762`; verifier: `engine/src/core/verify.cpp:4393-4404`）。CLI 引数や設定ファイルからこの値を読み替える処理は確認できません。

CUDA batch 対応 build では、2〜128 件のコピーについて host pointer の device alias を取得し、元と同じ destination / source / byte 数を既存 stream に batch API で投入します。CUDA 13.4 以降で mode がちょうど 2 なら overlap hint を属性に加えます。batch API が失敗すると個別コピーへ再投入し、コピーは捨てません。alias 解決が失敗した場合も個別コピーになります。1 件または 128 件超は最初から個別コピーです（`engine/include/strata/core/dma_batch.hpp:65-103`, `106-123`）。

verifier の mode 0 は従来どおり `cudaMemcpyAsync` を blob ごとに直接呼び、その戻り値を検査しません。非 0 は `copy_expert_blobs` を通り、fallback の個別コピーも戻り値を検査します。非 0 経路で upload が失敗すると `strata DMA: expert upload failed: %s` を stderr に出し、GPU wait を 5000 ms 解放して `abort()` します。これは、未コピーの重みを読み手に使わせないための経路です（`engine/src/core/verify.cpp:4400-4412`; helper: `engine/include/strata/core/dma_batch.hpp:99-123`）。

## ログと測定値

batch API の呼び出しが失敗したときは、プロセス中一度だけ stderr に `strata: cudaMemcpyBatchAsync failed (%s); the uploads go one copy at a time` と出して個別コピーへ戻ります。host alias 解決失敗や batch 対象外の件数では、この警告は出ません（`engine/include/strata/core/dma_batch.hpp:70-95`）。verifier の非 0 upload が fallback 後も失敗した場合のログ・終了経路は上記のとおりです。

manifest が有効な実行では、`transfer` / `dma-batch` の経路項目に有効状態、理由、`mode N` を記録します（`engine/src/program/generate.cpp:16253-16258`）。値の parse に関する警告はありません。

Strata の `docs/BATCHED_DMA.md:47-69` は、Windows / CUDA 13.4 の RTX 4070 Laptop（8 GB）、Ryzen 9 7940HS、64 GB DDR5-5600 で、登録済み host memory から 2 MiB の独立コピー 16 件を warm-up 後に 5 回測定した helper 比較を報告しています。初回表の median host submission は個別 0.0936 ms、batch 0.0162 ms、hint 付き 0.0155 ms、median total transfer はそれぞれ 2.5589 ms、2.5248 ms、2.5206 ms です。同資料は全モデル生成の速度向上を立証していないとし、別条件の model run も生成長が異なるため転送変更単独の効果を分離できないと記載しています。これらは資料記載の測定値であり、この調査で再測定した値ではありません。

## 根拠

- 値の取得、parse、cache: `engine/include/strata/core/dma_batch.hpp:28-35`; SYCL: `engine/sycl/include/strata/core/dma_batch.hpp:31-39`。
- CUDA batch gate、batch API、fallback と警告: `engine/include/strata/core/dma_batch.hpp:65-103`; 個別コピー helper: `106-123`。
- SYCL batch gate: `engine/sycl/include/strata/core/dma_batch.hpp:1`, `81-117`, `143-175`。
- verifier callback と失敗処理: `engine/src/core/verify.cpp:4390-4412`; PCIe group の構成・callback: `engine/src/core/expert_source.cpp:5543-5557`, `5681-5696`。
- adaptive refill: `engine/src/program/generate.cpp:15425-15428`, `15447-15461`, `15489-15494`, `24760-24797`; SYCL: `engine/sycl/src/program/generate.cpp:8941-9017`, `13910-13943`。
- 測定条件と値: `docs/BATCHED_DMA.md:47-69`。
