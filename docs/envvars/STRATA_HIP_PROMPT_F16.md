# `STRATA_HIP_PROMPT_F16`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

HIP の prefill で、BF16 重みを使う 16-bit GEMM の入出力を FP16 にするかを選ぶ。対象 stage の活性値イメージを BF16 から FP16 にし、GEMM の結果も FP16 で書いて同じ出力行内で FP32 に widen する。通常経路と bit-identical ではなく、decode の GEMM 設定を変えるスイッチではない。HIP 以外では有効にならない。`src/prefill/gemm.cu` の `prompt_f16()` が選択し、`src/prefill/prefill.cpp` の stage 初期化がその値を `Gemm` と活性値 writer に渡す（`src/prefill/gemm.cu:605-635`, `src/prefill/prefill.cpp:2613-2618`, `src/prefill/kernels.cu:84-90,2843-2853`）。

## 値と判定

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 通常の HIP 実装 (`src/prefill/gemm.cu`) | gfx1103 の統合 Radeon 780M、Linux のみ on。それ以外 off | 最初の文字が `1`。例: `1`, `10`, `1anything` | 設定済みで最初の文字が `1` 以外。例: 空文字、`0`, `true`, ` 1`, `2`, `0anything` |
| `sycl/src/prefill/gemm.dp.cpp` の HIP compile path | off | 最初の文字が `1`。例: `1`, `10`, `1anything` | unset または最初の文字が `1` 以外 |
| CUDA / Metal など HIP 以外 | off（この変数を読む有効経路なし） | なし | すべて |

両 HIP 実装とも `getenv` の戻り値を確認し、値全体を parse せず `e[0] == '1'` で判定する。したがって空文字は「設定あり・off」、空白や大文字小文字を含む `true` は off、後続文字は無視される。数値範囲・符号の検査や無効値警告はない。通常の HIP 実装は `prompt_f16_resolve()` に渡し、unset の場合だけ device arch・統合 GPU 判定・Windows 判定で既定値を決める（`src/prefill/gemm.cu:615-623`, `include/strata/core/arch_defaults.hpp:79-85`）。SYCL ツリー側は unset で false とする（`sycl/src/prefill/gemm.dp.cpp:359-380`）。

## 有効になる条件

- HIP compiler 経路であること。通常の `src/prefill/gemm.cu` と `src/prefill/kernels.cu` は `__HIPCC__` 条件でこの処理を行い、CUDA では FP16 活性値 writer は no-op、`prompt_f16()` は false を返す（`src/prefill/gemm.cu:605-635`, `src/prefill/kernels.cu:84-90,2843-2853`）。
- 明示値が unset の場合、通常 HIP 実装では device 情報が Radeon 780M の gfx1103、統合 GPU、Linux と判定されること。この条件以外のカードや Windows は既定 off。HIP device / properties の取得に失敗した場合も false 側になる（`src/prefill/gemm.cu:610-623`, `include/strata/core/arch_defaults.hpp:82-85`）。
- 値が `1` で始まる場合は通常 HIP 実装ではカードや OS を問わず on。SYCL ツリーの HIP compile path も `__HIPCC__` のときだけ判定し、カード情報による既定 on は持たない（`src/prefill/gemm.cu:605-623`, `sycl/src/prefill/gemm.dp.cpp:359-380`）。
- Prompt stage の初期化で決まる。通常 HIP 実装は stage の device を current にしてから値を確認する（`src/prefill/prefill.cpp:2613-2618`）。同じ値は必要バッファ量の計算でも参照される（`src/prefill/prefill.cpp:3563-3576`）。
- `STRATA_PREFILL_BF16X2` の BF16 low-part GEMM は `f16_io` が on のとき無効扱いになる。`STRATA_XN_F16` は `!f16_io` のときだけ `xn_f16` に影響するため、この FP16 経路を上書きしない（`src/prefill/prefill.cpp:842-849,2616-2624`）。

## 実行時の詳細

通常 HIP 実装は `prompt_f16()` 内に device ごとの `static std::atomic<int8_t>` cache を持つ。最初の問い合わせで環境変数と device 情報から決めた on/off を格納し、以降その device では cache を返すため、プロセス実行中に環境値を変えても再評価されない。device index が 0–63 外、または `hipGetDevice` が失敗した場合は off を返す。`hipGetDeviceProperties` の失敗も arch 名と統合属性を空/false にして既定判定を off にする（`src/prefill/gemm.cu:605-635`）。SYCL ツリーの HIP compile path も同様に device ごとに cache する（`sycl/src/prefill/gemm.dp.cpp:359-384`）。

stage 初期化は `prompt_f16()` の結果を `m.f16_io` と `Gemm::set_f16_io()` に保存し、`set_act_f16()` で HIP device symbol `g_act_f16` を設定する。設定に失敗すると `prefill: setting the FP16 activation image failed: ...` を stderr に出して終了コード 1 で終了する（`src/prefill/prefill.cpp:2613-2618`, `src/prefill/kernels.cu:84-90,2843-2853`）。

on のとき活性値 writer の `act16()` は FP32 値を飽和付き FP16 に変換し、16-bit GEMM は `f16_io_` かつ `beta == 0` の呼び出しで FP16 入出力 GEMM に分岐する。BF16 重みは scratch に FP16 変換してから実行し、出力は FP16 で書いた後 widen する。通常の FP16 GEMM では rocBLAS の形状別 solution が使えればそれを使い、そうでなければ HIP GEMM に fallback する（`src/prefill/kernels.cu:84-90`, `src/prefill/gemm.cu:1081-1093,1209-1218,1351-1363`）。この経路の FP16 丸めにより prompt の中間値・結果は既定経路と bit-identical ではない（`src/prefill/gemm.cu:612-615,624-626`）。

FP16 経路で BF16 の low-part 累積 GEMM（`beta != 0`）に入ると `prefill gemm: an accumulating BF16 GEMM on the FP16 prompt path` を stderr に出して `exit(1)` する。FP16 GEMM scratch が不足する場合は `prefill gemm: scratch too small for K=...` を出して `exit(1)` する（`src/prefill/gemm.cu:1081-1087`）。

## ログと測定値

- 明示値が有効で on の場合、通常 HIP 実装は device ごとに `strata prefill: HIP device <n> <arch> - STRATA_HIP_PROMPT_F16=1: the prompt's 16-bit GEMMs run FP16 in and out (rocBLAS is tuned only for that on gfx103x; not bit-identical to the default)` を stderr に出す。`STRATA_HIP_PROMPT_F16` が unset で gfx103x の場合は、約 2 倍速いという tip を stderr に出す。既定値のまま on になる gfx1103 は後者の gfx103x tip の対象ではない（`src/prefill/gemm.cu:624-630`）。
- Strata の `docs/AMD_HIP.md:506-513` は gfx1030 の rocBLAS が FP16-in/FP16-out GEMM 向けに tuned kernels を持つと記し、gfx1030/103x の経路選択の説明をしている。同資料は Radeon 780M (gfx1103), Q2_0 の prompt で 300 / 1,000 / 2,048 / 8,192 tokens に対して x1.11 / x1.15 / x1.19 / x1.25 を記載し、Radeon AI PRO R9700 (gfx1201) の dense GEMM は x0.70–x0.72 と記載する。これらは資料中の測定結果であり、今回再測定していない。
- `STRATA_DBG_NAN` が設定されている場合、FP16 GEMM 後に非有限値があれば `strata prefill: STRATA_DBG_NAN: ... non-finite FP16 GEMM outputs (...; FP16 ends at 65504)` を stderr に出す。ただしこれは別の診断変数であり、この変数自体はその検査を有効にしない（`src/prefill/gemm.cu:1364-1373`）。

## 根拠

- `src/prefill/gemm.cu:605-635` — HIP 条件、device ごとの cache、環境値・device 既定値の判定、ログ。
- `include/strata/core/arch_defaults.hpp:79-85` — unset 時の gfx1103 統合 Radeon 780M/Linux 既定値と override 判定。
- `src/prefill/prefill.cpp:2613-2624,3563-3576` — stage 初期化、環境の値の反映、関連する BF16 buffer 判定。
- `src/prefill/kernels.cu:84-90,2843-2853` — FP16 活性値変換と device symbol 設定、設定失敗時の終了。
- `src/prefill/gemm.cu:1081-1093,1209-1218,1351-1373` — GEMM の FP16 分岐、fallback、失敗と診断経路。
- `sycl/src/prefill/gemm.dp.cpp:359-384` — SYCL ツリーの HIP compile path における明示 opt-in と cache。
- `docs/AMD_HIP.md:506-513` — Strata 資料に記載された HIP 経路の測定値。
