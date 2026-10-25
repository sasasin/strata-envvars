# `STRATA_MULTI_BLOCK_ARGMAX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA と同梱 SYCL backend の head 処理で、複数 block に分ける argmax / top probability kernel を使うかを制御します。対象コードでは `multi_block_head_ops()` がこの設定を返し、MTP の候補 token 確率計算を 8 block の `row_top_prob_split()` に切り替えます。また、CUDA device の compute capability major が 8 の場合、speculative verify と MTP の greedy argmax を複数 block の `argmax_rows()` に切り替えます。

## 値と判定

値全体を真偽値として parse するのではなく、`std::atoi()` の結果が 0 かどうかで判定します。

| 値 | `multi_block_head_ops()` |
|---|---|
| unset | 有効 |
| 数値変換結果が 0（空文字、`0`、`false`、数字で始まらない文字列など） | 無効 |
| 数値変換結果が 0 以外（例: `1`, `-1`, `2`, `1tail`） | 有効 |

`atoi` は先頭空白と符号を許し、数字列の後ろは判定に使いません。したがって `0tail` は無効、`1tail` は有効です。値の大文字小文字自体は解釈されません。数値変換できない文字列と空文字は 0 として扱われます。

判定値は `multi_block_head_ops()` 内の `static const bool` に保存されます。最初の呼び出し後にプロセス環境を変更しても再評価されません。CUDA と SYCL の実装で既定値と parse は同じです（`src/kernels/cuda/verify_kernels.cu:879-889`、`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1571-1581`）。

## 有効になる条件

- HIP (`__HIPCC__`) では `multi_block_head_ops()` と `argmax_rows_wanted()` が常に `false` を返し、この設定は使われません。HIP は一 block の `row_top_prob()` と既存の greedy sampler 経路を使います。
- CUDA/SYCL では、値が有効なら MTP の各 head-logit row に対する top probability 計算に `row_top_prob_split()` を使います。無効なら同じ呼び出し元が `row_top_prob()` を使います（`src/core/mtp.cpp:993-1003`、`sycl/src/core/mtp.cpp:1136-1146`）。
- greedy argmax の `argmax_rows()` 切り替えはさらに device の compute capability major が 8（SM 8.0–8.9）であることが必要です。device 情報取得に失敗した場合、または他の世代の場合は `argmax_rows_wanted()` が false になり、呼び出し元は `sample_tokens()` を使います（`src/kernels/cuda/verify_kernels.cu:891-904`、`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1583-1597`）。
- MTP では coupled draft sampling の分岐に入ると、greedy argmax と top probability の処理より前に関数を終了します。その経路ではこれらの切り替えは実行されません（`src/core/mtp.cpp:981-992`、SYCL: `sycl/src/core/mtp.cpp:1129-1135`）。

## 実行時の詳細

`argmax_rows_wanted()` は SM 8.x かつ `multi_block_head_ops()` が有効な場合だけ true です。呼び出し元の verifier は各 verify window の head logits について、true なら `argmax_rows()`、false なら greedy `sample_tokens()` を起動します（`src/core/verify.cpp:1783-1796`、`sycl/src/core/verify.cpp:1626-1636`）。MTP の head も同じ分岐を持ちます（`src/core/mtp.cpp:993-1000`、`sycl/src/core/mtp.cpp:1136-1143`）。複数 block argmax は row を最大 128 block に分け、各 block の候補を scratch に書き、最後に候補をまとめます。header は tie 時の最小 index、NaN を選ばないこと、および全値が `-inf` 以下の場合に index 0 を返すことを single-token greedy pick と同じ仕様として記しています（`src/kernels/cuda/verify_kernels.cu:710-787`、`include/strata/kernels/verify_kernels.hpp:121-126`）。

MTP の通常経路では、argmax の後に選択 token の確率を計算します。有効時の `row_top_prob_split()` は row ごとに 8 block で指数和を部分計算し、部分和を合算して `1 / total` を出力します。無効時は一 block の `row_top_prob()` に戻ります（`src/kernels/cuda/verify_kernels.cu:702-704,789-819,836-841`）。この関数は CUDA/SYCL の head kernel を共有する名前ですが、MTP 呼び出し元で確率分岐が確認できるものです。

この変数は `STRATA_ARGMAX_MULTI` とは別です。後者は `sample_tokens()` 内で SM 9.0+ の cluster greedy kernel を使うかを決めます（`src/kernels/cuda/sampler.cu:1252-1263`）。`STRATA_MULTI_BLOCK_ARGMAX=0` はこの別フラグを変更しません。SM 8.x で argmax の複数 block 分割を無効にしたとき、呼び出し元は通常の sampler に戻ります。

実装に、この変数専用のログ、警告、エラー出力はありません。関連 header のコメントは `STRATA_MULTI_BLOCK_ARGMAX=0` を `multi_block_head_ops()` の無効化条件として示しています（`include/strata/kernels/verify_kernels.hpp:137-142`）。`docs/DETAILS.md` では近い機能の別フラグ `STRATA_ARGMAX_MULTI` に触れていますが、この環境変数の具体的な値や挙動の説明は見つかりませんでした（`docs/DETAILS.md:28`）。

## 根拠

- `src/kernels/cuda/verify_kernels.cu:879-904` — 値の読み取り、既定値、HIP 除外、SM 8.x 条件。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:1571-1597` — SYCL 実装の同じ判定。
- `src/core/verify.cpp:1783-1796`、`sycl/src/core/verify.cpp:1626-1636` — verify の greedy argmax 呼び出し。
- `src/core/mtp.cpp:981-1003`、`sycl/src/core/mtp.cpp:1129-1146` — MTP の coupled sampling、argmax、top probability の分岐。
- `src/kernels/cuda/verify_kernels.cu:702-819,823-841`、`include/strata/kernels/verify_kernels.hpp:121-142` — kernel 処理と公開関数の説明。
- `src/kernels/cuda/sampler.cu:1252-1263`、`include/strata/kernels/sampler.hpp:47-50` — 独立した `STRATA_ARGMAX_MULTI` の制御。
