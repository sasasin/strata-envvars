# `STRATA_PREFILL_NVFP4`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。作業ツリーは clean。Strata 所有ソースを対象とし、外部ライブラリ内部の動作は対象外。

## 役割

CUDA の batched prompt prefill で、NVFP4 量子化された MoE expert の gate/up・down 積に使う MMQ 精度を選びます。既定の `w4a8` は NVFP4 重みと Q8_1 活性値を使い、`w4a4` は重みと活性値の両方を NVFP4 にして Blackwell FP4 MMA を使います。`fp16` は NVFP4 重みを MMQ 対象から外し、FP16 の経路を使わせます。

この変数は通常の decode 精度を選ぶものではなく、NVFP4 以外の重み形式にも影響しません。設定は最初の NVFP4 mode 判定時に `static` 変数へ保存され、そのプロセス内では以後再読込されません。

## 値と判定

値は `strcmp` による文字列全体の完全一致で判定します。trim、大小文字変換、数値変換はありません。

| 値 | NVFP4 の MMQ 判定・活性値 |
|---|---|
| unset | `w4a8`。Q8_1 活性値を使う既定経路 |
| `w4a8` | `w4a8` |
| `w4a4` | W4A4 が実行可能なら FP4 活性値。実行できなければ警告して W4A8 に fallback |
| `fp16` | NVFP4 は `supported()` が false となり、MMQ を使わない |
| 空文字、`W4A8`、前後に空白がある値、`w4a4x2` など | `stderr` に `STRATA_PREFILL_NVFP4=<値>: expected w4a8, w4a4 or fp16` を出して `exit(1)` |

ただし値を読むのは NVFP4 type の判定時です。NVFP4 重みがない場合、また `STRATA_PREFILL_MMQ=0` で MMQ plan が NVFP4 type を検査しない場合は、この parser が呼ばれず、不正値でもこのエラーが出ない経路があります。MMQ plan 自体も初回評価後に cache されます。

根拠: `src/prefill/moe_mmq.cu:188-198,200-221`; `src/prefill/prefill.cpp:1012-1038`。

## 有効になる条件

- NVFP4 mode は CUDA MMQ にだけ実装されています。`GGML_USE_HIP` では `supported()` の NVFP4 case と NVFP4 の dispatch が compile-time で除外され、`fp4_activations()` も常に false を返します。
- MMQ は build に含まれ、prefill が MMQ を選ぶ必要があります。`STRATA_PREFILL_MMQ=0` は MMQ plan を無効化し、既定では環境変数 unset の場合に有効です。MMQ が使われない経路ではこの設定は prefill の積の選択に作用しません。
- `fp16` を選ぶと NVFP4 type は MMQ 非対応になります。資料ではこの mode を dequantize + cuBLAS FP16 GEMM と説明しています。実際の layer ごとの最終経路は他の prefill 条件にも依存します。
- `w4a4` は実行時 probe が成功した場合に限り選ばれます。CMake は W4A4 専用 unit を CUDA architectures の 12x 対象から `12xa` に変換して build します。device code を実行できない GPU/build の組み合わせでは W4A8 に fallback します。W4A8 は通常の MMQ unit で動き、W4A4 と同じ arch-specific unit を必要としません。

根拠: `src/prefill/moe_mmq.cu:200-221,281-294`; `src/prefill/prefill.cpp:1012-1035`; `CMakeLists.txt:1442-1457`; `src/prefill/mmq_nvfp4_w4a4.cu:22-46`。

## 実行時の詳細

`mmq_plan()` が layer の weight type を調べると `mmq::fits()` から `supported()` が呼ばれ、NVFP4 type の場合に mode が決まります。`FP16` mode では `supported()` が false を返すため、その type は MMQ layer として plan されません。`W4A8` / `W4A4` は他の MMQ 対応条件（全 visible GPU に適合する tile があること等）を満たせば MMQ 対象になります。tile 条件を満たさない場合は既存の別経路に回ります。

`W4A4` が選ばれた場合、初回の `fp4_activations()` で `w4a4_available()` を一度 probe します。probe は device buffer を確保して W4A4 unit の kernel を起動し、その結果を host に読み戻します。失敗時は `prefill mmq: STRATA_PREFILL_NVFP4=w4a4 needs an sm_12x card in a 12x build; W4A8` を stderr に出し、false を cache します。続く quantize と積の dispatch は Q8_1 活性値および W4A8 kernel を使います。成功時は NVFP4 活性値を量子化し、W4A4 kernel に dispatch します。gate/up の積、SwiGLU、down の積それぞれに同じ mode 判定が使われます。

同梱診断ツール `mmq_expert_bench` と `mmq_nvfp4_parity` も環境値を表示し、`fp4_activations()` を通じて同じ mode/probe を使います。parity tool の `--group`、`--real`、`--layers` 分岐は mode 表示より前に return するため、それらの分岐では直接の mode 表示・評価を行いません。

根拠: `src/prefill/prefill.cpp:1012-1038,3873-3929`; `src/prefill/moe_mmq.cu:281-325,373-377`; `src/prefill/mmq_nvfp4_w4a4.cu:34-52`; `src/prefill/mmq_expert_bench.cpp:108-115`; `src/prefill/mmq_nvfp4_parity.cpp:328-345`。

## 文書との照合

`docs/NVFP4.md:127-155` は `w4a8`、`w4a4`、`fp16` と既定値、適用経路を記述しています。同節の測定では、8 prompts（code/prose、1K–8K tokens）の first-token KL mean が W4A8 0.0018、W4A4 0.0080、FP16 基準で、4–8K prompt prefill がそれぞれ 2,503、2,904、1,905 tok/s と記されています。資料記載の測定値であり、ここで再測定した結果ではありません。

同じ `docs/NVFP4.md:99-103` には `STRATA_PREFILL_NVFP4=w4a4x2` の測定記述がありますが、調査対象 HEAD の parser は `w4a4x2` を受け付けず、上記エラーで終了します。この説明は現行ソースと一致しません。
