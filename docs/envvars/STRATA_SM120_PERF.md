# `STRATA_SM120_PERF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

compute capability 12.0（sm_120）の CUDA GPU 向けに、複数の性能スイッチの未設定時既定値を有効にする。`sm120_series()` がこの変数を一度判定し、`sm120_default()` / `sm12x_default()` を通じて CUDA のカーネル選択や一部の既定値に使う。`STRATA_SM120_PERF=0` ならこの既定経路を無効にする。個々のスイッチを明示設定した場合は、その個別設定の判定が優先される。共通判定とアーキテクチャ判定は `engine/include/strata/core/sm120_series.hpp:32-42,60-81`、個別の CUDA 呼び出し例は `engine/src/kernels/cuda/qsa_decode_attn.cu:902-922` と `engine/src/kernels/cuda/fused_gr.cu:1582-1607`。

同一 compute capability の CUDA GPU だけが見えている起動では、Strata は別途その GPU 用の個別環境変数群を設定する。sm_120 の一括表には `STRATA_HC_UPMIX`, `STRATA_Q80_ROWS1`, `STRATA_EXP_MODE`, `STRATA_SIDE_MIXER`, `STRATA_DEQUANT_SIDE`, `STRATA_QFUSE`, `STRATA_LFUSE`, `STRATA_PLE_COMPACT`, `STRATA_PLE_COPY_STREAM`, `STRATA_PF_FUSED_KQ`, `STRATA_PREFILL_CPU_SHARE_NT`, `STRATA_PREFILL_NVFP4` が含まれる。GPU が 16 GiB 以下なら `STRATA_ADAPT_FETCH=2` も候補となり、そうでなく 16 GiB より大きければ `STRATA_VERIFY_DEVICE_HITS=1` が候補となる。各設定済みの個別変数は、値が `0` の場合も含めて上書きされない（`engine/src/core/nv_defaults.cpp:104-135,222-238`）。

## 値と判定

| 読み取り経路 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `sm120_series()` を使う CUDA の既定分岐 | on | `atoi` の結果が非ゼロ（例: `1`, `-1`, `1junk`） | `atoi` の結果が 0（例: `0`, 空文字, `true`, `0anything`, 空白だけ） |
| `nv_default_env()` の一括表 | on（ただし `STRATA_DEFAULTS=026` なら表を出さない） | 先頭文字が `'0'` でない設定値（例: `1`, `true`, 空文字, ` 0`） | 先頭文字が `'0'`（例: `0`, `0anything`）、または `STRATA_DEFAULTS=026` |

`sm120_series()` は文字列全体の検証ではなく `std::atoi(e) != 0` を使うため、数値として読める先頭部分で判定し、数値でない文字列は 0 扱いになる。空文字も 0 扱い。これに対し、一括表の `off()` は値が設定されていて先頭文字が `'0'` の場合だけ off とする。従って例えば `STRATA_SM120_PERF=true` は `sm120_series()` の既定分岐を無効にする一方、一括表を止めない。`STRATA_SM120_PERF= 0` は一括表を止めないが、`atoi` の結果は 0 なので `sm120_series()` 側は無効になる。判定実装は `engine/include/strata/core/sm120_series.hpp:33-38`、`engine/src/core/nv_defaults.cpp:14-18,104-107`。

## 有効になる条件

- アーキテクチャ既定分岐は、CUDA デバイスの compute capability が 12.0 であり、上記 `sm120_series()` の判定が on の場合に適用される。`sm120_default()` は `is_sm120()` とシリーズ判定の両方を要求する（`engine/include/strata/core/sm120_series.hpp:41-42,60-61`）。
- 一括表の自動設定は、起動時に見える GPU がすべて同一 compute capability である CUDA 経路で行われる。異なるアーキテクチャの複数 CUDA GPU では一括表は適用されず、sm_120 GPU が含まれ、かつ変数が未設定の場合、Strata は値を `"0"` に設定する。ユーザーが何らかの値を設定していれば保持する（`engine/src/program/generate.cpp:4422-4450,4451-4470`）。
- 一括表は `STRATA_DEFAULTS=026` が有効な場合にも適用されない（`engine/src/core/nv_defaults.cpp:104-107`）。これは一括表の抑止であり、すべての個別カーネルの未設定時 fallback を包括的に off にするとは限らない。`sm12x_default_v()` は `v026` を 12.1 側の条件に使い、sm_120 側の `sm120_default()` には渡さない（`engine/include/strata/core/sm120_series.hpp:78-81`）。たとえば `STRATA_SIDE_MIXER` の直接 fallback は同シリーズ判定を参照する（`engine/src/core/verify.cpp:272-292`）。一方、`STRATA_GR_V3_PF` / `STRATA_SMALL_UNR` は個別 fallback 側でも `STRATA_DEFAULTS=026` を確認する（`engine/include/strata/core/bw_dense_defaults.hpp:14-19`）。個別の設定変数は一括表により上書きされない（`engine/src/core/nv_defaults.cpp:222-234`）。
- CUDA の個別カーネル分岐にも同シリーズ判定が用いられる。例として Daily attention、hyper-connection up/down、SwiGLU、speculative verify の PDL、fused IQ prefill のタイル選択に使われる（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-922`; `engine/src/kernels/cuda/fused_gr.cu:1570-1607`; `engine/src/kernels/cuda/iq_kernels.cu:4584-4594`; `engine/src/kernels/cuda/verify_kernels.cu:2076-2093`; `engine/src/prefill/moe_fused_iq.cu:2887-2895`）。これらの機能は各個別スイッチ、カーネル属性・ビルド内容、カード属性、モデルのレイアウト等の条件でも制限される。変数が on であることだけでは全スイッチや全カーネルの実行を保証しない。
- `STRATA_SM120_PERF` 自体が GPU を選択したり、CLI 引数を上書きしたりする処理は見つからない。CUDA 一括表はユーザーが指定した各スイッチを保持し、混在 GPU 経路では同変数が未設定のときだけ `"0"` を設定する。

## 実行時の詳細

`sm120_series()` は関数内 `static const bool` に結果を保存する。最初に呼ばれた時点の環境を読み、そのプロセス内では以降の環境変更を再評価しない（`engine/include/strata/core/sm120_series.hpp:33-39`）。一括表の判定は `apply_nv_defaults()` が `nv_default_env()` を呼んだ時点で行われ、各既定値は対象の環境変数が未設定の場合だけ `_putenv_s(..., 0)` / `setenv(..., 0)` で設定される（`engine/src/core/nv_defaults.cpp:222-238`）。

この初期化は `generate.cpp` の CUDA 起動処理にあり、同一アーキテクチャなら `apply_nv_defaults()` を呼び、混在アーキテクチャなら別処理へ分岐する（`engine/src/program/generate.cpp:4422-4470`）。混在構成での `"0"` 設定は Windows では `_putenv_s`、その他では `setenv` を使い、値が未設定の場合に限る。これは子プロセスへの転送処理ではなく、Strata プロセス自身の環境を変更する処理である。

## ログと測定値

混在アーキテクチャの複数 GPU に sm_120 があり、変数が未設定なら、Strata は stderr に次の行を出す。

```text
strata: mixed-arch multi-GPU with sm_120: STRATA_SM120_PERF=0 (set STRATA_SM120_PERF=1 to override)
```

同一世代の CUDA GPU に対して一括表が一つ以上の設定を行った場合は、`apply_nv_defaults()` が stderr に `strata: sm_120 (Blackwell): ... speed switches on by default (STRATA_SM120_PERF=0 turns them off...` で始まる行を出し、設定した個別スイッチ名を続ける。一括表が空の場合はこの行を出さない（`engine/src/core/nv_defaults.cpp:240-255`）。性能値はソースコメントや `docs/DETAILS.md:1480-1490` に測定記録があるが、条件依存の記録であり、この文書では一般的な性能向上値として扱わない。

## 根拠

- `engine/include/strata/core/sm120_series.hpp:32-42,60-81` — `atoi` による一度限りの判定、compute capability 12.0 の判定、および 12.0/12.1 の既定分岐。
- `engine/src/core/nv_defaults.cpp:14-18,104-135,222-255` — 一括表の先頭文字判定、sm_120 の既定変数群、個別値保持、設定処理とログ。
- `engine/src/program/generate.cpp:4422-4470` — 初期化順、同一 GPU 世代での一括適用、混在 GPU での自動 off と警告。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:902-922`; `engine/src/kernels/cuda/fused_gr.cu:1570-1607`; `engine/src/kernels/cuda/verify_kernels.cu:2076-2093`; `engine/src/prefill/moe_fused_iq.cu:2887-2895` — 個別の実行経路におけるシリーズ判定と機能条件の例。
- `engine/include/strata/core/bw_dense_defaults.hpp:14-19`; `docs/DETAILS.md:1480-1490` — `STRATA_DEFAULTS=026` を含む関連する既定値制御と Strata の測定資料。
