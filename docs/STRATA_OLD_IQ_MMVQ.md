# `STRATA_OLD_IQ_MMVQ`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

IQ 系の行列ベクトル計算と grouped expert 計算で、重みを列ごとに読み直す旧カーネルを選びます。既定の新カーネルは、重みを一度 decode して複数列・複数 entry に適用します。CUDA 実装では対象形式に対する新カーネルが通常選ばれ、この変数を有効にすると旧カーネルへ戻ります。SYCL 実装では `STRATA_EXPERT_SPLIT=1` で新しい multi カーネルを選んだ場合に、この変数がその選択を抑止します。

実装は CUDA/HIP 系の `src/kernels/cuda/iq_kernels.cu` と SYCL 系の `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にあります。ヘッダーは両方の方式が bitwise 同じ結果になると説明していますが、この文書では性能差を一般化しません。

## 値と判定

両実装とも `env_on()` で環境値の先頭文字だけを判定します。文字列全体の parse、数値変換、大文字小文字の変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| 空でなく、先頭文字が `0` 以外 | 有効（例: `1`, `true`, `false`, `2`, 空白で始まる文字列） |

値が有効なら、対象の旧 per-column / lane カーネルを選択します。`false` は文字列として解釈されず、先頭文字が `f` なので有効です。

## 有効になる条件

- CUDA/HIP の IQ カーネルでは、`kSplit<T>` がある形式について新しい multi カーネルを選ぶ分岐に作用します。環境変数が有効なら、`STRATA_KQ_SPLIT` の状態に関係なく旧カーネルになります。`kSplit<T>` でない形式は元から旧カーネルを使うため、この変数による選択差はありません。
- CUDA/HIP では `STRATA_KQ_SPLIT` が K-quant、Q5_1、Q8_0 の一部形式を個別に旧経路へ戻せます。したがって `STRATA_OLD_IQ_MMVQ` が無効でも、これらは `STRATA_KQ_SPLIT` 次第で旧経路になります。
- SYCL では grouped expert の新 multi 経路に `STRATA_EXPERT_SPLIT` も必要です。`STRATA_OLD_IQ_MMVQ` が有効なら、`STRATA_EXPERT_SPLIT=1` でも旧 lane 経路になります。未設定時の SYCL は `STRATA_EXPERT_SPLIT` も無効なので、旧経路が選ばれます。
- CUDA の EXPDEC grouped expert kernel は、この変数が有効だと対象形式であっても使われません。`STRATA_EXPDEC` が有効でも `expdec_gu()` / `expdec_down()` は false を返し、呼び出し側が通常の経路を続けます。
- `STRATA_OLD_IQ_MMVQ` は CUDA grouped expert の SwiGLU fused 経路と、特定形状で使う狭い row 分割にも条件として参照されます。有効時にはこれらの経路を避けます。
- HIP は CUDA と同じ `.cu` ファイルに含まれますが、HIP GFX906 の grouped expert には独自の分岐があります。したがって、この変数を HIP 実行全体の一律な旧 kernel 強制スイッチとは扱えません。ここでは `g_old_kernels` を直接参照する経路について記述しています。

## 実行時の詳細

変数は CUDA/HIP と SYCL のカーネル翻訳単位にある namespace-scope `g_old_kernels` の初期化時に読み取られます。通常のエンジン実行では初期化後に環境を変更しても値は再読込されません。カーネル選択後に CUDA graph を capture した場合、ヘッダーの説明どおり、capture 済み graph は capture 時のカーネル選択を保持します。モジュールには `iq_set_old_kernels(bool)` API もあり、コードからフラグを上書きできます。

CUDA/HIP の `launch_mmvq` は対象形式でフラグが有効なら `mmvq_kernel` を起動し、無効なら multi-column kernel を起動します。grouped expert の gate/up と down も同様に、対象形式ではフラグが有効な場合に `native_gu_kernel` / `native_down_kernel` を選びます。SYCL の `launch_mmvq`、`launch_gu`、`launch_down` はフラグが有効なら lane kernel を選びます。環境変数自体にログ、標準出力、警告、エラー出力はありません。

## 根拠

- 判定と初期値: `src/kernels/cuda/iq_kernels.cu:3273-3279`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3205`。
- CUDA/HIP の multi-column 選択と K-quant 例外: `src/kernels/cuda/iq_kernels.cu:830-831,3374-3388,4154-4168`。
- CUDA grouped expert の gate/up、down、EXPDEC、fused/row 条件: `src/kernels/cuda/iq_kernels.cu:4030-4069,4073-4082,4130-4140,4154-4169,5121-5123,5156-5159,5232-5236`; HIP GFX906 分岐: `src/kernels/cuda/iq_kernels.cu:5124-5132,5684-5695`。
- SYCL の MMVQ / grouped expert 経路と setter: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3453-3475,4587-4605,4621-4640`。
- 旧・新 kernel の同値性と graph capture に関する API 注記: `include/strata/kernels/iq_kernels.hpp:121-130`。
- EXPDEC との相互作用の説明: `docs/EXPERTDEC.md:31-34`。
