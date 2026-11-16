# `STRATA_SYCL_TLA_ATTN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この名前は、ビルド時には SYCL の TLA FP32 prompt attention 実装を含める CMake option、実行時にはその実装を選択候補にする環境変数として使われる。ビルド option は既定で `OFF` であり、`ON` にすると TLA ソースを `strata_kernels` に追加し、`strata_prefill` に `STRATA_SYCL_TLA_ATTN=1` compile definition を付ける。実行時の環境変数は、この compile definition がある `sycl/src/prefill/prefill.cpp` のコードでのみ評価される。したがって実行時に `STRATA_SYCL_TLA_ATTN=1` を設定するだけでは、TLA 実装を含まないビルドに機能は追加されない。`sycl/CMakeLists.txt:280-302`, `sycl/src/prefill/prefill.cpp:42-44,3637-3643`

有効時も常に TLA に切り替える設定ではない。QSA prompt attention の通常のバッチ実装が処理を受け持たず、さらにバッチ幅・選択幅・デバイス・KV pool などが適合した場合に限り、該当する attention batch の計算を `qsa_prompt_attn_tla_batch` に渡す。適合しない場合は SYCL の per-cell または decode attention に進む。`sycl/src/prefill/prefill.cpp:3633-3655`, `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2012-2016`

## 値と判定

読み取りは `getenv` と `v && v[0] == '1'` の判定で、文字列全体や数値として parse しない。先頭文字が ASCII `1` なら有効、そうでなければ無効で、大文字小文字や後続文字は判定対象外。`1`, `10`, `1anything` は有効、未設定・空文字・`0`・`0anything`・`true`・` 1`・`2` は無効となる。数値の範囲や境界はない。判定結果は関数内 `static const bool` に保存され、初回にこのコードへ到達した後の環境変更は反映されない。`sycl/src/prefill/prefill.cpp:3637-3638`

| 条件（build / 実行経路） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| TLA compile definition あり、後述の呼び出し条件を通過 | false | 先頭文字が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `0anything`, `true`, ` 1`, `2` など |
| TLA compile definition なし | 実行時読み取りコード自体がない | 該当なし | 該当なし |

同じ名前の CMake option は独立した build-time 設定で既定 `OFF`。`ON` には `STRATA_SYCL_AOT=bmg-g31`、指定された `STRATA_SYCL_TLA_DIR` に TLA headers が存在すること、および `STRATA_ZE_LOADER` が必要で、不足時は CMake の `FATAL_ERROR` になる。実行時環境変数の値でこれらの build 条件を変更することはない。`sycl/CMakeLists.txt:282-302`

## 有効になる条件

- SYCL build で CMake option `STRATA_SYCL_TLA_ATTN=ON` を指定して TLA 実装をビルドしていること。条件を満たさない build では該当する `#ifdef` 内の include と dispatch がコンパイルされない。`sycl/CMakeLists.txt:282-302`, `sycl/src/prefill/prefill.cpp:42-44,3637-3643`
- QSA prompt attention の経路で、`STRATA_PROMPT_ATTN_OLD` が未設定なら `qsa_prompt_attn_batch` が `false` を返すこと。通常の SYCL 経路でその関数が先に処理を受け持つ場合、この環境変数は評価されない。`STRATA_PROMPT_ATTN_OLD` は値ではなく設定有無を見ており、空文字でも旧経路を選ぶため、旧経路でも以下の TLA 条件を満たせば TLA が試行される。`sycl/src/prefill/prefill.cpp:3613,3633-3642`, `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2012-2016`
- attention sub-batch の `nb` がちょうど `32`、選択幅 `m.cap` が `2051` であること。`STRATA_ATTN_BATCH` はこの幅に影響し、既定は `32`。QSA の既定 geometry では `idx_top_k=2048`, `idx_block=4` から選択幅が最大 `2051` となる。異なる batch 幅または選択幅では TLA 呼び出しを飛ばす。`sycl/src/prefill/prefill.cpp:744-757,1536-1538,3635-3642`, `include/strata/kernels/qsa.hpp:96-107,131-139`
- TLA 関数が要求する shape と pool 条件に合うこと。head dimension `256`、KV heads `2`、query heads `24`、正の page size、必要な query / ids / steps / scratch / output と INT8 K/V・scale・page table があり、Q4 K/V pool ではないこと、さらに `v_q` は 4-byte、query と `k_q` は 64-byte 境界に整列していること。失敗時は関数が `false` を返し、呼び出し元が通常の SYCL fallback を実行する。`sycl/src/kernels/cuda/qsa_prompt_attn_tla.dp.cpp:171-175`
- Level Zero backend を使い、`STRATA_HAVE_ZE` が定義されたコードでは Intel vendor ID `0x8086` と device ID `0xe223` に適合すること。その他の backend、デバイス、または `STRATA_HAVE_ZE` なしでは TLA 関数が `false` を返し、fallback する。`sycl/src/kernels/cuda/qsa_prompt_attn_tla.dp.cpp:176-190`
- TLA が false を返した場合、`STRATA_ATTN_PERCELL` が未設定、空文字、または先頭文字が `0` 以外なら per-cell kernel を使う。先頭文字 `0` なら decode batch kernel を使う。これは TLA 変数とは別の fallback 選択である。`sycl/src/prefill/prefill.cpp:3644-3655`

## 実行時の詳細

QSA prompt attention の batch で、まず `STRATA_PROMPT_ATTN_OLD` の設定有無、または `qsa_prompt_attn_batch` の成否により既存の batch kernel 経路と fallback loop が選ばれる。fallback loop 内で環境変数の static cache を初めて評価し、true かつ `nb == 32` かつ `m.cap == 2051` の場合に TLA 関数を呼ぶ。関数が `true` を返せば `continue` してその batch の fallback kernel を省く。`false` なら `STRATA_ATTN_PERCELL` による per-cell / decode kernel に進む。`sycl/src/prefill/prefill.cpp:3633-3655`

TLA 関数は入力ポインタ・shape・alignment・pool を検査し、Level Zero 対応時には device handle ごとに device ID 判定結果を `thread_local` cache する。不適合は通常 `false` で呼び出し元へ戻る。適合した場合に kernel を launch し、その thread で初回だけ成功ログを出して `true` を返す。対象変数自体の判定 cache はプロセス内の関数 static で、初回の fallback loop 到達時に作られる。`sycl/src/kernels/cuda/qsa_prompt_attn_tla.dp.cpp:171-195`, `sycl/src/prefill/prefill.cpp:3637-3642`

## ログと測定値

TLA 関数が成功した thread では、最初の成功時に stderr へ `strata: using SYCL TLA FP32 prompt attention` を出す。以降は同じ thread からの成功で再表示しない。不適合で `false` を返す場合や、環境変数が false の場合に、この変数を理由とする警告・エラー・fallback ログはない。`sycl/src/kernels/cuda/qsa_prompt_attn_tla.dp.cpp:191-195`, `sycl/src/prefill/prefill.cpp:3637-3655`

`docs/DETAILS.md` には本変数またはこの TLA 経路の性能測定値を確認できなかったため、速度・精度の測定値は記載しない。

## 根拠

- CMake option、build 要件、ソース追加と compile definition: `sycl/CMakeLists.txt:280-302`
- compile guard、runtime 値判定、dispatch、fallback: `sycl/src/prefill/prefill.cpp:42-44,3613-3655`
- 既定 batch 幅と上限、選択幅の算出: `sycl/src/prefill/prefill.cpp:744-757,1536-1538`; `include/strata/kernels/qsa.hpp:96-107,131-139`
- TLA kernel の入力条件、backend/device 判定、fallback 戻り値と成功ログ: `sycl/src/kernels/cuda/qsa_prompt_attn_tla.dp.cpp:171-195`
- 通常の SYCL prompt-attention batch kernel が非対応時に `false` を返す dispatch: `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2012-2016`
