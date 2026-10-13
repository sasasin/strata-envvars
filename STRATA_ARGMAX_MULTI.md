# `STRATA_ARGMAX_MULTI`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

greedy（無作為）argmax の kernel 選択を切り替える。CUDA の `sample_tokens()` で `p.greedy` または `p.temperature <= 0.0f` の分岐に入ったとき、条件がそろうと token ごとに 8 CTA の thread-block cluster（sm_90+）で `sampler_greedy_cluster_kernel` を launch する。この変数で無効化すると、置き換えられる従来の one-block kernel（token ごとに 1 block、1,024 threads）を常に使う。

両方の kernel は同じ token を返す設計である（cluster の答えは row だけの関数で、one-block kernel と bit for bit 同一。`src/kernels/cuda/sampler.cu:195-198`、parity 検査 `src/kernels/decode_cluster_parity.cpp:7`）。制御するのは選択の結果ではなく、同じ結果を生む 2 つの実装のどちらを launch するかである。

読み取り箇所は CUDA 実装 `src/kernels/cuda/sampler.cu:1255-1258` と SYCL 移植 `sycl/src/kernels/cuda/sampler.dp.cpp:1492-1495` の 2 箇所。判定結果は `static const bool multi` に保存され、greedy 分岐の最初の通過時に一度だけ評価される（`src/kernels/decode_cluster_parity.cpp:18` の注釈「they read the variables once」も同じ）。実行中に環境を書き換えても再評価されない。

## 値と判定

`std::atoi(v) != 0` で判定する。文字列全体を数値として parse し、先頭文字比較ではない。

| 状態 | 判定 |
|---|---|
| 未設定 | 有効（既定 ON） |
| `1`, `10`, `-1`, `2`, `1abc` など atoi が 0 以外を返す値 | 有効 |
| `0`, `0abc`, `-0` | 無効 |
| 空文字、`abc`, `true`, `false`, `0x1` など atoi が 0 を返す文字列 | 無効 |

大文字小文字・空白・数値の妥当性は検査されない。`atoi` の失敗は 0 と区別されないため、無効な文字列は `0` と同じく無効になる。

## 有効になる条件

値が有効でも、cluster launch は次の条件をすべて満たす経路でしか実行されない（`src/kernels/cuda/sampler.cu:1261`）。

- greedy 分岐：`p.greedy` または `p.temperature <= 0.0f`。
- ペナルティなし：`shmem == 0`（`penalty_last_n == 0`、または history が nullptr / len 0）。
- `p.logit_bias == nullptr`（この条件は CUDA 実装のみ。SYCL 実装の dispatch にはない）。
- `n_tokens` が 1..65535（`src/kernels/cuda/sampler.cu:1195-1196`）。
- 対象デバイスが sm_90+ であり、かつコードがその arch 向けにビルドされていること。判定は device ごとの `static int ok[64]` cache で、初回呼び出し時に compute capability（実カードまたは `STRATA_EMULATE_CC` 経由の `cc_major_of`）、`fa.ptxVersion >= 90 && fa.binaryVersion >= 90`、cluster 1 組分の occupancy（`kAmCtas = 8`）を確認する（`src/kernels/cuda/sampler.cu:1200,1215-1227`）。older build の PTX は trap を持つため、この判定で false になる。
- HIP ビルドでは `sample_greedy_cluster()` が常に false を返し、cluster は launch されない（`src/kernels/cuda/sampler.cu:1191-1194`）。
- SYCL ビルド（`sycl/CMakeLists.txt:88-107,205-213` が `sampler.dp.cpp` を使う）でも `#if 1` 分岐で常に false（移植版には thread-block cluster がない）。SYCL では変数を読むが dispatch 結果に影響しない：one-block kernel への submit になる（`sycl/src/kernels/cuda/sampler.dp.cpp:1401-1405,1498`）。

条件が満たされない、または launch 前判定で device が非対応とされた場合は one-block kernel に fallback する。この fallback は無警告である。

## 実行時の詳細

呼び出し元は engine の decode 経路である。verify window の sampling（`src/core/verify.cpp:1792,2336,3000,3408`）と MTP draft（`src/core/mtp.cpp:999`）から `sample_tokens()` が呼ばれる。cluster kernel は CUDA graph capture 内で launch できる（`include/strata/kernels/sampler.hpp:49`「capturable」）。

cluster が動くと、1 token の row（例: 248,320 logits）を 8 CTA が分担し、各 CTA の結果は CTA 0 の distributed shared memory で合流する（`src/kernels/cuda/sampler.cu:189-202`）。one-block kernel は 1 SM の 1 block が row 全体を読む。

判定は `sample_tokens()` の greedy 分岐の初回通過時に static cache される。greedy ではない呼び出しだけが続く場合、環境変数はその時点では読まれない。

launch 失敗時のログは `sample_tokens cluster launch: <error>`（stderr）で、これは cluster 判定が通過した後実際に launch された場合だけ出る（`src/kernels/cuda/sampler.cu:1231-1234`）。変数自身の設定・無効に関するログはない。

## 測定値

`docs/DETAILS.md:24-28` の記載（Engine 0.1.36、同一 PC、RTX 50、sm_90+、Q2_0）: decode output が 4K で 89 → 93.5、128K で 64.5 → 76.4 tokens/s。`STRATA_ARGMAX_MULTI=0` で decode kernel（cluster 経路）を切ると説明されている。実装注釈には RTX 5070 の per-call 値 40 us（one-block）→ 6 us（cluster、`decode_cluster_parity --bench`）が書かれている（`src/kernels/cuda/sampler.cu:190-193`）。これらは資料に記載された測定環境での値であり、他機種の性能を保証しない。

## 関連変数

- `STRATA_QSA_CLUSTER`：同じ S19 の cluster 最適化の QSA top-k 側を切り替える別変数（本ファイルの対象外）。
- `STRATA_EMULATE_CC`：cluster 判定の compute capability 参照に影響する（tests only の設計、`include/strata/core/emulate.hpp:1-23`）。

## 根拠

- 読み取りと判定: `src/kernels/cuda/sampler.cu:1255-1258`、`sycl/src/kernels/cuda/sampler.dp.cpp:1492-1495`
- dispatch 条件: `src/kernels/cuda/sampler.cu:1261-1263`、`sycl/src/kernels/cuda/sampler.dp.cpp:1498`
- cluster 実行条件と device cache: `src/kernels/cuda/sampler.cu:1190-1237`
- HIP / SYCL で launch されない: `src/kernels/cuda/sampler.cu:1191-1194`、`sycl/src/kernels/cuda/sampler.dp.cpp:1403-1405`
- cluster size / kernel 設計: `src/kernels/cuda/sampler.cu:189-209`、`include/strata/kernels/sampler.hpp:46-50`
- 一度だけ読む: `src/kernels/decode_cluster_parity.cpp:17-18,378-379`（テスト内の設定だが static cache の事実を示す手掛かり。判定は本番コードの `static const bool`）
- 呼び出し元: `src/core/verify.cpp:1792,2336,3000,3408`、`src/core/mtp.cpp:999`
- docs 照合: `docs/DETAILS.md:24-28`
