# `STRATA_SCORES_MULTI`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の block score 計算で、複数 query の score を一つの kernel grid で計算する経路を選びます。通常の `block_scores_kernel` は query ごとに grid の y 軸を分け、query ごとに key block を読みます。multi 経路の `block_scores_multi_kernel` は最大 8 query を扱い、block を読む処理を query 間で共有します。主に小さな decode batch と prefill の pooled16 scoring が対象です。

## 値と判定

値は `std::atoi()` で整数に変換し、変換結果が 0 かどうかで判定します。文字列全体の厳密な数値検証はありません。

| 値 | 判定 |
|---|---|
| unset | 有効 |
| 空文字 | 無効（`atoi` の結果 0） |
| `0`、`00`、`-0`、数値変換できない文字列 | 無効 |
| `1`、`-1`、その他 0 以外の整数 | 有効 |
| 整数の前後に空白がある文字列、数値の後ろに文字が続く文字列 | `atoi` の変換結果で判定。例: ` 2tail` は有効、`0tail` は無効 |

先頭の空白と符号は `atoi` の変換規則に従い、変換可能な数値の後ろは判定に使われません。値は `qsa_block_scores()` 内の `static const bool` として初回評価時に保存されるため、同じプロセス内で後から環境変数を変更しても再評価されません。

根拠: `src/kernels/cuda/qsa_select.cu:1092-1105`、`sycl/src/kernels/cuda/qsa_select.dp.cpp:1566-1577`。

## 有効になる条件

値が有効でも、次の両方を満たす呼び出しに限り multi kernel が起動します。

- `nq <= MQ`（`MQ` は 8）。
- `active_blocks <= 0`。ヘッダー上の既定値は `-1` で、正の値は block 数を制限する呼び出し用です。

条件外、または環境変数を無効にした場合は `block_scores_kernel` を query ごとの grid で起動します。`nq <= 0` の呼び出しは何もせず戻り、geometry 不一致または `nq > 65535` は `qsa_block_scores: unsupported indexer geometry` を stderr に出して終了します。これらは環境変数の値にかかわらず先に判定されます。

CUDA/HIP 共通ソースと SYCL 用変換ソースに同じ判定と分岐があります。`qsa_block_scores()` は decode の verifier 経路と layer の fast-select 経路から呼ばれ、prefill の pooled16 scoring からも呼ばれます。通常の prefill scoring など、query 数が 8 を超える呼び出しではこの変数は経路を変えません。

根拠: `include/strata/kernels/qsa_select.hpp:27-30`、`src/kernels/cuda/qsa_select.cu:1092-1115`、`sycl/src/kernels/cuda/qsa_select.dp.cpp:1566-1610`、`src/core/verify.cpp:1367-1384`、`src/core/layer.cpp:1126-1129`、`src/prefill/prefill.cpp:2816-2822`。

## 実行時の詳細

multi kernel は grid を固定 256 CTA とし、各 CTA が block を stride して処理します。各 block の score は最大 8 query について計算し、結果を `out[query * max_blocks + block]` に書き込みます。query ごとの head 内積、正値部分の合計、最終 tail block の部分 block 加点は通常 kernel と同じ演算順です。ソースコメントは通常経路と同じ score bit になると説明していますが、この調査では実行測定や parity test は行っていません。

multi kernel の launch error は `qsa_block_scores multi: %s`、通常 kernel の launch error は `qsa_block_scores: %s` として stderr に出力され、その後プロセスを終了します。SYCL 変換側は multi kernel を SYCL queue に submit し、該当コードには CUDA 同様のエラーコード検査が置換された旨の DPCT コメントがあります。

## 文書との照合

`docs/DETAILS.md` および関連する設計資料に `STRATA_SCORES_MULTI` の説明やこの経路の測定値は見つかりませんでした。この文書はコード上の分岐・処理だけを記載しています。

## 根拠

- `include/strata/kernels/qsa_select.hpp:26-30` — score 配列の形、関数宣言、正の `active_blocks` の契約。
- `src/kernels/cuda/qsa_select.cu:29-56` — query ごとの通常 score kernel。
- `src/kernels/cuda/qsa_select.cu:810-866` — multi score kernel の処理。
- `src/kernels/cuda/qsa_select.cu:1092-1115` — 環境変数の読み取り、適用条件、各 kernel の起動とエラー処理。
- `sycl/src/kernels/cuda/qsa_select.dp.cpp:1111-1165,1566-1610` — SYCL 変換版の multi kernel と分岐。
- `src/core/verify.cpp:1367-1384`、`src/core/layer.cpp:1126-1129`、`src/prefill/prefill.cpp:2816-2822` — 実際の呼び出し例。
