# `STRATA_IQ_STAGE_TABLES`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

IQ3_XXS と IQ3_S の grouped expert gate/up CUDA kernel で、量子化コードブックと符号マスク表を各 CUDA block の shared memory にコピーして使うかを選びます。無効なら同じ計算は通常の global memory 参照で行われます。カーネル内の参照表配置を切り替える設定で、Strata のコメントは結果が bitwise 同じとしています。

この設定は IQ3_XXS / IQ3_S の全演算を一律に切り替えるものではありません。single-matrix MMVQ には適用されず、別の EXPDEC / experimental-layout kernel へ分岐した場合もこの設定を判定しない経路があります。

## 値と判定

`stage_tables_on()` は `getenv()` の値について、文字列全体や数値を parse せず、最初の1文字を判定します。

| `STRATA_IQ_STAGE_TABLES` | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外（例: `1`, `true`, `false`, ` 1`） | 有効 |

大文字小文字、空白、後続文字は検査しません。したがって `false` も有効です。判定値は関数内の `static const bool` に保存され、`g_stage_grid` が有効な状態で最初に関数が呼ばれた時点で読み取られます。その後プロセス内で環境を書き換えても再評価されません。なお `g_stage_grid` が無効なら関数は保存値の初期化より前に `false` を返します。

## 有効になる条件

- `STRATA_IQ_STAGE_GRID` が staging を無効化していないこと。こちらは未設定または空文字なら有効、先頭文字が `0` なら無効です。無効の場合、`STRATA_IQ_STAGE_TABLES` を設定しても有効になりません。
- IQ3_XXS（型 ID 18）または IQ3_S（型 ID 21）の grouped gate/up kernel に到達すること。
- 該当経路で、旧 kernel や別の kernel layout への分岐が先に選ばれないこと。

標準の `launch_gu()` 経路は `STRATA_IQ_STAGE_TABLES` が無効なら非 staging の grouped kernel を起動し、有効なら staging 版を起動します。fused gate/up + SwiGLU 経路も同じ判定を使います。ただし `STRATA_OLD_IQ_MMVQ`、split kernel の無効化、特殊な expert layout などで別 kernel が使われる場合、この判定が kernel 選択に使われないことがあります。

特に `STRATA_EXPDEC` による対応 layout の経路は `expdec_gu_kernel` を使い、その `EdGrid<18/21>` がコードブックとマスク表を staging しますが、`stage_tables_on()` は参照しません。また `STRATA_EXP_LAYOUTS` 下の LDS gate/up 経路も別のテンプレート条件で動きます。このため `STRATA_IQ_STAGE_TABLES=0` はそれらの経路まで含めた全 kernel の staging 禁止を保証しません。

## 実行時の詳細

型 ID 18 は `iq3xxs_grid` 256語と2組の128語の符号マスク表、型 ID 21 は `iq3s_grid` 512語と2組の256語の符号マスク表を shared memory にコピーし、block 内で同期してから dot 計算に使います。符号マスク表は、各値の符号を展開する per-lookup の命令列を置き換えるための表です。`stage_tables_on()` を使う標準経路では、条件を満たさない場合に `STAGE_GRID=false` のテンプレート kernel を選びます。

環境変数の読み取り自体はログ出力、警告、終了状態を発生させません。ソースコメントと `docs/OLDER_GPUS.md` には bitwise 同一性と機種別測定が記載されていますが、性能はハードウェアと kernel 経路に依存し、一般的な速度向上を保証するものではありません。コード内コメントの「compute capability 6.0 では default on」という説明に対し、この HEAD の `stage_tables_on()` は環境変数未設定時に `false` を返します。現行判定は実装コードを根拠にしています。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:726-731` — 型 ID 18 / 21 がそれぞれ IQ3_XXS / IQ3_S であること。
- `src/kernels/cuda/iq_kernels.cu:3280-3304` — `STRATA_IQ_STAGE_GRID` と `STRATA_IQ_STAGE_TABLES` の値判定、static cache、既定値。
- `src/kernels/cuda/iq_kernels.cu:1680-1765` — IQ3_XXS / IQ3_S のコードブックと符号マスク表を shared memory に配置する処理。
- `src/kernels/cuda/iq_kernels.cu:4080-4100` — grouped gate/up の標準 kernel 選択と `stage_tables_on()` の適用。
- `src/kernels/cuda/iq_kernels.cu:4130-4149` — fused gate/up + SwiGLU 経路での同じ判定。
- `src/kernels/cuda/iq_kernels.cu:2361-2379, 3976-4043` — EXPDEC の別 kernel が独自に IQ3 表を staging する経路。
- `src/kernels/cuda/iq_kernels.cu:5151-5203` — grouped expert の呼び出し側での SwiGLU、experimental layout、EXPDEC への分岐。
- `docs/OLDER_GPUS.md:129-142` — 機種別測定の記述と測定範囲。
