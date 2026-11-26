# `STRATA_GU_SWIGLU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP の grouped routed-expert 処理で、条件を満たす gate/up を計算したあと、SwiGLU と q8_1 量子化までを `native_gu_swiglu_kernel` の一回の launch にまとめるかを制御する。通常経路は gate/up、SwiGLU、q8_1 の別々の処理を使う。この融合経路では gate/up の中間値をメモリーへ書き戻す処理を省く。カーネルコメントは置換元と同じ gate/up の dot、SwiGLU の丸め、`q8_1_store` を使うと説明している（`engine/src/kernels/cuda/iq_kernels.cu:3118-3124`）。

ユーザーが値を指定すれば、対応する grouped-expert 経路で GPU 世代に関係なく明示的な ON/OFF 指定として扱う。未設定時は CUDA の compute capability 12.0 では既定ルールを評価し、それ以外の CUDA 世代と HIP では OFF。sm_86 / sm_89 の CUDA build では、エンジン起動時の NVIDIA 既定値注入が未設定の変数に `1` を設定するため、通常は ON になる（`engine/src/kernels/cuda/iq_kernels.cu:4578-4595`、`engine/src/core/nv_defaults.cpp:41-43,51-58,75-89`）。

## 値と判定

`gu_swiglu_on()` が初回呼び出し時に `std::getenv` し、設定されていれば `std::atoi` の結果が 0 かどうかで判定する。文字列全体の検証はせず、`atoi` が先頭から数値として読める部分を使う。未設定は `-1` という番兵値になり、下表の build / GPU 既定判定へ進む。空文字は設定済みで `atoi("") == 0` のため OFF。int として表現できる非 0 の数値（例: `1`、`2`、`-1`）は ON、0 の数値（例: `0`、`0anything`）や数値で始まらない文字列（例: `true`、`false`、`words`）は OFF。先頭空白や符号は `atoi` の規則に従い、数値の後ろの文字は判定に影響しない。int の範囲を超える数値に対する `atoi` の動作は C/C++ の規定上保証されない（`engine/src/kernels/cuda/iq_kernels.cu:4578-4580`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| 任意の build / GPU で明示指定 | unset 時は下の build / GPU 既定判定へ進む | `1`, `2`, `-1`, `1tail` | 空文字, `0`, `true`, `false`, `0anything`, `words` |
| HIP build の未設定 | OFF | — | — |
| CUDA build、sm_120（compute capability 12.0）、同一 compute capability の可視 GPU | `sm12x_default` が真なら ON。`STRATA_SM120_PERF=0` または `STRATA_DEFAULTS=026` では OFF | — | — |
| CUDA build、sm_121 / GB10、またはその他の世代の未設定 | OFF（sm_121 は `kGb10GuSwiglu=false`） | — | — |
| CUDA build、sm_86 / sm_89 の単一世代構成での起動時 default table | 既定注入が `1` を設定する。sm_86 は `STRATA_SM86_PERF` が先頭文字 `0` の場合は注入しない。sm_89 は同様に `STRATA_SM89_PERF` が先頭文字 `0`、または `STRATA_DEFAULTS=026` の場合に注入しない | — | — |

sm_86 / sm_89 の default table はユーザーが `STRATA_GU_SWIGLU` を何らかの値で設定済みなら上書きしない。したがって、明示した空文字や無効文字列も default table の `1` より優先されて OFF になる（`engine/src/core/nv_defaults.cpp:222-234`）。

## 有効になる条件

- `engine/src/kernels/cuda/iq_kernels.cu` が build に含まれる CUDA または HIP build であること（`engine/cmake/strata_gpu_engine.cmake:98-108`）。他の backend ではこの読み取り経路は確認できない。
- grouped expert の gate/up 処理で、`gs_layout` が真、nibble layout ではなく、`g_exp_phase == 0`、`v1` ではなく、`expdec_mode()` の別経路が選ばれていないこと（`engine/src/kernels/cuda/iq_kernels.cu:7241-7248`）。`STRATA_EXP_LAYOUTS` build では `gs_layout` に fused gate/up layout や fallback 条件も関係する。
- `launch_gu_swiglu<TG>` が split 形式に対応し、`g_old_kernels`、`split_off<TG>()`、`g_no_sub16_gu` がすべて無効で、`L.had_block == 0`、`L.n_embd == 2560`、正の `L.n_ff` が 32 の倍数、かつ行ごとの dot 数が 80 であること（`engine/src/kernels/cuda/iq_kernels.cu:4601-4609`）。このため、値が ON でもすべてのモデル、量子化形式、expert layout で使われるわけではない。
- CUDA の sm_120 未設定既定が適用されるには、対象 device の属性取得に成功し、device index が `0..63` に入り、compute capability が 12.0 であること。device 属性取得失敗時は OFF へ進む（`engine/src/kernels/cuda/iq_kernels.cu:4584-4594`）。
- CUDA の起動時既定値注入は、可視 GPU がすべて同じ compute capability の場合にのみ `generate.cpp` から `apply_nv_defaults` が呼ばれる。異種 GPU 構成ではこの表による `STRATA_GU_SWIGLU` 注入は行われない（`engine/src/program/generate.cpp:4425-4449`）。ただし、変数を明示した値はカーネル側で引き続き評価される。
- 混在 GPU に sm_120 があり `STRATA_SM120_PERF` が未設定の場合、エンジンは `STRATA_SM120_PERF=0` を設定する。未設定の `STRATA_GU_SWIGLU` の sm_120 既定を抑止するが、ユーザーが `STRATA_GU_SWIGLU` 自体を明示指定している場合はそれが優先される（`engine/src/program/generate.cpp:4450-4469`、`engine/src/kernels/cuda/iq_kernels.cu:4579-4580`）。

## 実行時の詳細

通常の CUDA 起動では、可視 GPU が同一世代なら `generate.cpp` がモデル処理の前段で `apply_nv_defaults` を呼ぶ。sm_86 / sm_89 の表は未設定時に `STRATA_GU_SWIGLU=1` をプロセス環境へ追加し、stderr に既定で有効にしたスイッチ名を含む一覧を出す。明示値は `getenv(...) != nullptr` の条件で保持される。sm_120 の未設定既定は変数を環境へ追加せず、grouped-expert カーネルが `gu_swiglu_on()` を初回評価する時に device 属性を調べる（`engine/src/program/generate.cpp:4425-4449`、`engine/src/core/nv_defaults.cpp:222-255`、`engine/src/kernels/cuda/iq_kernels.cu:4578-4595`）。

環境変数の parse 結果は関数内 `static` に保存されるため、プロセス実行中に環境を変更しても反映されない。unset 時の CUDA device ごとの既定判定も `per_dev[64]` に保存される。該当する一括カーネルを起動した場合は `gs_done` が真になり、後段の通常 gate/up と SwiGLU/q8_1 pass を迂回する。条件を満たさない場合は `gs_done` が偽のまま通常経路へ進む（`engine/src/kernels/cuda/iq_kernels.cu:4584-4595,4613-4618,7248-7268,7306-7337`）。

## ログと測定値

- 変数を直接読む箇所に、ON/OFF 値を報告するログはない。
- sm_86 / sm_89 の起動時 default table が変数を追加した場合は、`strata: ... speed switches on by default ...` の stderr 行に設定されたスイッチ名が列挙される。行の正確な architecture 名や off switch 表記、注記は `engine/src/core/nv_defaults.cpp:241-255`。
- sm_120 混在 GPU 構成で `STRATA_SM120_PERF=0` が自動設定される場合の stderr は `strata: mixed-arch multi-GPU with sm_120: STRATA_SM120_PERF=0 (set STRATA_SM120_PERF=1 to override)`（`engine/src/program/generate.cpp:4463-4469`）。
- 融合 kernel launch 後の CUDA/HIP エラーは `native_expert_grouped/gu+swiglu: <runtime error>` の形で stderr に出て終了コード 1 で終了する（`engine/src/kernels/cuda/iq_kernels.cu:47-50,7255`）。
- `iq_kernels.cu` のコメントは、RTX PRO 5000 Blackwell、6 ペアで decode が story +0.6%、code +0.9%、8K +0.5%、各ケース 6/6 で同一 token と報告している。これはコメント中の記録であり、この調査で再測定した値ではない（`engine/src/kernels/cuda/iq_kernels.cu:4574-4577`）。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:4578-4595` — 環境変数の parse、未設定時の backend / compute capability 既定、cache。
- `engine/src/kernels/cuda/iq_kernels.cu:4601-4618,7241-7268,7306-7337` — 適用条件、融合 launch、通常経路への fallback。
- `engine/src/kernels/cuda/iq_kernels.cu:3118-3124` — 融合 kernel の計算説明。
- `engine/src/core/nv_defaults.cpp:41-58,75-89,222-255` — sm_86 / sm_89 の既定注入と観測可能なログ。
- `engine/src/program/generate.cpp:4425-4469` — 既定注入の呼び出し条件と mixed-arch の扱い。
- `engine/include/strata/core/sm120_series.hpp:60-81,89-101` — sm_120 / sm_121 未設定既定の共通ルールと GB10 の個別判定。
- `engine/cmake/strata_gpu_engine.cmake:98-108` — CUDA kernel source と HIP build の関係。
