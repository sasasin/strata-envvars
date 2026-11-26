# `STRATA_MMVQ_IL_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の interleaved MMVQ が、量子化型・列数・出力行数クラスごとに warp あたりで処理する行数を上書きします。値 `1` / `2` / `4` は専用 interleaved kernel の行数、`0` は通常の `native_mmvq` による経路です。コードコメントでは選択によって出力は bitwise 同一で、表は速度選択だけを変えるとされています（`engine/src/kernels/cuda/native_mmvq.cu:3861-3867, 4236-4252`）。

`STRATA_MMVQ_IL` が有効で、型・GPU・形状が interleaved 経路に対応するときに使われます。これは全体を有効化するスイッチではなく、既定のアーキテクチャ別テーブルより先に単一の表セルを上書きします（`engine/src/core/verify.cpp:192-194, 1848-1857`; `engine/src/kernels/cuda/native_mmvq.cu:4112-4143`）。

## 値と判定

値は `type:ncols:r0,r1,r2,r3,r4` 形式のエントリを `;` で連結します。`type` は GGML 型 ID、`ncols` は列数、5 つの `r` は `n_out` の各クラス（`<2048`, `2048–4095`, `4096–8191`, `8192–12287`, `>=12288`）の値です。ソースコメントの例は 2〜4 列ですが、実際の parser は `ncols` を 1〜4 で受理します（`engine/src/kernels/cuda/native_mmvq.cu:4078-4080, 4089-4097, 4112-4114`）。

| 条件 | 未設定 | 受理される値の例 | 無視または無効になる値の例 |
|---|---|---|---|
| CUDA interleaved MMVQ の表引き | 空の上書き表となり、通常のアーキテクチャ別テーブルへ進む | `23:3:0,0,2,4,4`、複数なら `23:3:0,0,2,4,4;12:2:0,1,1,1,1` | `ncols=0` / `5`、行数の `3` / `-1`、必要な区切りや数値が欠けたエントリは無効 |

`getenv` が null なら空の表を返します。設定された空文字列も parser のループが一度も回らず、警告なしで空の表になります（`engine/src/kernels/cuda/native_mmvq.cu:4081-4088`）。各非空エントリは `sscanf` の `%d` で整数を読み、5 個の行数すべてが `0`、`1`、`2`、`4` のいずれかであること、`ncols` が 1〜4 であることを確認します。したがって符号付き整数や数値前の空白は `%d` の規則で受理されますが、`type` の値域は検査されません（後段で対応型だけが使います）。大文字小文字の概念はありません（`engine/src/kernels/cuda/native_mmvq.cu:4091-4102, 4226-4227`）。

parser は `%n` が示す読み取り位置を検査しないため、5 個目の数値の後ろに続く文字は拒否されず、読み取られた値でエントリが登録されます。区切り文字は形式どおりの `:` と `,` が必要です。無効な行数なら `rows must be 0/1/2/4 - entry ignored`、形式・列数などの読み取りに失敗すれば `cannot read '<entry>' (type:ncols:r0,r1,r2,r3,r4) - ignored` を stderr に出し、そのエントリだけを捨てます（`engine/src/kernels/cuda/native_mmvq.cu:4091-4104`）。同じ `(type,ncols)` を複数登録した場合は、検索が先頭から最初の一致を返すため先のエントリが優先されます（`engine/src/kernels/cuda/native_mmvq.cu:4125-4126`）。

## 有効になる条件

- CUDA 版の `engine/src/kernels/cuda/native_mmvq.cu` が対象です。HIP コンパイル側は stub が `native_mmvq_il_supported()` を常に false とし、`native_mmvq_il_rows_for()` も 0 を返すため、この環境変数を読みません（`engine/src/kernels/cuda/native_mmvq.cu:4255-4271`）。
- `STRATA_MMVQ_IL` は未設定または先頭文字が `0` 以外なら on、先頭文字が `0` なら off です。これは `verify.cpp` で static cache され、off の場合は通常 MMVQ へ進みます（`engine/src/core/verify.cpp:192-194, 1848-1857`）。
- GPU の interleaved 経路が対応していることが必要です。`g_multi_exact` が false、GPU 世代が未対応、または型が IQ4_XS (23)、Q4_K (12)、Q5_K (13)、Q6_K (14)、Q3_K (11) 以外なら専用経路は選ばれません。SM 7.0 / 7.5 / 6.0 / 6.1 ではさらに各世代用の opt-in 条件があります（`engine/src/kernels/cuda/native_mmvq.cu:4191-4214, 4218-4227`）。
- 有効な `(type,ncols)` エントリの行数が `0` なら、`native_mmvq_il_supported()` の判定が false となり、呼び出し側は通常の MMVQ に fallback します。非ゼロ値でも上記の GPU・型・全体スイッチの条件を満たさなければ適用されません（`engine/src/kernels/cuda/native_mmvq.cu:4125-4143, 4218-4234`）。
- 列数 1〜4 はこの環境変数の表を検索します。列数 5〜8 は検索前に別の wide table 経路へ分岐し、この値を使いません（`engine/src/kernels/cuda/native_mmvq.cu:4115-4126`）。
- 環境変数の表は通常のアーキテクチャ表より優先されるため、該当エントリがある場合、通常表の世代別行数選択や Q3_K / one-column 向けの抑止判定より先に返ります（`engine/src/kernels/cuda/native_mmvq.cu:4125-4143`）。ただし対応型と GPU 適用条件は別途残ります。
- `STRATA_MMVQ_IL_PF=1` のとき、sm_70 / sm_80 の PF 表が該当セルに非ゼロの `pf_rows` を持つと、launch 時にその値がこの変数由来の行数を上書きします。通常の `STRATA_MMVQ_IL_PF` 既定値（unset / 0）ではこの上書きはありません（`engine/src/kernels/cuda/native_mmvq.cu:2350-2365, 2419-2430`）。テスト・ベンチマーク API の `native_mmvq_il_tune()` に非ゼロ行数を設定した場合も環境表を使わず、その指定行数が優先されます（`engine/src/kernels/cuda/native_mmvq.cu:4184-4187, 4218-4227`）。

## 実行時の詳細

表は最初に `il_env_rows()` が呼ばれた時点で読み取られ、関数内 `static const std::vector` に保存されます。その後の GPU 呼び出しでは保存済み表が使われ、プロセス実行中に環境を書き換えても再読込されません。読み取りを遅らせるため、interleaved の表引きに到達しない実行では parser も呼ばれません（`engine/src/kernels/cuda/native_mmvq.cu:4081-4108, 4125-4126`）。

一致した表セルは `native_mmvq_il_supported()` の選択判定と、その後の `native_mmvq_il()` の launch の両方で参照されます。非ゼロなら指定した 1 / 2 / 4 行を warp が処理し、0 または一致なしなら通常 MMVQ が使われます（`engine/src/kernels/cuda/native_mmvq.cu:4218-4252`）。通常実行では `verify.cpp` の検証処理が interleaved MMVQ の候補を判定し、必要に応じて量子化済み入力を interleave してから起動します（`engine/src/core/verify.cpp:1831-1857, 1906-1919, 3108-3120`）。

## ログと測定値

不正な非空エントリについて parser が stderr に出す文言は「値と判定」に記載した 2 種類です。正しく読み取れた場合や未設定・空文字の場合、この変数自体による有効化ログはありません（`engine/src/kernels/cuda/native_mmvq.cu:4084-4105`）。この文書では性能値を記載しません。Strata の設計資料にある測定はアーキテクチャ別テーブルの測定であり、この環境変数を設定した場合の測定値ではありません（`docs/MMVQ_IL_TABLE.md:12-22, 32-38`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:4078-4108` — 環境変数の唯一の実読み取り箇所、parser、cache、警告。
- `engine/src/kernels/cuda/native_mmvq.cu:4112-4143, 4218-4252` — 表の優先順位、適用判定、通常経路への fallback、kernel launch。
- `engine/src/kernels/cuda/native_mmvq.cu:2350-2365, 2419-2430, 4255-4271` — PF 上書き、launch 行数、HIP 側 stub。
- `engine/src/core/verify.cpp:192-194, 1831-1857, 1906-1919, 3108-3120` — 全体スイッチと検証処理からの利用。
- `docs/MMVQ_IL_TABLE.md:32-38` — 例示形式と測定手順（parser の実挙動の根拠にはせず、コードと照合）。
