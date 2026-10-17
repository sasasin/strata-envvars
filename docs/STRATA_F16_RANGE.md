# `STRATA_F16_RANGE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの内部動作は対象外。

## 役割

HIP の prompt prefill で FP16 に変換される activation と BF16 weight、および FP16 GEMM から戻る出力について、最大絶対値と FP16 の有限範囲を超えた値・NaN の個数を数え、prompt ごとに stderr へ出します。これは診断用カウンターであり、計算方式や値を切り替える設定ではありません。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_F16_RANGE") != nullptr` だけで設定有無を判定します。unset は無効、設定済みなら値が空文字でも `0`、`false`、その他どの文字列でも有効です。数値変換、範囲検査、CLI や別変数との優先順位はありません。実装上、初期化時と出力時にそれぞれ関数内 `static const bool` へ結果を保存するため、各箇所の最初の評価後は環境を変更しても再評価されません。

## 有効になる条件

- 実カウンターと読み出し処理は HIP ビルドでのみ実装されています。CUDA では設定有無を読んで有効化関数を呼びますが、それらは no-op で、読み出し関数は `false` を返すため範囲ログは出ません。
- HIP でも prompt prefill の初期化と完了処理が通る必要があります。調査時点のコードではこの設定による集計処理は gfx103x の FP16 経路だけには限定されておらず、HIP の FP16 活性値変換箇所および FP16 GEMM が使う対象箇所を数えます。FP16 入出力 GEMM の選択自体は別設定 `STRATA_HIP_PROMPT_F16` が制御します。
- prompt が複数の prefill stage/device に分かれる場合、カウンターは GPU device symbol に保持されます。コードの集計ログには device ID が含まれません。

## 実行時の詳細

初期化時に `set_f16_range(true)` と `gemm_set_f16_range(true)` が HIP device symbol の計測 flag を設定します。activation 側では `hf_sat` に入る値の絶対値最大と、`abs(value) > 65504` または NaN の件数を数えます。これは変換後の値ではなく、飽和変換に入る前の値です。GEMM 側では BF16 weight を FP16 に変換する入力値（slot 0）と、rocBLAS が FP16 で書いた出力を FP32 に widen する際の値（slot 1）を数えます。最大値は浮動小数点値の bit 表現による atomic max、超過数は atomic count です。

prompt 完了後、CUDA stream 同期などの後処理を経て両カウンターを読み出し、成功時に次の形式で stderr に出します: `strata f16 range: <tokens> tokens: activation images max |x| ... (... beyond 65504 or NaN), BF16 weights max |w| ... (...), FP16 GEMM outputs max |y| ... (... not finite)`。この集計では weight と activation の超過数は 65504 超または NaN、GEMM output の超過数は非有限値の件数として表示されます。読み出し後に最大値と件数はゼロへ戻されます。符号付きの有限値は absolute value で測定されます。

設定時の flag を device symbol に書けない場合は stderr に `prefill: setting the FP16 range check failed: ...` または `prefill gemm: setting the FP16 range check failed: ...` を出し、`exit(1)` します。読み出し copy に失敗した場合、その読み出し関数は `false` を返し、上記の範囲ログは出ません。

## 文書との照合

`docs/AMD_HIP.md` はこの設定を prompt ごとの FP16 範囲診断として説明しており、コードの HIP 限定カウンターと整合します。同文書の性能値は特定の AMD 機、ROCm、モデル・量子化・prompt 条件での測定であり、この環境変数による性能効果を示すものではありません。本調査では新たな測定をしていません。

## 根拠

- `src/prefill/prefill.cpp:1382-1390` — prefill stage 初期化、FP16 activation mode 設定と環境変数の読み取り。
- `src/prefill/prefill.cpp:4718-4726` — prompt 完了時の読み出し、stderr の実際の文言。
- `src/prefill/kernels.cu:44-67,80-85,2318-2355` — activation 計測、HIP/CUDA 分岐、読み出しと reset。
- `src/prefill/gemm.cu:63-131` — weight/output の HIP 計測と読み出し、CUDA no-op。
- `include/strata/prefill/kernels.hpp:43-49`, `include/strata/prefill/gemm.hpp:15-19` — カウンター API の説明と対応範囲。
- `docs/AMD_HIP.md:523-534` — HIP FP16 prompt 経路と診断に関する資料。
