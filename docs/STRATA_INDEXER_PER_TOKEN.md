# `STRATA_INDEXER_PER_TOKEN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA（sparse-attention）を使うモデルの prompt prefill における indexer key の append 方法を切り替える A/B 用フックです。既定では chunk 内の `T` 個を `native_qsa_indexer_append_batch()` で一括追記します。変数が設定されていると、同じ chunk の各 token について `native_qsa_indexer_append()` を順番に呼ぶ旧経路になります。どちらの経路でも、chunk 内すべての append を終えてから QSA の selection 処理へ進みます。

これは prefill 内の QSA indexer append を選ぶもので、decode や verifier の append 経路を切り替えるものではありません。実装には CUDA/HIP 側の `src/prefill/prefill.cpp` と SYCL 側の `sycl/src/prefill/prefill.cpp` に同じ判定があります。

## 値と判定

| 環境の状態 | 判定 | 動作 |
|---|---|---|
| 未設定 | 無効 | chunk 単位の batch append |
| 空文字を含め、何らかの値が設定済み | 有効 | token ごとの append |

コードは `std::getenv("STRATA_INDEXER_PER_TOKEN") != nullptr` を使い、値を数値や文字列として parse しません。したがって `1` だけでなく `0`、`false`、空文字も設定されていれば有効です。大文字小文字や値の後続文字も判定に関係しません。CLI 引数・設定ファイルとの優先順位や別環境変数による上書きはありません。

判定は関数内の `static const bool` に保存され、プロセスで最初にこの QSA prefill 分岐へ到達したときに一度だけ評価されます。その後に環境を書き換えても再評価されません。

## 有効になる条件

- prompt prefill が `Prefill::run_impl()` の QSA layer 処理まで進むこと。QSA layer がないモデルでは、この判定も append も実行されません。
- CUDA/HIP ビルドでは `src/prefill/prefill.cpp`、SYCL ビルドでは `sycl/src/prefill/prefill.cpp` の該当実装を通ること。
- 値が設定済みであること。値が未設定なら、batch 経路のままです。

この分岐は indexer の append の後に行う QSA selection の kernel や batch size を選ぶものではありません。selection は append loop の完了後、同じ `T` 件について従来どおり処理されます。

## 実行時の詳細

QSA layer ごとに、prefill は indexer key projection の結果 `m.idx_raw` と chunk の token 数 `T` を用意します。既定経路では `native_qsa_indexer_append_batch(m.idx_raw, T, p0, ...)` を一度呼びます。有効時は `t = 0..T-1` の順に、`m.idx_raw + t * 128` とその token の step position を渡して単一 append を呼びます。両経路ともその後に `qsa_block_scores` と `qsa_block_topk` を実行します。

append 呼び出しが例外を投げると、prefill は `prefill indexer: ` を付けたエラー文字列を設定して失敗を返します。環境変数自体についてのログ出力はありません。

実装コメントは batch 経路を「一 token ごとの旧実装に対し chunk の append を三つの kernel launch にする」最適化として説明しています。共通 header は batch append が単一 append を順に呼んだ場合と同じ buffer state を作ると説明し、`docs/AMD_HIP_PERFORMANCE.md` も C-2 の batched QSA indexer append を各 backend で bit-exact と記しています。この環境変数に関する独立した性能測定値は、参照した資料にはありません。

## 根拠

- `src/prefill/prefill.cpp:2713-2732` — CUDA/HIP 系の環境判定、batch と token 単位の分岐、selection 前の例外処理。
- `sycl/src/prefill/prefill.cpp:2997-3016` — SYCL 系の同じ分岐。
- `include/strata/kernels/native_qsa_indexer.hpp:34-44` — batch API と単一 append API の契約。
- `src/kernels/cuda/native_qsa_indexer.cu:268-307` — CUDA/HIP 側の単一 append と batch append の実装。
- `sycl/src/kernels/cuda/native_qsa_indexer.dp.cpp:467-568` — SYCL 側の単一 append と batch append 実装。
- `docs/AMD_HIP_PERFORMANCE.md:135-140` — C-2 の batched append が全 backend で bit-exact との資料記述。ここに記された性能測定は当該変数の比較測定ではありません。
