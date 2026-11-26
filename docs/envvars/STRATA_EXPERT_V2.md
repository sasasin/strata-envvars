# `STRATA_EXPERT_V2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP の native grouped expert 計算で、条件に合う IQ3_S gate/up と IQ4_NL down の層を S26 カーネル群で処理する opt-in switch です。対象層では gate/up、SwiGLU と Q8_1 量子化、down の実装が `s26_gu_l_kernel`、`s26_swiglu_q8_1_kernel`、`s26_down_l_kernel` に切り替わります。切り替えに該当しない層・呼び出しは通常の grouped expert 経路へ進みます。通常の層選択やルーティングを変える CLI 引数は見つかりませんでした。[`engine/src/kernels/cuda/iq_kernels.cu:7121-7132`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [`engine/src/kernels/cuda/iq_kernels.cu:4113-4155`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

SYCL では対応する S26 kernel がビルドされず、この変数は切り替えに使われません。後述の条件で値が有効なら、SYCL の grouped expert 初回呼び出し時に無視する旨を stderr に出します。[`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7767-7790`](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

## 値と判定

CUDA/HIP の `native_expert_grouped` 内で `std::getenv` の結果について `v && v[0] == '1'` を判定します。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしません。従って `1`、`10`、`1anything` は有効で、未設定、空文字、`0`、`0anything`、`true`、` 1` は無効です。負値も先頭文字が `1` でなければ無効です。この bool は関数内 `static` に保存され、プロセス内で初回評価後に環境を書き換えても反映されません。[`engine/src/kernels/cuda/iq_kernels.cu:7121-7122`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

| 経路 | unset | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| CUDA/HIP grouped expert | 通常は無効。ただし後述の AMD 既定値注入対象では、起動時に `1` が設定されることがある | 先頭文字が `1`（例: `1`, `10`, `1abc`） | 空文字、`0`, `0abc`, `true`, ` 1` など |
| SYCL grouped expert | 無効 | 先頭文字が `1` の場合も機能は無効。警告条件に該当 | 上記以外は警告なし |

## 有効になる条件

CUDA/HIP で値が有効なだけでは切り替わりません。`native_expert_grouped` に渡された layout がすべて次を満たす場合だけ S26 経路を選びます。

- nibble 変換済み layout ではない（`!nib_layout(L)`）。
- `L.had_block == 0`、`L.tail_off == 0`。
- gate/up の型が `L.gu_type == 21`（IQ3_S）、down が `L.d_type == 20`（IQ4_NL）。
- `n_embd == 2560`、`n_ff == 640`。

条件を満たさなければ同関数の後続経路へ進みます。呼び出し元の Qwen3.5/3.6 engine は通常の MoE grouped 経路で `native_expert_grouped` を呼びます。[`engine/src/kernels/cuda/iq_kernels.cu:7121-7132`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [`engine/src/qwen35/q36_engine.cu:2997-3002`](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)

環境に値がない場合でも、HIP 起動時の `apply_arch_defaults` は対象 GPU で既定値を補い、利用者が設定済みの値は保持します。ソース上の対象は gfx1151（`STRATA_GFX1151_DEFAULTS` が `0` で始まる場合を除く）と discrete RDNA3 gfx1100/1101/1102（`STRATA_GFX11_DEFAULTS=0` 等でその既定値群が無効化される場合を除く）です。gfx1103 と gfx1150 は `terminal/setup.py` の設定表にも `STRATA_EXPERT_V2=1` が含まれます。gfx12 の `arch_default_env` にはこの変数は含まれません。[`engine/src/core/arch_defaults.cpp:64-89`](../../../../Niko1221/Strata/engine/src/core/arch_defaults.cpp) [`engine/include/strata/core/gfx11_extra.hpp:39-73`](../../../../Niko1221/Strata/engine/include/strata/core/gfx11_extra.hpp) [`engine/src/core/arch_defaults.cpp:302-323`](../../../../Niko1221/Strata/engine/src/core/arch_defaults.cpp) [`engine/src/program/generate.cpp:4287-4320`](../../../../Niko1221/Strata/engine/src/program/generate.cpp) [`terminal/setup.py:4472-4485`](../../../../Niko1221/Strata/terminal/setup.py)

`STRATA_TSUM` は S26 経路に入る条件ではありません。S26 経路内で先頭文字が `1` の場合に転置 butterfly の和を選び、それ以外では既存の SwiGLU と量子化を別 kernel で行います。`STRATA_EXPERT_NIBBLE` が有効な起動では `STRATA_EXPERT_V2` が衝突設定として扱われ、nibble 側の設定を無効にして続行する警告経路があります。[`engine/src/kernels/cuda/iq_kernels.cu:7122-7130`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [`engine/include/strata/core/expert_nibble.hpp:277-298`](../../../../Niko1221/Strata/engine/include/strata/core/expert_nibble.hpp) [`engine/src/program/generate.cpp:5474-5489`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)

## 実行時の詳細

CUDA/HIP の環境値は `native_expert_grouped` が最初に呼ばれ、該当する関数内 static が初期化される時に評価されます。エンジン起動時の AMD 既定値設定はこの初回読み取りより前に `apply_arch_defaults` を呼び、利用者値が存在すれば上書きせず、未設定時のみ `_putenv_s` / `setenv(..., 0)` で設定します。したがって既定値の対象 GPU では unset が実効的に有効となる一方、明示した空文字や `0` は保持されて無効になります。[`engine/src/program/generate.cpp:4287-4320`](../../../../Niko1221/Strata/engine/src/program/generate.cpp) [`engine/src/core/arch_defaults.cpp:218-223,302-323`](../../../../Niko1221/Strata/engine/src/core/arch_defaults.cpp)

S26 の呼び出しは gate/up kernel、SwiGLU と Q8_1 の処理、down kernel の順です。`STRATA_TSUM` が有効なら S26 の SwiGLU/量子化を一つの kernel にまとめ、無効なら二つに分けます。S26 の後は `check("native_expert_grouped (v2)")` を呼んで当該経路から戻ります。[`engine/src/kernels/cuda/iq_kernels.cu:4113-4155`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [`engine/src/kernels/cuda/iq_kernels.cu:7122-7132`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

SYCL では grouped expert 関数内の `static const bool v2_note` が初回到達時に一度評価されます。`STRATA_EXPERT_V2` または `STRATA_EXPERT_V2K` のいずれかが先頭文字 `1` なら、次の一行を stderr に出し、S26/S27 は使わず SYCL の既存経路を続けます。`cap_groups <= 0` または `cap_entries <= 0` なら関数が先に戻るため、この確認・警告にも到達しません。[`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7771-7790`](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

## ログと測定値

SYCL の警告文字列は `note: STRATA_EXPERT_V2 / STRATA_EXPERT_V2K are AMD-only experiments, ignored on SYCL` です。CUDA/HIP の S26 選択を示す専用の成功ログはこの分岐にありません。kernel 実行後に `check("native_expert_grouped (v2)")` が呼ばれます。[`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7782-7788`](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp) [`engine/src/kernels/cuda/iq_kernels.cu:7131-7132`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

ソースコメントは S26 の算術・出力について bitwise 一致を述べていますが、本調査では build・実行・測定を行っていません。`docs/STRIX_HALO.md` はこの変数を IQ3_S / IQ4_NL grouped decode expert 群の一つとして記載しており、対象機能の説明と整合します。同資料は本変数単独の測定値を示していないため、ここでは性能値を記載しません。[`engine/src/kernels/cuda/iq_kernels.cu:3808-3811`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [`docs/STRIX_HALO.md:115-117`](../../../../Niko1221/Strata/docs/STRIX_HALO.md)

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:7121-7132` — CUDA/HIP の値判定、S26 条件、追加 switch、選択後の戻り。
- `engine/src/kernels/cuda/iq_kernels.cu:4113-4155` — S26 の SwiGLU、量子化、kernel 呼び出し順。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7771-7790` — SYCL の読み取り・警告。
- `engine/src/core/arch_defaults.cpp:64-89,218-223,302-323`、`engine/include/strata/core/gfx11_extra.hpp:39-73`、`engine/src/program/generate.cpp:4287-4320` — HIP 起動時の AMD 既定値とユーザー値の保持。
- `terminal/setup.py:4472-4485` — gfx1103 / gfx1150 の setup switch 表。
- `engine/include/strata/core/expert_nibble.hpp:277-298`、`engine/src/program/generate.cpp:5474-5489` — nibble 設定との衝突時の扱い。
