# `STRATA_OLD_IQ_MMVQ`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

IQ 量子化形式の行列・expert 計算で、旧来の per-column カーネルを選びます。通常の新経路は、重みの各部分を一度 decode して複数列または複数 entry に適用します。旧経路では列ごとに重みを decode します。対象は CUDA/HIP の `iq_kernels.cu` と SYCL 移植版 `iq_kernels.dp.cpp` に実装された IQ カーネルです。ヘッダーの説明では両経路の結果は bitwise 同一とされています。これは実装文書の記述であり、この調査で実行比較した結果ではありません。

## 値と判定

両実装とも共通の `env_on()` で判定します。環境変数が未設定、空文字、または先頭文字が `0` なら無効です。それ以外は有効です。文字列全体の parse、数値変換、大文字小文字の変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（新経路を既定選択） |
| 空文字 | 無効 |
| `0` / `0anything` | 無効 |
| `1`, `true`, `false`, `2`, `anything` | 有効（先頭文字が `0` 以外で空でない） |

グローバル変数 `g_old_kernels` の初期化時に値を読みます。通常はプロセス内で一度の初期化であり、実行中の環境変更は自動では反映されません。`iq_set_old_kernels(bool)` による明示的な上書き API はありますが、ソース上の呼び出しは `iq_multi_parity` 等の parity 用プログラム内です。通常のモデル実行経路からの呼び出しは見つかりませんでした。グラフ capture 後は capture 済みのカーネルが残るとヘッダーに記されています。

## 有効になる条件

- `iq_mmvq` では `kSplit<TY>` が真の形式だけ、設定値による旧/新の分岐に入ります。split でない形式は、この変数にかかわらず同じ `mmvq_kernel` を使います。
- CUDA/HIP の `native_expert_grouped` では通常の split 形式 gate/up と down の dispatch が旧カーネルを選ぶ条件に使います。ただし、`STRATA_EXPERT_V2` / `STRATA_EXPERT_V2K` 専用条件や `STRATA_EXP_LAYOUTS` の fused / LDS / AMD layout 経路は通常 dispatch を通らず、これらの経路をこの変数が切り替えることはありません。
- CUDA/HIP 側は `STRATA_OLD_IQ_MMVQ` が無効のとき、対象寸法・形式に応じて gate/up の行数や down の行数も変える経路があります。有効にするとこの行数選択は従来の値に戻ります。
- SYCL 側の grouped expert は `STRATA_EXPERT_SPLIT` も参照します。split 形式では `STRATA_OLD_IQ_MMVQ` が有効、または `STRATA_EXPERT_SPLIT` が無効なら lane 経路を使い、両方が有効な場合に multi-entry 経路を使います。従って SYCL では、この変数だけで multi-entry 経路を有効化することはありません。

## 実行時の詳細

`iq_mmvq` の split 形式では、CUDA/HIP は `g_old_kernels` が真なら `mmvq_kernel`、偽なら `mmvq_multi_kernel` 系を launch します。SYCL 版も同じように、真なら `mmvq_kernel`、偽なら `mmvq_multi_nc` 系へ進みます。

grouped expert の CUDA/HIP 経路では、split gate/up の `launch_gu()` と split down の `launch_down()` が旧カーネルか multi-entry カーネルを選びます。SYCL では split gate/up/down が lane kernel と multi-entry kernel を選ぶ際にこの値を参照します。選択結果は後続の GPU launch に現れます。

この環境変数を読む箇所に、この値に応じたログ、警告、終了処理はありません。関連する公開ヘッダーは、値を graph capture 前に設定すること、capture 済み graph では capture 時に選んだカーネルが使われることを説明しています。`docs/DETAILS.md` にこの変数の個別説明や測定条件付きの性能値は見つかりませんでした。

## 根拠

- 値判定と環境読み取り: `src/kernels/cuda/iq_kernels.cu:1951-1956`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2813-2818`。
- `iq_mmvq` の CUDA/HIP 分岐: `src/kernels/cuda/iq_kernels.cu:1988-2002`。SYCL 分岐: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3067-3095`。
- grouped expert の CUDA/HIP 通常 gate/up と down の分岐: `src/kernels/cuda/iq_kernels.cu:2666-2693`。専用 V2/V2K 経路、`STRATA_EXP_LAYOUTS` の個別 launch、通常経路の行数選択: `src/kernels/cuda/iq_kernels.cu:3464-3495,3505-3558,3582-3584`。
- SYCL grouped expert の `STRATA_EXPERT_SPLIT` との組み合わせ: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2817-2824,4176-4222`。関連する行数選択: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5200-5204`。
- 結果の同一性、capture に関する説明、setter/getter: `include/strata/kernels/iq_kernels.hpp:82-86`。setter の実装: `src/kernels/cuda/iq_kernels.cu:2698-2699`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4227-4228`。
