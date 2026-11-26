# `STRATA_QSA_WARP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA block selection と prompt attention で、Ampere 世代以降の GPU をそれぞれ旧来の warp scorer／Turing 用 attention kernel として扱う A/B 用スイッチ。`select` は selection 側、`attn` は prompt attention 側だけに作用し、`1` は両方に作用する。いずれも値を有効にすると実 GPU の compute capability を書き換えるのではなく、各処理の dispatch 判定に使う値を `7` または `75` に置き換える（`engine/src/kernels/cuda/qsa_select.cu:2377-2391`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2508`）。

## 値と判定

どちらの CUDA 実装も `std::getenv` で取得した文字列を `strcmp` で完全一致比較する。数値変換や空白除去、大文字小文字変換はない。変数未設定、空文字、`0`、`true`、`false`、`01`、`1anything`、`SELECT` などはスイッチとして無効。空文字も「設定されている」だけでは有効にならない。

| 値 | QSA selection (`qsa_block_scores_tc`) | prompt attention (`qsa_prompt_attn_batch`) |
|---|---|---|
| unset、空文字、その他の文字列 | 無効 | 無効 |
| `1` | 有効 | 有効 |
| `select` | 有効 | 無効 |
| `attn` | 無効 | 有効 |

CUDA selection は実 GPU の major capability を取得できた後、デバイスごとのキャッシュが未初期化の場合にのみ変数を読み、`1` または `select` なら判定用 major を `7` にする（`engine/src/kernels/cuda/qsa_select.cu:2377-2391`）。CUDA prompt attention も同様にデバイスごとの初回判定で読み、`1` または `attn` かつ実 capability が `75` 以上なら判定用 capability を `75` にする。sm_75 未満では設定値を認めず実 capability のままにする（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2482-2500`）。

## 有効になる条件

- CUDA の `qsa_block_scores_tc` / `qsa_prompt_attn_batch` が呼ばれること。geometry 不適合、空の query、必要な入力や KV pool の欠落などで呼び出し側が fallback する経路では、この値でその kernel を強制起動しない（`engine/src/kernels/cuda/qsa_select.cu:2309-2312`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2478,2519-2521`）。
- selection 側で値が有効になると判定用 major は 7 となり、通常の TF32 tensor-core scorer（sm_80 以上）は選ばれず `qsa_block_scores_tc` は `false` を返す。その後の caller は通常 `qsa_block_scores` の warp 実装へ進む。例外として `STRATA_SELECT_SIMT` が `1` または `2` であれば、sm_80 未満向け FP32 tiled scorer を試し、成功時はそちらを使う。geometry 等でそれも使えないときは caller の warp scorer に戻る（`engine/src/kernels/cuda/qsa_select.cu:2391-2422`、`engine/src/prefill/prefill.cpp:5377-5393,9450-9457`）。
- attention 側は CUDA の実 capability が sm_75 以上の場合だけ Turing 判定に切り替わる。sm_75 未満では switch を無視する。`STRATA_PROMPT_ATTN_OLD` が設定されて呼び出し側が旧経路を選ぶ場合、`qsa_prompt_attn_batch` 自体が呼ばれない（`engine/src/prefill/prefill.cpp:5537-5557,9461-9468`）。
- CUDA 以外ではこの変数による同じ切替は行わない。HIP の prompt attention は読み取った capability を `turing` / `volta` 判定に使わず HIP WMMA 条件へ進む。HIP の selection は CUDA 側のこの capability 分岐ではなく HIP 用 scorer 判定を使う（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2509-2518`、`engine/src/kernels/cuda/qsa_select.cu:2313-2320`）。SYCL 移植ファイルにも読み取りはあるが、selection はその判定値に関係なく `false` を返して caller fallback へ進み、prompt attention は capability 値を捨てて ESIMD/XMX を試すため、この変数で dispatch は変わらない（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1729-1757`、`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1984-2016`）。
- `STRATA_SELECT_TWO_PASS` が有効でも、warp 扱いにより sm_80 以上の tensor-core scorer が使えない場合は two-pass selection は実行されず、selection は通常経路になります（`engine/src/kernels/cuda/qsa_select.cu:3873-3902`）。

## 実行時の詳細

selection は `qsa_block_scores_tc` の geometry 検査後、GPU ごとの `static int cc_major[64]` が未初期化のときに一度判定する。prompt attention も `n_q > 0` の呼び出しで `static int cc[64]` を GPU ごとに一度判定する。設定値は各関数内で GPU ごとに cache されるため、その GPU で最初の判定を終えた後にプロセス内の環境値が変わっても再評価されない。別 GPU の初回判定は別に行われる（`engine/src/kernels/cuda/qsa_select.cu:2309-2312,2377-2391`、`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2499`）。

prompt attention では、判定用 capability が 75 以上 80 未満なら `turing` が立ち、int8 KV 経路は `STRATA_PROMPT_ATTN_V1` が設定されているか、`STRATA_PA_V2T` が有効でない限り `launch<1>` に進む。`STRATA_PA_V2T` が有効なら `launch_i8` に進み、Ampere 以降向け `launch_i8v3` は `!turing` 条件を満たさないため選ばれない。Q4 KV は `STRATA_PROMPT_ATTN_Q4_TC` が有効でなければ Turing 条件でこの batched kernel を断り、呼び出し側の旧 attention 経路へ fallback する（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2501-2508,2522-2568`）。他の KV 構成は同関数内の形式別分岐に従う。

この変数自体の有効・無効を示すログはない。`STRATA_SELECT_TWO_PASS` も要求されている場合に限り、two-pass を使えない経路の最初の判定で次の stderr 行を出す。warp 扱いの CUDA GPU では理由部分が `this CUDA card or with STRATA_QSA_WARP` になる（`engine/include/strata/kernels/qsa_two_pass_status.hpp:12-34`、`engine/src/kernels/cuda/qsa_select.cu:3896-3902`）。

```text
strata: STRATA_SELECT_TWO_PASS=1 is not used on this CUDA card or with STRATA_QSA_WARP: the two-pass scorer runs only in the CUDA prompt path's tensor-core selection (sm_80+); the selection is unchanged
```

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2309-2312,2377-2422` — geometry、CUDA capability 判定、値の比較、sm_80 未満の SIMT/fallback。
- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2508,2519-2568` — prompt attention の capability cache と KV 形式別 kernel 分岐。
- `engine/src/prefill/prefill.cpp:5377-5393,5537-5557,9450-9472` — selection と attention の呼び出し、旧経路への fallback。
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1729-1757`、`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1984-2016` — SYCL 側の読み取りと dispatch への非適用。
- `engine/include/strata/kernels/qsa_two_pass_status.hpp:12-34`、`engine/src/kernels/cuda/qsa_select.cu:3873-3902` — 関連スイッチの unsupported 判定とログ。
