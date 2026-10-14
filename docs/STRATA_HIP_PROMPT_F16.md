# `STRATA_HIP_PROMPT_F16`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の prompt prefill で使う 16-bit GEMM の入出力を FP16 に切り替える opt-in 設定です。通常の経路では BF16 activation / BF16 GEMM の出力を FP32 に変換します。有効時は、BF16-weight GEMM の activation image と GEMM の出力を FP16 にし、出力を FP32 の行列へ widen します。これにより丸め経路が変わり、既定経路と bit-identical ではありません。

判定は `prompt_f16()` が行い、その結果を各 prefill stage の `Gemm` と activation 変換 kernel に渡します。stage の GPU ごとに判定結果をキャッシュします。

## 値と判定

文字列全体や数値としての妥当性は検査せず、環境変数の先頭文字だけを見ます。

| 状態 | HIP での判定 |
|---|---|
| 未設定 | 無効。gfx103x では有効化を案内する stderr の tip を出す |
| 空文字 | 無効。変数は設定済みなので tip は出さない |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` など |
| その他の文字列 | 無効。`0`, `true`, ` 1` など |

大文字小文字、空白の trim、後続文字は判定に使いません。HIP 以外では `prompt_f16()` は常に false を返し、環境変数を読みません。

根拠: `src/prefill/gemm.cu:350-375`、対応する SYCL 側実装 `sycl/src/prefill/gemm.dp.cpp:357-382`。

## 有効になる条件

- HIP コンパイル (`__HIPCC__`) であること。CUDA build では有効になりません。
- prefill stage の初期化・バッファ見積もりが、その stage の GPU を current にして `prompt_f16()` を呼ぶこと。無効な device 番号、または `hipGetDevice()` の失敗時は false です。
- GEMM の対象が prompt prefill 内の対応する 16-bit 経路であること。decode の精度や出力はこの設定では変わりません。

gfx103x 専用の判定ではありません。gfx103x で未設定の場合は案内ログを出しますが、明示的に先頭文字 `1` を設定すると関数の判定上はどの HIP device でも有効になります。

## 実行時の詳細

`prompt_f16()` は `cached[64]` に device index ごとの結果を atomic に保存します。各 device について最初の呼び出しでだけ環境変数を読み、以後は保存値を返すため、プロセス実行中に環境を書き換えても、その device の判定は変わりません。layer split では各 stage の device を current にして判定します。環境変数を読む子プロセス処理はありません。

有効時、`Prefill::init` は結果を `m.f16_io` と `Gemm::set_f16_io()` に設定し、`set_act_f16()` で当該 device の activation kernel 用フラグも設定します。HIP kernel は BF16 ではなく飽和付き FP16 で activation image を書きます。`Gemm::bf16()` は FP16 image と FP16 に変換した weight を使う GEMM に切り替えます。`Gemm::f16()` は `beta == 0` の場合に FP16 出力 GEMM を使い、結果を FP32 の行へ widen します。`bf16x2_mode()` は `f16_io` が true の場合に 0 を返すため、BF16 low-part を加算する経路も使いません。

値が有効と判定されたときは stderr に `STRATA_HIP_PROMPT_F16=1: the prompt's 16-bit GEMMs run FP16 in and out ... (not bit-identical to the default)` を含む device ごとのログが出ます。未設定で architecture 名が `gfx103` から始まる場合は、`tip: STRATA_HIP_PROMPT_F16=1 reads long prompts about 2x faster here ...` の案内が出ます。`hipGetDeviceProperties()` が失敗すると architecture 名は空になりますが、環境値による on/off 判定は維持されます。

## 文書記載の測定

`docs/AMD_HIP.md:438-446` は、gfx1030 の rocBLAS で FP16-in / FP16-out GEMM に調整済み kernel があるとして、本設定を説明しています。同文書の記載では、2x RX 6900 XT のうち1枚、Ryzen 5 5600X、128 GB RAM、Ubuntu 26.04、ROCm 10.0.0、engine 0.1.39 を手動ビルド（`-DSTRATA_PREFILL_MMQ=ON`）し、GSQ-RCO IQ3_S の prompt で、9.4K / 34.7K / 105.8K token が 744 / 915 / 926 tok/s（既定経路では 439 / 466 / 461 tok/s）だったとしています。これは文書記載の特定環境・旧 engine の測定値で、現 HEAD の性能保証ではありません。同節は出力が既定経路と bit-identical でないことも明記しています。

## 根拠

- 判定、device ごとの cache、tip / 有効ログ: `src/prefill/gemm.cu:350-375`。
- stage ごとの設定と device 切替: `src/prefill/prefill.cpp:1215-1225`、容量見積もり側の呼び出し `src/prefill/prefill.cpp:1905-1907`。
- HIP activation 格納形式の切替: `src/prefill/kernels.cu:49-55,1818-1828`。
- BF16 GEMM の FP16 経路、beta 制約と weight 変換: `src/prefill/gemm.cu:624-651`。
- FP16 GEMM と FP32 出力への widen: `src/prefill/gemm.cu:728-745,878-899`。
- f16 mode で BF16 low-part を無効にする処理: `src/prefill/prefill.cpp:321-330`。
- 対応する port 実装: `sycl/src/prefill/gemm.dp.cpp:357-382`、`sycl/src/prefill/prefill.cpp:1119-1125`。
- 性能・丸めの説明: `docs/AMD_HIP.md:438-446`。
