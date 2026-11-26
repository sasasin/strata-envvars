# `STRATA_MMVQ_IL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA verifier の一部の量子化行列ベクトル計算で、interleaved small-batch MMVQ (`native_mmvq_il`) を選べるようにする master switch。未設定では有効、値の先頭が `0` の場合だけ無効になる。無効時は対象計算を通常の `native_mmvq` に送る。生成器全体や通常の単一 token 推論の一律な切替ではなく、verifier 内でこの経路を使う箇所に作用する。読み取りと利用箇所は `engine/src/core/verify.cpp:193-194,1831-1857,1910-1919,2281-2288,2731-2737,3101-3119`。

対象は、verifier の GDN/QSA 投影、shared-expert 計算に渡す interleaved scratch の有無、およびロード済み LM head の計算。実際に interleaved kernel が呼ばれるかは別途 `native_mmvq_il_supported` の条件にもよる。行列の量子化型や行数テーブルをこの変数自体が指定するわけではない。CUDA 実装は対応型・形状・GPU でのみ有効化し、対象外なら通常 kernel へ fallback する（`engine/src/kernels/cuda/native_mmvq.cu:4218-4227,4230-4234`）。

## 値と判定

`std::getenv("STRATA_MMVQ_IL")` の結果を関数内 `static const bool` に一度だけ保存する。未設定 (`nullptr`) は有効。設定されている場合は先頭 1 文字だけを見て、`'0'` なら無効、それ以外なら有効とする。空文字は先頭文字が NUL なので有効。文字列全体の parse、数値検査、大文字小文字変換、空白除去はしない（`engine/src/core/verify.cpp:194`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 全 build | 有効 | 空文字、`1`、`true`、`false`、` 0`、`00`、`0anything` 以外で先頭が `0` でない文字列 | `0`、`00`、`0anything`（先頭が `0` なら後続を問わない） |

ここでの「有効」は master switch が通る意味であり、GPU・型・形状などが未対応なら interleaved kernel は使われない。

## 有効になる条件

- 読み取り値が有効で、対象処理が verifier の該当経路を通ること。読み取りは初めて `g_mmvq_il()` が呼ばれた時点で行い、その後はプロセス内の static 値を再利用する。実行中に環境を変更しても再評価されない（`engine/src/core/verify.cpp:194`）。
- interleaved MMVQ の CUDA 実装では列数が 1..8、`g_multi_exact` が有効、GPU architecture が対応していることが必要。対応型は ggml type 23 / 12 / 13 / 14 / 11。さらに `il_rows(...)` または `g_tune_rows` が 0 でないこと（`engine/src/kernels/cuda/native_mmvq.cu:4218-4227`）。
- CUDA architecture 条件は sm_80 以上、sm_70 は `STRATA_SM70_TABLE` が有効、sm_75 は `STRATA_SM75_IL` 等の switch 条件、sm_60 / sm_61 は各 `STRATA_SM60_TABLE` / `STRATA_SM61_TABLE` の条件。device ordinal 0..15 ごとに対応可否を cache する（`engine/src/kernels/cuda/native_mmvq.cu:4190-4214`）。
- 対象形状が `dense_i8_tc_mmvq` によって処理される条件（`g_tune_rows == 0`、`n_out >= 1024`、列数がその最小数以上、型対応、`dense_i8_tc_decode_enabled()`）では `native_mmvq_il_supported` は false になり、通常の `native_mmvq` 側へ進む（`engine/src/kernels/cuda/native_mmvq.cu:4220-4225`）。
- HIP では interleaved path の stub が常に unsupported を返し、`native_mmvq_il` も通常 `native_mmvq` を呼ぶ。この変数が有効でも HIP で interleaved kernel は選ばれない（`engine/src/kernels/cuda/native_mmvq.cu:4255-4268`）。
- Q8_1 の通常 quantize と interleaved copy を一つの呼出しで作る `STRATA_QIL` 経路は、HIP 以外で、`STRATA_QIL` の値または sm_75 の既定、列数 2..4、および本変数が有効な場合に限る。本変数が無効なら通常 quantize に戻る（`engine/src/core/verify.cpp:1835-1846`）。
- shared-expert では fork stream を使わない場合にだけ scratch (`xil_`) を渡す。本変数が無効、または fork stream の場合は null を渡すため shared-expert の interleaved gate/up/down 分岐は成立しない。さらに shared-expert 実装側で token 数 2 以上と各行列の対応が必要（`engine/src/core/verify.cpp:2731-2737`, `engine/src/kernels/cuda/shared_expert.cu:229-256`）。
- LM head が split の場合は `run_verify_split` に本変数の判定が渡され、各 device 側で対応判定を通った場合だけ interleaved MMVQ を使う。split でない head も対応判定が必要（`engine/src/core/verify.cpp:3101-3119`, `engine/src/core/native_head.cpp:436-477`）。
- GDN/QSA の各投影でも `side_proj` 等の経路条件や型・列数・出力行数によって通常 MMVQ が選ばれる場合がある。たとえば QSA の追加 projection では `side_proj` が false なら `q_il` 自体が false（`engine/src/core/verify.cpp:2281-2288`）。

## 実行時の詳細

verifier は `g_mmvq_il()` を条件に、対応した投影で `native_mmvq_il` を選択する。必要な interleaved copy がまだないときは `native_q8_1_interleave` を先に呼び、既存の通常 MMVQ 入力 `xq_` と追加の `xil_` を渡す。`STRATA_QIL` 経路では量子化と copy の作成をまとめる（`engine/src/core/verify.cpp:1831-1857`）。LM head でも非 split 経路は interleave 作成後に同 kernel を呼び、split 経路は各側で別々に対応可否を確認する（`engine/src/core/verify.cpp:3101-3119`, `engine/src/core/native_head.cpp:449-477`）。

対応判定に失敗した場合、呼び出し側は通常 `native_mmvq` を選ぶ。`native_mmvq_il` 自体に到達した場合でも、内部の対応判定が false なら `native_mmvq` に fallback する（`engine/src/core/verify.cpp:1848-1857`, `engine/src/kernels/cuda/native_mmvq.cu:4230-4234`）。

この変数はプロセスへ起動時設定を転送したり、モデルを変更したりしない。読み取りは verifier が最初に条件を評価するまで遅延し、以後 cache される。対象 kernel の launch check や CUDA エラーが発生した場合の上位処理は通常の verifier / kernel エラー経路に従う。split head では例外を `verify head: ` の prefix 付き `err` に変換して false を返す（`engine/src/core/verify.cpp:3121-3124`）。

## ログと測定値

本変数の値や interleaved 経路の選択を報告する専用ログは、確認した読み取り・分岐にない。測定値は本変数の実装根拠として記載しない。fallback はログではなく対応判定後の通常 MMVQ 呼出しとして行われる（`engine/src/core/verify.cpp:1848-1857`, `engine/src/kernels/cuda/native_mmvq.cu:4218-4234`）。

## 根拠

- `engine/src/core/verify.cpp:193-194` — master switch の値判定と static cache。
- `engine/src/core/verify.cpp:1831-1857` — Q8_1 入力の作成、投影 dispatch と fallback。
- `engine/src/core/verify.cpp:1910-1919,2281-2288` — GDN/QSA の追加 projection 条件。
- `engine/src/core/verify.cpp:2731-2748` と `engine/src/kernels/cuda/shared_expert.cu:229-256` — shared-expert scratch と消費側の条件。
- `engine/src/core/verify.cpp:3101-3124` と `engine/src/core/native_head.cpp:436-477` — LM head の通常・split 経路。
- `engine/src/kernels/cuda/native_mmvq.cu:4190-4271` — architecture 条件、型・形状条件、dense i8 fallback と HIP stub。
