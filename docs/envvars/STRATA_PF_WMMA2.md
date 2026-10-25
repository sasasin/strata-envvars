# `STRATA_PF_WMMA2`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA の grouped prefill expert GEMM で、IQ2_S の gate/up と IQ4_NL の down に、別実装の FP16 WMMA カーネルを選べるようにします。環境変数だけで単独に経路を有効化するものではありません。呼び出し側の `STRATA_PF_WMMA` による FP16 grouped-WMMA 経路が選ばれた後、型・形状・配置が合う GEMM ごとにこのカーネルを選びます。条件に合わない GEMM は既存の grouped-WMMA 実装へ進みます。

## 値と判定

`src/kernels/cuda/iq_kernels.cu:5617-5619` で `std::getenv("STRATA_PF_WMMA2")` を読み、値が設定され、先頭文字が `'1'` のときだけ有効とします。文字列全体や数値としての妥当性は調べません。

| 値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| `1`, `10`, `1anything` | 有効（先頭文字が `1`） |
| `0`, `true`, ` 1` など | 無効 |

この判定は関数内の `static const bool` に保存されます。初回に `w2_on()` が呼ばれた後の環境変更は再評価されません。`w2_on()` は `gemm_iq_f16_grouped()` の基本引数チェックと現在 GPU の compute capability チェックを通過した後に参照されます。

## 有効になる条件

呼び出し側では、MMQ が使われ、`pf_wmma()` が有効で、fused layer ではなく、peer 経路がなく、native expert pack で、down 型が Q2_0 または IQ4_NL、さらに gate/up の行サイズを計算できる layer に限って grouped-WMMA 経路へ入ります。`pf_wmma()` は別変数 `STRATA_PF_WMMA` の先頭文字が `1` であることと、見えているすべての CUDA GPU の compute capability major が 7 以上であることを要求します。したがって `STRATA_PF_WMMA2=1` だけではこの呼び出し経路は開始されません。根拠: `src/prefill/prefill.cpp:1153-1169,4016-4022`。

その後 `gemm_iq_f16_grouped()` は、現在 GPU の major が 7 以上であることを確認します。WMMA2 カーネルを選ぶには、さらに次の条件をすべて満たす必要があります (`src/kernels/cuda/iq_kernels.cu:5623-5645`)。

- WMMA2 の環境判定が有効。
- 出力行数 `n_out` が128の倍数、`ldx` と `ldy` が8の倍数。
- X のアドレスが16バイト、Y が32バイト、W と expert stride が4バイト境界。
- IQ2_S (`ty == 22`) なら K が512の倍数、IQ4_NL (`ty == 20`) なら K が128の倍数。
- IQ row byte 数が4の倍数で、`n_experts * ceil(max_rows / 64) <= 65535`。

このうち一つでも満たさなければ WMMA2 専用カーネルは起動せず、通常の grouped-WMMA 経路の型・K チェックとカーネル選択に続きます。HIP ではこの CUDA 実装の環境判定は使われず、非 CUDA コンパイル側の `gemm_iq_f16_grouped()` は `false` を返します (`src/kernels/cuda/iq_kernels.cu:5678-5683`)。

## 実行時の詳細

条件を満たした場合、IQ2_S または IQ4_NL 用 `gemm_iq_f16_w2_kernel` を CUDA stream 上で起動し、起動直後の `cudaGetLastError() == cudaSuccess` を成功として返します。実装は W の量子化重みをブロック内で FP16 に展開し、FP16 入力との WMMA 積を FP32 accumulator に加算します (`src/kernels/cuda/iq_kernels.cu:5418-5424,5502-5615,5635-5644`)。

prefill 呼び出し側は gate/up と down の両方について戻り値を確認します。いずれかが失敗すると prefill を止め、`prefill: the WMMA expert tiles could not launch` をエラーとして返します (`src/prefill/prefill.cpp:4556-4569`)。WMMA2 の形状条件に合わない場合に通常経路へ進むことと、選択したカーネルの起動失敗でエラーになることは別です。

## 文書との照合

`docs/NVIDIA_V100.md:93-101` は `STRATA_PF_WMMA2=1` を opt-in の二つ目の prompt-expert kernel と記載し、IQ2_S gate/up と IQ4_NL down を対象に挙げています。+2.5〜4.3% の prompt speed という数値は同資料が contributor の V100 測定として示す値で、今回のソース調査で再測定・独立検証した値ではありません。ソース上も既定 OFF であり、対象型と呼び出し条件に限って選択されます。

## 根拠

- 値の読み取りとキャッシュ: `src/kernels/cuda/iq_kernels.cu:5617-5619`
- WMMA2 用 kernel dispatch、形状条件、通常経路への継続: `src/kernels/cuda/iq_kernels.cu:5623-5675`
- 非 CUDA 実装: `src/kernels/cuda/iq_kernels.cu:5678-5683`
- `STRATA_PF_WMMA` と visible GPU 条件: `src/prefill/prefill.cpp:1153-1169`
- grouped-WMMA 呼び出し条件と呼び出し元: `src/prefill/prefill.cpp:4016-4022,4556-4569`
- 既存資料の説明と測定値: `docs/NVIDIA_V100.md:93-101`
