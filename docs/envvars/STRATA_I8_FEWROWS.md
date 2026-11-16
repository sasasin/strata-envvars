# `STRATA_I8_FEWROWS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

OWN-I8 の prompt expert 経路において、expert あたりの平均 routed row 数が指定値より少ないとき、通常の OWN-I8 int8 kernel の代わりに grouped kernel を使う境界値を指定する。変数は `native_expert_i8_few_rows_limit()` が読み、`prefill.cpp` が各 native expert layer の経路選択に使う。0 は few-rows 経路を無効にする。環境変数自体は OWN-I8 を有効化せず、kernel の有効条件を満たした場合にだけ経路選択へ影響する（`src/kernels/cuda/iq_kernels.cu:6311-6322`、`src/prefill/prefill.cpp:5991-6010`、`include/strata/kernels/i8_expert_rule.hpp:82-83`）。

## 値と判定

CUDA/HIP 共通の関数内 `static` 変数に `std::getenv` の結果を一度保存し、その文字列を十進数字の先頭部分として読む。未設定・空文字・最初の文字が数字でない値はカード別既定値になる。最初の文字が `0`～`9` なら、連続する数字だけを読む。数字以降の文字は無視される。値全体の数値妥当性、符号、空白、大文字小文字は検査しない。累積値が 100000 を超えた時点で走査を止め、その値を返す（100000 への clamp ではない。実装上の戻り値上限は 1000009）。`include/strata/kernels/i8_expert_rule.hpp:67-80`。

| 条件 | unset / 空文字 / 数字で始まらない値 | 数字で始まる値 |
|---|---|---|
| CUDA compute capability 6.0（Tesla P100） | `6` | 先頭の数字列。例: `0` / `0abc` → 0、`1e3` → 1、`7x` → 7、`1000000` → 999999 |
| それ以外（HIP を含む。CUDA device query 失敗時も含む） | `7` | 同じ先頭数字列規則 |

たとえば `true`、`-1`、`+1`、` 1` は数字で始まらないため既定値、`1 ` は 1、`000` は 0 になる。10進変換は `atoi` ではなく、数字ごとの累積処理である（`include/strata/kernels/i8_expert_rule.hpp:68-80`）。

`STRATA_EXPERT_I8` の実効状態が 0 のときは、こちらの値にかかわらず関数が 0 を返して経路を無効にする。未設定の `STRATA_EXPERT_I8` は build/card class により実効状態が変わるため、表の既定 limit だけで few-rows 経路が有効になるとは限らない（`src/kernels/cuda/iq_kernels.cu:6240-6246,6311-6322`、`include/strata/kernels/i8_expert_rule.hpp:28-39,54-57`）。

## 有効になる条件

- CUDA または HIP backend の OWN-I8 実装を含むビルドであること。この読み取り関数は `src/kernels/cuda/iq_kernels.cu` にある。CPU/SYCL/Metal の読み取り箇所は候補名の全参照検索で見つからなかった。
- prefill の native expert layer が OWN-I8 の group walk へ進むこと。コード上、native layout、fused/staged 経路でないこと、WMMA・Hadamard・peer・CPU share・direct MMQ 等の除外条件、group gather、非空 expert order、必要なバッファが揃うことが前提（`src/prefill/prefill.cpp:5971-5990`）。
- `STRATA_PREFILL_GROUP_GATHER` が未設定、または `atoi` の結果が 0 以外であること（`src/prefill/prefill.cpp:5974-5977`）。空文字・非数値文字列も `atoi` では 0 となり無効になる。
- `STRATA_EXPERT_I8` が 0 でない実効状態で OWN-I8 がその layer を取ること。さらに layout の型・寸法・tail/block 条件および shared memory 制約が対応し、group entry 条件も満たす必要がある（`src/kernels/cuda/iq_kernels.cu:6285-6288,6330-6334`、`include/strata/kernels/i8_expert_rule.hpp:52-57`）。
- few-rows 判定では `limit > 0`、expert 数が正、`rows_local < limit * order.size()` が必要。等号ちょうど、または閾値より大きい場合は通常の int8 側になる。grouped kernel が対応する layout で scratch 条件も満たす必要があり、不成立なら 256-entry floor を使う int8 判定へ戻る（`src/prefill/prefill.cpp:5995-6010`）。
- CLI 引数や設定ファイルによるこの値の上書きは、Strata ソース内に見つからなかった。設定は環境変数の値と上記の build/runtime 条件で決まる。

## 実行時の詳細

`native_expert_i8_few_rows_limit()` の初回呼び出し時に環境変数のポインターを `static` に保存するため、以後の呼び出しで環境を変更しても再読込されない。一方 CUDA の compute capability は関数呼び出しごとに現在 device から問い合わせる。CUDA device の取得に失敗した場合は major/minor が初期値 0 のままなので既定値 7 になる。HIP build はこの CUDA device query をコンパイルせず、既定値 7 を使う（`src/kernels/cuda/iq_kernels.cu:6311-6322`、`include/strata/kernels/i8_expert_rule.hpp:79-80`）。

条件を満たし、`rows_local < limit * order.size()` の場合、`i8_few` が立ち、activations は `quantize_q8_1_rows` で q8_1 化される。その後 group flush が `i8grp::run(..., few=true, ...)` を呼び、grouped kernel に渡す。閾値を満たさない場合は int8 kernel へ進む。grouped route が false を返すと stderr に `prefill: int8 experts: the group's record could not be made (%lld rows, %d experts)` を出してプロセスを終了する。前段の activations / group record の確保失敗は `prefill: int8 experts: no memory for the activations` または `prefill: int8 experts: no memory for the group record` を error として返す（`src/prefill/prefill.cpp:5998-6010,6042-6071,6635-6640`、`include/strata/prefill/i8_group.hpp:61-94`）。

## ログと測定値

この変数の読み取り・閾値判定そのものに対応するログはない。`STRATA_I8_COUNT` を有効にすると、prompt chunk ごとに few-rows route の layer 数と routed entry 数も含む `strata i8-count: ... few-rows route (grouped kernels, counted in the int8 ones): ...` の stderr 行を出す（`src/prefill/prefill.cpp:1865-1876,7267-7274`）。

`docs/DETAILS.md` にこの変数または OWN-I8 few-rows route の説明は見つからなかった。関連する測定条件・数値は Strata のコードコメントにありますが、この調査では再計測していない。`include/strata/kernels/i8_expert_rule.hpp:59-65` は Flash-Next 形状の MoE layer について N8 有無別の平均 row crossing と出典を記載する。コメント上の既定値は N8 ありの crossing に合わせ、P100 は 6、その他は 7。測定値を一般的な速度向上としては扱わない。

## 根拠

- 環境変数の読み取り、`STRATA_EXPERT_I8` による無効化、CUDA/HIP ごとの device query: `src/kernels/cuda/iq_kernels.cu:6311-6322`
- 値の先頭数字列 parse、既定値、境界比較: `include/strata/kernels/i8_expert_rule.hpp:64-83`
- OWN-I8 の状態判定と対応 layout / group size: `src/kernels/cuda/iq_kernels.cu:6240-6246,6285-6288,6330-6334`; `include/strata/kernels/i8_expert_rule.hpp:28-57`
- prefill 適用条件、閾値判定、fallback: `src/prefill/prefill.cpp:5971-6010`
- activations の量子化と grouped / int8 実行経路、観測可能な失敗: `src/prefill/prefill.cpp:6042-6071,6635-6640`; `include/strata/prefill/i8_group.hpp:61-94`
- 任意診断ログ: `src/prefill/prefill.cpp:1865-1876,7267-7274`
