# `STRATA_IQ_STAGE_TABLES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA IQ grouped expert の gate/up カーネルで、IQ3_XXS (type 18) と IQ3_S (type 21) の codebook と符号 mask 表を block の shared memory にコピーして参照する経路を選びます。既定ではこの専用 staging は無効です。単一行列の `mmvq` ではこの変数を使いません。実装は `stage_tables_on()` と `launch_gu()` にあります。[`engine/src/kernels/cuda/iq_kernels.cu:3708-3719,4541-4570`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

stage 時は `stage_iq_grid()` が IQ3_XXS / IQ3_S の codebook と sign-mask 表を shared memory に書き、grouped expert kernel がそれを読みます。非 stage 時は同じ形式の非 staging multi kernel を起動します。ソースコメントは出力が bitwise 同一としていますが、この調査では実行比較していません。[`engine/src/kernels/cuda/iq_kernels.cu:1997-2053,4559-4567`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 値と判定

`stage_tables_on()` が初回に呼ばれたとき `std::getenv` で読み、文字列全体の parse はせず、空でない先頭文字が `'0'` 以外なら on とします。空文字は off、未設定も off です。`false` や `true` を認識する parser ではありません。大文字小文字、後続文字、数値としての妥当性は検査せず、空白始まりは on、`0anything` は off になります。[`engine/src/kernels/cuda/iq_kernels.cu:3713-3719`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `STRATA_IQ_STAGE_GRID` が unset / 空 / 先頭が `0` 以外 | 本変数は off | `1`, `true`, `false`, ` 0` | unset, 空文字, `0`, `0anything` |
| `STRATA_IQ_STAGE_GRID` の先頭が `0` | 常に off | なし | 本変数の値にかかわらず全て |

この変数に CLI 引数や別の環境変数から値を渡す処理はありません。別環境変数 `STRATA_IQ_STAGE_GRID` は staging 全体の上位 gate で、unset・空文字では on、先頭が `0` なら本変数の読み取り結果も使われません。[`engine/src/kernels/cuda/iq_kernels.cu:3696-3700,3713-3719`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 有効になる条件

- CUDA `launch_gu()` の multi-kernel 経路に入ること。`STRATA_OLD_IQ_MMVQ` が有効なら旧 `native_gu_kernel` に分岐し、この staging 判定を使いません。IQ3_XXS / IQ3_S は split 対応形式で、K-quant などに適用される `STRATA_KQ_SPLIT` の gate 対象ではありません。[`engine/src/kernels/cuda/iq_kernels.cu:987-995,4541-4552`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- gate/up の type が IQ3_XXS (18) または IQ3_S (21) であること。`launch_gu()` の型ごとの分岐は `STRATA_GU_FMTS` から展開され、判定はこの二形式に限られます。[`engine/src/kernels/cuda/iq_kernels.cu:994-995,4550-4567,7305-7311`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `STRATA_IQ_STAGE_GRID` が有効であること。無効なら `stage_tables_on()` は直ちに false を返し、非 staging kernel が選ばれます。[`engine/src/kernels/cuda/iq_kernels.cu:3696-3700,3713-3719,4559-4562`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `STRATA_EXP_LAYOUTS` の `fused_gu` 経路で先に処理される場合、この変数による `launch_gu()` の分岐には入りません。`launch_gu_swiglu()` が選ばれる経路では、type 18/21 の staging 判定にもこの変数が使われます。同経路は `gu_swiglu_on()`、layout、shape などの条件を満たす必要があります。[`engine/src/kernels/cuda/iq_kernels.cu:7205-7239,7241-7255,4597-4618`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `STRATA_EXPDEC` が有効で `expdec_gu_ok()` の形状条件（`had_block == 0`、`tail_off == 0`、`n_embd == 32 * ED_XB`、`n_ff` が 64 の倍数かつ正）を満たす場合も EXPDEC の別 kernel が起動し、この変数による `launch_gu()` 判定には入りません。条件不成立時は理由ログを出して通常経路へ進みます。`STRATA_OLD_IQ_MMVQ` が有効なら EXPDEC は使われません。[`engine/src/kernels/cuda/iq_kernels.cu:4378-4381,4421-4442,4452-4466,7300-7311`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `STRATA_EXPERT_NIBBLE` build で対象 expert layer が `nib_layout(L)` なら nibble gate/up kernel が選ばれ、本変数を参照しません。[`engine/src/kernels/cuda/iq_kernels.cu:5276-5310,7300-7311`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- `STRATA_EXP_LAYOUTS` が有効な HIP grouped expert で AMD layout の `em` が 1, 2, 4 かつ `amd_gu` 対象なら `native_gu_amd_kernel` が選ばれ、その分岐では本変数を参照しません。AMD build 全体での他の `em` 経路における採用条件は、この分岐だけからは一般化しません。[`engine/src/kernels/cuda/iq_kernels.cu:7283-7299`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 実行時の詳細

`g_stage_grid` は翻訳単位の初期化時に読み取られます。一方、本変数は `stage_tables_on()` の関数内 `static` として初回に評価され、以降その値を cache します（ただし `g_stage_grid` が false の呼び出しでは static 初期化に到達しません）。そのため、プロセス起動後に環境を変更しても、既に評価済みの判定は変わりません。[`engine/src/kernels/cuda/iq_kernels.cu:3696-3700,3713-3719`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

標準の `launch_gu()` では type 18/21 について、stage 判定が true なら `native_gu_multi_kernel<TG, true, ...>`、false なら `native_gu_multi_kernel<TG, false, ...>` を起動します。`g_no_sub16_gu` によって template の第3引数も変わりますが、本変数はその選択を変えません。[`engine/src/kernels/cuda/iq_kernels.cu:4541-4570`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## ログと測定値

この変数の読み取り・on/off 判定専用のログや警告はありません。grouped expert の後続 `check("native_expert_grouped/gu")` は CUDA error を検査し、失敗時は `what: error` を stderr に出して `exit(1)` します。これは変数固有のエラーではありません。[`engine/src/kernels/cuda/iq_kernels.cu:47-50,7313-7316`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

`docs/OLDER_GPUS.md` は Pascal で既定 off と記載し、P100 の A/B は end-to-end で変化なし、RTX 3090 Ti では強制 on の同じ層が 3–13% 長くかかったと記録しています。これらは同資料にある測定条件の範囲の記述であり、現行 commit での再測定ではありません。[`docs/OLDER_GPUS.md:133-138,167-169`](../../../../Niko1221/Strata/docs/OLDER_GPUS.md)

現行コードの `stage_tables_on()` は GPU compute capability を調べず、未設定時に off を返します。一方、同じ実装直前のコメントには cc 6.0 で既定 on とする記述があります。実コードにその既定判定はないため、この文書ではコード上の off を現行挙動として記載しました。[`engine/src/kernels/cuda/iq_kernels.cu:3708-3719`](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:3696-3719` — `STRATA_IQ_STAGE_GRID` と本変数の読み取り、判定、cache。
- `engine/src/kernels/cuda/iq_kernels.cu:1997-2053` — IQ3_XXS / IQ3_S の staged table の構築。
- `engine/src/kernels/cuda/iq_kernels.cu:4541-4570,4597-4618` — grouped gate/up の kernel 選択。
- `engine/src/kernels/cuda/iq_kernels.cu:7205-7239,7283-7299,7313-7316` — fused / AMD dispatch とエラー確認。
- `docs/OLDER_GPUS.md:133-138,167-169` — スイッチ一覧と既存の条件付き測定記録。
