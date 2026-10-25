# `STRATA_EXPDEC_RB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の EXPDEC gate/up カーネルで、1 block が処理する出力行数を指定する調整値です。未設定または 0 以下なら、起動時の group 数と `STRATA_EXPDEC_MINBLK` を使って自動決定します。down カーネルの行数は別の `STRATA_EXPDEC_DRB` が制御します。

この値だけでは EXPDEC は有効になりません。`STRATA_EXPDEC` が有効で、旧 multi kernel が無効、かつ対象の weight format と形状が gate/up EXPDEC の対応条件を満たした場合に使われます。

## 値と判定

`env_int_or("STRATA_EXPDEC_RB", 0)` が初期値を読みます。値が未設定または空文字なら既定値 `0` です。それ以外は `std::atoi` で整数に変換します。文字列全体の数値検証はなく、たとえば `16tail` は `16`、数値で始まらない文字列は `0` になります。

| 変換後の値 | 動作 |
|---|---|
| `<= 0` | 自動決定。1 pass 分の行数から始め、`STRATA_EXPDEC_MINBLK` 個以上の block を保てる範囲で block あたりの行数を倍増する。 |
| `> 0` | 指定値を pass あたり行数の倍数に切り上げ、総行数 `2 * n_ff` を上限にする。 |

pass あたりの行数は `16 * R` です。`R` は `STRATA_EXPDEC_R` の値がちょうど `2` の場合だけ 2、それ以外は 1 です。したがって設定値はそのまま採用されるとは限らず、切り上げまたは総行数への切り詰めが行われます。

## 有効になる条件

- CUDA の EXPDEC gate/up 実装経路であること。EXPDEC の実装資料は CUDA only としています。
- `STRATA_EXPDEC` が有効であること。無効なら gate/up は通常カーネルに進みます。
- `STRATA_OLD_IQ_MMVQ` によって旧 kernels が選ばれていないこと。
- gate/up の weight type が 16、17、18、21、22 のいずれかで、`n_embd == 32 * ED_XB`、`n_ff > 0`、`n_ff` が 64 の倍数であること。

対応外の形式や形状では、この行数設定は gate/up の通常カーネルに影響しません。対象形式でも EXPDEC 自体が有効になっていなければ使用されません。

## 実行時の詳細

環境変数は `iq_kernels.cu` のグローバル設定値初期化時に読み取られます。処理時に `expdec_rows_per_block()` が設定値を参照し、正値の場合は `rb = ceil(knob / (16 * R)) * (16 * R)` を計算して `nrow = 2 * n_ff` を超えないようにします。この `rb` が gate/up kernel の grid と kernel 引数に使われます。0 以下の場合は、`cap_groups`（0 以下なら 1 として扱う）と `STRATA_EXPDEC_MINBLK` に基づく倍増ループで `rb` を決めます。

EXPDEC が対応形式に適用されると、stderr に `strata expdec: CUDA... gate/up ... rows per block ...` 形式のログが、その role / format の初回に出ます。対応しない形式では通常カーネルを使う旨のログになります。

`native_expert_set_expdec_params()` API は `gu_rows_per_block >= 0` の場合にこの値を上書きできます。ソース内の呼び出しは `src/kernels/expdec_bench.cpp` のベンチ用経路で確認できます。環境変数を実行中に変更した場合の再読み込みはありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3933-3953`: `env_int_or()` の空値・変換規則、既定値、関連 knob。
- `src/kernels/cuda/iq_kernels.cu:3955-3957`: gate/up の対応 weight type と shape 条件。
- `src/kernels/cuda/iq_kernels.cu:3963-3974`: rows-per-block の自動選択と正値の丸め・上限処理。
- `src/kernels/cuda/iq_kernels.cu:3976-3983,4015-4019`: gate/up 起動時の `rb` 利用とログ。
- `src/kernels/cuda/iq_kernels.cu:4030-4035,5200`: EXPDEC と旧-kernel 条件、および通常 kernel fallback。
- `src/kernels/cuda/iq_kernels.cu:5022-5030`: API からの設定上書き。
- `src/kernels/expdec_bench.cpp:68-70,383`: ベンチが起動時設定を読み、設定 API を呼ぶ経路。
- `docs/EXPERTDEC.md:1-4,16-34,40-42`: CUDA only、EXPDEC の役割、block 行数 knob と既定の自動決定の説明。測定値は `STRATA_EXPDEC_RB` 固有の推奨値を示すものではないため、本書では設定値の性能効果を断定しない。
