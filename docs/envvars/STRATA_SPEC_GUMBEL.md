# `STRATA_SPEC_GUMBEL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数の動作は対象外。

## 役割

サンプラーの通常の逆累積分布（inverse CDF）による抽選を、Gumbel-max による抽選に切り替えます。候補 token ごとに seed・位置・token ID から指数分布ノイズを作り、最終分布の確率をそのノイズで割った値が最大の token を選びます。候補集合が異なる MTP draft と target の間で、共通候補には同じノイズを割り当てるため、両者の候補順位の違いに左右されにくい抽選になります。

環境変数を読むのは CUDA sampler 実装 `src/kernels/cuda/sampler.cu` です。同じソースの `sample_tokens()` による target 側の抽選では、coupled draft を使わない場合も有効です。draft 側の抽選へ設定を渡すのは `coupled_draft_stage()` であり、MTP の coupled draft 経路が動くときに限られます。

## 値と判定

値を数値や真偽値として parse せず、共通 helper `env_flag()` が環境変数の有無、空文字、文字列全体が `0` かを判定します。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 文字列がちょうど `0` | 無効 |
| その他の非空文字列 | 有効（例: `1`, `00`, `false`, ` 0`） |

大文字小文字や数値としての妥当性は検査しません。`STRATA_SPEC_GUMBEL=0anything` は文字列全体が `0` ではないため有効です。`sample_tokens()` では内部の `SamplerParams::gumbel` が既に true なら、環境変数が無効でも Gumbel 抽選が有効です。

判定結果は `gumbel_env()` 内の関数ローカル `static const bool` に保存されます。プロセス内で最初に `sample_tokens()` または `coupled_draft_stage()` から参照した時点で読み取り、その後の環境変更は反映されません。

## 有効になる条件

- `sample_tokens()` の sampled 経路で、`greedy` が false かつ `temperature > 0` のときに抽選方式を切り替えます。greedy / `temperature <= 0` は argmax 分岐を通るため変化しません。
- `sample_tokens()` の sampled 経路では、top-k、top-p、min-p、temperature の処理後に残った候補と確率を使います。旧 sampler、one-block sampler、split sampler のいずれも最終的に Gumbel 判定を使う tail / pick 部分を通ります。split scratch が使えず one-block に fallback する場合も同じです。
- MTP draft と target の候補集合差に対して同じ token ごとのノイズを使う効果は、coupled draft 経路が有効な場合に限られます。coupled draft は `STRATA_SPEC_COUPLED` または CLI 設定により起動されます。Gumbel 自体は `STRATA_SPEC_COUPLED` がなくても target の `sample_tokens()` には適用されます。
- `STRATA_SPEC_PROB` の draft は `spec_draft_sample()` を使い、ここでは Gumbel 抽選を行いません。また専用の `sample_tokens_spec()` は `sample_tokens()` のように環境変数を `SamplerParams` に上書きせず、専用 verification merge も Gumbel 判定を参照しません。そのため、この専用 speculative verification path では `STRATA_SPEC_GUMBEL` による抽選切り替えは行われません。通常の `sample_tokens()` に fallback する経路では同関数側の判定が適用されます。
- 調査対象ソース内で変数名の実コード参照は CUDA sampler にあります。SYCL 側の sampler に同名の環境変数参照は見つかりません。CUDA sampler のビルド登録は `CMakeLists.txt` にあります。個別の CUDA/HIP ビルド構成や実行環境での動作確認はこの調査では行っていません。

## 実行時の詳細

`env_flag()` は `std::getenv()` の結果が null でなく、先頭文字が NUL でなく、`strcmp(value, "0") != 0` である場合に true を返します。`gumbel_env()` がこの結果を初回に一度だけキャッシュします。通常 sampler の `sample_tokens()` は入力構造体をコピーし、`p.gumbel = p_in.gumbel || gumbel_env()` として kernel に渡します。kernel は各行 `t` の top-k/top-p/min-p と temperature 適用後に、`exp(logit - max) / sum` の確率を作ります。有効時は token ID と `(seed, counter + t)` で決まる `gumbel_exp()` を使い、確率を指数ノイズで割った比が最大の token を採用します。無効時は同じ分布に対して従来の Philox 一様値で累積確率を引きます。

coupled draft では、MTP の round graph 内で `coupled_draft_stage()` が `gumbel_env()` の結果を device 側 `SamplerParams::gumbel` へコピーします。続く `coupled_draft_sample()` は target と共通の sampler chain と counter を用い、同じ token ID に同じノイズを与えます。sub-vocabulary の draft head では、draft index でなく `sub_to_id` で復元した token ID をノイズ key に使います。greedy または temperature が 0 以下の draft は kernel の argmax 分岐を通るため影響を受けません。

この変数自体によるログ出力は実装にありません。`docs/DETAILS.md` は Gumbel-max が同じ最終分布からの抽選であると説明し、Ryzen AI Max+ 395 / Radeon 8060S / Linux / ROCm 7.14.1 の UD-Q4_K_XL、`--spec 4 --mtp`、temperature 1.0、top-p 0.95、top-k 20 などの条件で coupled draft acceptance と出力速度を比較しています。同資料では、RTX 3060 / IQ3_XXS の別測定で Gumbel 追加による速度差は run-to-run のばらつきを超えなかったと記しています。これらは当該条件での資料記載値であり、一般的な性能保証ではありません。

## 根拠

- `src/kernels/cuda/sampler.cu:66-78`: Gumbel noise の key と計算。
- `src/kernels/cuda/sampler.cu:471-552`: 通常 sampler と coupled draft が共有する tail の候補確率、Gumbel pick、inverse-CDF pick。
- `src/kernels/cuda/sampler.cu:1106-1114`: 空文字・`0` の判定規則と初回判定の static cache。
- `src/kernels/cuda/sampler.cu:1239-1290`: 通常 sampler への設定適用、greedy 分岐、および旧・one-block・split の経路。
- `src/kernels/cuda/sampler.cu:1317-1343`: coupled draft への設定転送と sampled tail の呼び出し。
- `src/kernels/cuda/sampler.cu:1347-1370,1372-1390`: speculative verification と probabilistic draft の専用経路。これらの関数では `gumbel_env()` を読み出さない。
- `src/core/mtp.cpp:1199-1209,1270-1280`: MTP が coupled draft と probabilistic draft のどちらを呼び、round graph 内で coupled 設定を staging するか。
- `include/strata/kernels/sampler.hpp:15-30`: `SamplerParams::gumbel` の定義。
- `include/strata/core/coupled_draft.hpp:14-17`: coupled draft と Gumbel の設計説明。
- `CMakeLists.txt:377-385`: `sampler.cu` の `strata_kernels` への登録。
- `docs/DETAILS.md:116-128`: 機能説明、適用条件、記載された測定条件と結果。
