# `STRATA_ACT_DUMP_COV`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU native expert の入力 activation を記録する `STRATA_ACT_DUMP` 機能に、各記録ベクトルの外積を加算した行列を追加します。各 layer の gate/up 入力と down 入力それぞれについて `sum(x x^T)` を保存します。平均を引く処理はないため、平均中心化した統計的共分散行列ではなく、未中心化の二次モーメント行列です。

研究・キャリブレーション用の機能です。環境変数だけでは記録を開始せず、非空の `STRATA_ACT_DUMP` と、少なくとも一つの layer を指定する `STRATA_ACT_DUMP_LAYERS` も必要です。

## 値と判定

`ActDump` の初期化時に、`getenv("STRATA_ACT_DUMP_COV") != nullptr && std::atoi(value) != 0` で判定します。未設定は無効です。設定値は文字列全体を検証せず、`atoi` が先頭から読める10進整数を変換します。

| 設定値の例 | 判定 |
|---|---|
| 未設定、空文字、`0`、`00`、`abc`、`0.5` | 無効（変換結果が0） |
| `1`、`-1`、`2tail`、`  +3` | 有効（変換結果が0以外） |

したがって `true` は有効にならず、数値の後ろに文字があっても数値部分が0以外なら有効です。先頭の空白と符号は `atoi` の規則で処理されます。大文字小文字の比較はありません。

## 有効になる条件

- `STRATA_ACT_DUMP` が設定され、かつ空文字でないこと。そうでない場合、初期化処理は早期 return し、この変数を判定しません。
- `STRATA_ACT_DUMP_LAYERS` の解析結果が空でないこと。層リストが空なら `ActDump::on` が false のままで、記録関数は呼ばれません。
- CPU native expert の `native_quant_act` または `native_quant_h` が通ること。これらの関数は量子化する入力を記録します。通常の native expert が使われない経路、または native expert を含まないビルドでは、この機能による記録は行われません。

`STRATA_ACT_DUMP_LAYERS` はカンマ区切りの各要素を `atoi` で整数化し、記録時に `NativeFmt.layer` と一致する層だけを蓄積します。gate/up は1 token ごと、down は routed expert ごとに記録されます。折り畳み層では、gate/up または down の Hadamard 回転後のベクトルが記録対象です。

## 実行時の詳細

設定は `act_dump()` が最初に呼ばれたときに作られるプロセス内 singleton の `ActDump` で読み取られます。値はその後キャッシュされ、実行中の環境変更は再評価されません。有効時は layer と入力種別ごとに要素数 `n` の二乗サイズの `double` 配列を確保し、各ベクトルについて `cov[i*n+j] += x[i]*x[j]` を加算します。これに加え、`sum(x[i]*x[i])` と記録数も維持します。

ファイル名は `<STRATA_ACT_DUMP値>_L<layer>_gu.bin` または `<prefix>_L<layer>_dn.bin` です。バイナリには順に `int64 n`、`int64 count`、`double sum(x²)[n]`、`double sum(x xᵀ)[n*n]` を書きます。行列は行優先です。出力は一時ファイル `.tmp` に書いてから元ファイル名へ rename します。共分散行列を有効にした場合、記録した activation が全層・種別合計で400,000件に達するごとに蓄積分を書き出し、終了時にも flush します。無効時の flush 間隔は2,000件です。

ファイルを開けない場合はその flush 対象を飛ばします。環境変数の値やファイル書き込みに関するログ出力は、この実装箇所にはありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:135-139` — 診断用 dump の目的、関連環境変数、ファイル形式の概要。
- `src/kernels/cpu/native_expert.cpp:145-174` — prefix の必須条件、`atoi` による判定、layer の読み取りと singleton 初期化。
- `src/kernels/cpu/native_expert.cpp:176-214` — 出力形式、行列の蓄積、flush 間隔と一時ファイルの rename。
- `src/kernels/cpu/native_expert.cpp:217-240` — gate/up と down の入力を記録する位置、および Hadamard 回転。
- `src/core/expert_source.cpp:5005-5015`、`src/prefill/prefill.cpp:4028-4033` — 通常の decode と prefill における CPU native activation 量子化の呼び出し。
- `tools/trellis/build_swap.py:67-75` — Trellis ツールがファイル内の `n*n` 行列を covariance として読み、未記録なら `STRATA_ACT_DUMP_COV=1` で再キャリブレーションするよう求めること。
