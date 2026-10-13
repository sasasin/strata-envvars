# `STRATA_IQ_STAGE_GRID`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

i-quant の一部の GPU kernel が使う codebook grid（64-bit の lookup table）を、kernel 実行中に shared/local memory へコピーして参照するかを切り替えます。無効にすると同じ grid を元のテーブルから直接読みます。CUDA と SYCL に実装があります。

## 値と判定

CUDA (`src/kernels/cuda/iq_kernels.cu`) と SYCL (`sycl/src/kernels/cuda/iq_kernels.dp.cpp`) は同じ判定です。値全体の parse や数値変換はせず、未設定か、先頭1文字だけを見ます。

| 値 | `g_stage_grid` |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効 |
| 先頭文字が `0`（例: `0`, `0anything`） | 無効 |
| それ以外（例: `1`, `false`, ` 0`） | 有効 |

大文字小文字・空白・後続文字は検査しません。したがって `false` や先頭に空白のある ` 0` も有効です。環境値は翻訳単位のグローバル `bool` 初期化時に読み込まれ、その後の呼び出しではキャッシュ値を使います。プロセス実行中に環境を変更しても再評価されません。

根拠: `src/kernels/cuda/iq_kernels.cu:1958-1962`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2825-2829`。

## 有効になる条件

- 切替対象は compile-time の `kStageIqGrid<TY>` が真の形式、すなわち型 ID `16`, `17`, `22`, `29`（IQ2_XXS、IQ2_XS、IQ2_S、IQ1_M）です。他の形式ではこの環境変数による staging の切替はありません。根拠: `src/kernels/cuda/iq_kernels.cu:664-666,715-716,741-742,835-836` と SYCL 側の同等箇所 `sycl/src/kernels/cuda/iq_kernels.dp.cpp:869-871`。
- CUDA では、旧 kernel を `STRATA_OLD_IQ_MMVQ` で選んだ経路は新しい切替分岐を通りません。通常の新 kernel 経路では single-matrix MMVQ と grouped expert の gate/up kernel の staging を切り替えます。grouped expert の down kernel はこの変数を参照せず、別の activation staging を行います。根拠: `src/kernels/cuda/iq_kernels.cu:1988-2003,1361-1372,2666-2694`。
- SYCL の MMVQ 経路は同様に `g_stage_grid` を使います。一方、SYCL の grouped expert は既定の lane kernel を使い、この変数の分岐には入りません。`STRATA_EXPERT_SPLIT` が有効で、旧 kernel でなく、split 形式が選ばれた場合に限り grouped multi kernel に進み、その経路でこの変数が staging を選びます。根拠: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2822-2829,3087-3095,4176-4194`。
- 追加の `STRATA_IQ_STAGE_GRID_MMVQ` は MMVQ の staging をさらに opt-in に制限します。`STRATA_IQ_STAGE_GRID` が無効ならこちらが設定されていても MMVQ staging は有効になりません。CUDA/SYCL とも追加変数は未設定を無効とし、値の先頭文字が `1` の場合だけ有効です（`10` も有効）。grouped expert 側の staging 判定には使われません。根拠: `src/kernels/cuda/iq_kernels.cu:1963-1969,1994-2001`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2830-2836,3087-3095`。

## 実行時の詳細

staging が有効な kernel では、対象 IQ codebook テーブルを thread block/work group の shared/local memory にコピーし、同期後に各 weight の decode でそのコピーを参照します。CUDA 実装は `stage_iq_grid()` で IQ2_XXS 2 KiB、IQ2_XS 4 KiB、IQ2_S と IQ1_M 各8 KiB相当をコピーします（`uint2` の要素数に8 byteを掛けた値）。staging が無効なら helper は `nullptr` を返し、各形式の `Split::load` が元の codebook table を参照します。SYCL も対応する local memory へのコピーと barrier を行います。根拠: `src/kernels/cuda/iq_kernels.cu:1120-1155,667-678,717-724`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:1461-1507,869-871`。

この環境変数を読む箇所は CUDA と SYCL の各翻訳単位に1か所です。通常利用者向けの起動ログ、警告、エラーはこの判定コードからは出ません。`docs/DETAILS.md` にこの変数の説明は見つからず、`docs/INTEL.md:530-544` は SYCL の expert kernel と `STRATA_EXPERT_SPLIT` の条件を説明していますが、本変数の値判定は記述していません。性能値はここでは記載しません。

## 根拠

- 値の読み取りと既定値: `src/kernels/cuda/iq_kernels.cu:1958-1969`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2825-2836`。
- staging 対象形式、shared/local memory へのコピー: `src/kernels/cuda/iq_kernels.cu:664,1120-1155`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:869,1461-1490`。
- CUDA 呼び出し先での分岐: `src/kernels/cuda/iq_kernels.cu:1988-2003,2666-2684`。
- SYCL 呼び出し先での分岐と適用条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3087-3095,4176-4194`。
