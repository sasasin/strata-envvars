# `STRATA_HIP_PROMPT_F16`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバー（rocBLAS 自体）の動作は対象外。

## 役割

HIP ビルド専用の opt-in。prompt 経路の 16-bit GEMM を FP16 in / FP16 out で実行するか、既定（off）の path を保つかを決める。gfx103x（RDNA2）では rocBLAS の tuned kernel が FP16-in/FP16-out しかなく、FP16-in/FP32-out や BF16 積は generic kernel で約 6.6 倍遅い（資料記載）。このスイッチは出力ビットを変え（各 GEMM 出力の FP16 丸めが BF16 丸めを置き換える）ため、頼まれない限りどのカードでも off。

読み取りは `src/prefill/gemm.cu` の `prompt_f16()` 1 箇所（SYCL に同一ロジックのミラー `sycl/src/prefill/gemm.dp.cpp:364`）。結果は `Prefill::init` が stage のデバイスごとに一度確定し、`Gemm::set_f16_io` と `set_act_f16` へ渡す（`src/prefill/prefill.cpp:1188-1190`）。

## 値と判定

`std::getenv` の結果の**先頭文字 `e[0]` だけ**を `'1'` と比較する。

| 状態 | 判定 |
|---|---|
| 未設定（`nullptr`） | off（既定）。gfx103x では tip を 1 回表示 |
| 空文字 `""` | off（`e[0]` は `\0`）。tip は出さない（設定済み） |
| 先頭文字が `1`（`1`, `10`, `1anything`） | on |
| それ以外（`0`, `true`, `false`, `2` など） | off |

docs の「`STRATA_HIP_PROMPT_F16=0/1` overrides」は、`0` は off（既定と同じ）、`1` は on という意味。実装は `0` を特別扱いせず、先頭文字が `1` でなければ off。tip は「未設定かつ gfx103x」のときだけ（`e == nullptr` の条件）。

根拠: `src/prefill/gemm.cu:359-360`（判定）、`366`（tip 条件）。

## 評価時期とキャッシュ

`prompt_f16()` はデバイスごとに `static std::atomic<int8_t> cached[64]`（0 unknown, 1 off, 2 on）を持つ。あるデバイスの初回呼び出しで環境を読み、以後はそのデバイスではキャッシュ値を返す。プロセス起動後の環境変更は、初回評価済みデバイスでは反映されない。layer split で複数カードを混ぜる場合、各デバイスが自分の判定を持つ（`include/strata/prefill/gemm.hpp:94`）。

## 実際の挙動

on のとき、`Prefill::init`（stage の自 device 上で実行）が `m.f16_io = prompt_f16()` を設定し、`gemm.set_f16_io(true)` と `set_act_f16(true)` を呼ぶ（`src/prefill/prefill.cpp:1188-1190`）。これにより prompt path の 16-bit GEMM が FP16 in/out で走る（`Gemm::bf16()`/`f16()`/`native()` が FP16 out、Y の行内で widened）。off（既定）は「以前と同じ呼び出し」。

### bf16x2 との相互作用

`bf16x2_mode(f16_io)` は `f16_io` が true のとき 0 を返す（`src/prefill/prefill.cpp:307-312`）。FP16 activation は 11 mantissa bit を持つので BF16 の low part が適用されない。したがって on は、その stage で `STRATA_PREFILL_BF16X2` を実質 off にする（別変数の値があっても bf16x2 経路は使われない）。

## 観測できる出力

- on 時（初回評価、stderr）:
  `strata prefill: HIP device <d> <arch> - STRATA_HIP_PROMPT_F16=1: the prompt's 16-bit GEMMs run FP16 in and out (rocBLAS is tuned only for that on gfx103x; not bit-identical to the default)`（`src/prefill/gemm.cu:363-365`）。
- 未設定かつ gfx103x 時（tip、stderr）:
  `strata prefill: HIP device <d> <arch> - tip: STRATA_HIP_PROMPT_F16=1 reads long prompts about 2x faster here (FP16 prompt GEMMs, rocBLAS is tuned only for FP16 on gfx103x; the numbers differ slightly, see docs/AMD_HIP.md)`（`src/prefill/gemm.cu:366-369`）。

## 測定値（資料に記載）

`docs/AMD_HIP.md:430-432`（資料中の主張。本調査で計測器動作を独自確認した事実ではない）: gfx1030 の rocBLAS は FP16-in/FP16-out だけ tuned。FP16-in/FP32-out と BF16 積は generic kernel で約 6.6x 遅い（5.6・約5.3 TFLOPS 対 37.7、N=10240, T=7313, K=2560）。on で「about 2x faster」。bit-identical ではない。第 2 コミュニティ機（2x RX 6900 XT 16 GB、Ryzen 5 5600X、Ubuntu 26.04、ROCm 10.0.0、engine 0.1.39、`-DSTRATA_PREFILL_MMQ=ON`、GSQ-RCO IQ3_S）の測定は `docs/AMD_HIP.md:436-437` と `bench/results/2026-10-04-rdna2-fp16-prompt` を参照。

## 根拠

- 読み取り・判定・tip: `src/prefill/gemm.cu:350-375`。
- per-device キャッシュ: `src/prefill/gemm.cu:353-356`。
- init での適用: `src/prefill/prefill.cpp:1188-1190`。
- bf16x2 への影響: `src/prefill/prefill.cpp:307-312`。
- SYCL ミラー: `sycl/src/prefill/gemm.dp.cpp:364-374`、`sycl/src/prefill/prefill.cpp:657`。
- docs 照合: `docs/AMD_HIP.md:430-437`、`include/strata/prefill/gemm.hpp:50-53,92-94`。テスト（`tests/hip/gemm_f16_io_parity.cpp`）は実装根拠にしていない。
