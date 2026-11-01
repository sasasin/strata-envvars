# `STRATA_EXPDEC_MINBLK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリと GPU driver の環境変数は対象外。

## 役割

CUDA の EXPDEC カーネルが、行数を自動で 1 block あたりに割り当てるときの block 数目標を指定します。`STRATA_EXPDEC` を有効化する変数ではなく、EXPDEC が使われない経路には影響しません。

自動選択では、対象行数 `nrow`、1 pass の行数 `rpp`、group 上限 `cap_groups` から、block あたりの行数 `rb` を `rpp` から倍々に増やします。次の倍化後にも `ceil(nrow / (2 * rb)) * max(cap_groups, 1) >= STRATA_EXPDEC_MINBLK` が成り立つ間だけ増やすため、条件を満たす範囲で大きな `rb` を選びます。したがって値を大きくすると、通常は block 数目標を満たすために `rb` が小さくなります。

## 値と判定

CUDA 実装の `env_int_or()` は環境変数が未設定、または空文字列なら既定値を返し、それ以外は `std::atoi()` の結果を使います。既定値は `800` です。文字列全体の検証、範囲検査、clamp、無効値の警告はありません。

| 設定 | 取り込まれる値 | 自動選択での結果 |
|---|---:|---|
| 未設定または空文字列 | `800` | 800 block 以上を維持できる範囲で `rb` を倍増 |
| 数値文字列 | `atoi` の整数値 | その値を下限目標として比較 |
| 数字で始まらない文字列（例: `abc`） | `0` | 比較条件が常に成立し、`rb * 2 <= nrow` の範囲で最大まで倍増 |
| `0` または負数 | その値 | 同様に比較条件が成立し、`nrow` 以下で最大まで倍増 |
| 数字の後ろに文字がある文字列（例: `800x`） | 数字部分の値（例: `800`） | その整数値で比較 |

`atoi` は先頭空白と符号を許し、数字列の後の文字を無視します。整数として表現できない値の結果はこの実装で保証されません。読み取った値に対する追加の妥当性確認やエラー経路はありません。

## 有効になる条件

- この値を読む実装は `src/kernels/cuda/iq_kernels.cu` にあるため、CUDA カーネル実装がビルド・実行される経路が対象です。HIP/SYCL/CPU に同名の読み取り実装はありません。
- EXPDEC の実行には、別途 `STRATA_EXPDEC` または `native_expert_set_expdec()` による有効化が必要です。環境変数 `STRATA_EXPDEC` が未設定なら EXPDEC は初期状態で無効です。
- `STRATA_OLD_IQ_MMVQ` が有効な場合も EXPDEC は使われず、既定カーネルへ進みます。
- gate/up は IQ2_XXS、IQ2_XS、IQ3_XXS、IQ3_S、IQ2_S の形式で、`n_embd == 2560`、`n_ff` が 64 の倍数かつ正の場合に対応します。
- down は `STRATA_EXPDEC_DOWN` が有効で、Q2_0（さらに `STRATA_EXPDEC_D20` が有効な IQ4_NL）かつ `n_ff == 640`、`n_embd` が 128 の倍数かつ正の場合に対応します。
- `STRATA_EXPDEC_RB`（gate/up）または `STRATA_EXPDEC_DRB`（down）が正なら、該当するカーネルは固定行数を使い、この変数による自動選択を行いません。これらが未設定・空文字・0・負数なら既定値 0 または読み取った値に応じて自動選択です。
- `native_expert_set_expdec_params()` に正の `min_blocks` が渡された場合、保存済みの値を上書きします。ベンチ `expdec_bench` は `dec:mN` の選択でこの値を設定できます。通常の engine CLI 引数がこの値を設定する処理は確認できません。

## 実行時の詳細

`g_expdec_minblk` は CUDA translation unit のグローバル初期化で `env_int_or("STRATA_EXPDEC_MINBLK", 800)` を一度評価して保持します。リクエストごとの環境再読込やプロセス起動後の環境変更追跡はありません。内部 API の `native_expert_set_expdec_params()` は `p.min_blocks > 0` の場合に限り値を更新します。0 や負数は setter では無視され、現在値を保ちます。

EXPDEC の gate/up 自動 `rb` は `rpp = 16 * R`、down は `(256 / LANES) * R` を基準にします（`R` は別設定、`LANES` は down 形式に応じて 8 または 16）。正の `STRATA_EXPDEC_RB` / `_DRB` がある場合は、その値を基準行数単位に切り上げ、`nrow` を超える場合は `nrow` に制限します。自動計算は `native_expert_grouped()` から EXPDEC launch に到達したときに行われます。

EXPDEC が対象 layout に初めて到達すると stderr に形式ごとのログが一度出ます。対応外なら `strata expdec: CUDA%d ... not covered: the default kernel runs`、対応する場合は `strata expdec: CUDA%d gate/up ... %d rows per block ...` または down の同様の行に、選ばれた `rb` と grid が出ます。CUDA graph capture 中ならログ末尾に `captured into a graph` が付きます。無効な値そのものを示す警告やエラー、終了経路はありません。launch 後の CUDA エラーは共通の `check()` が stderr に出し、プロセスを終了しますが、これは本変数専用の失敗処理ではありません。

## 根拠

- 候補名の全参照検索では、実際の環境読み取りは `src/kernels/cuda/iq_kernels.cu:4073` のみです。`docs/EXPERTDEC.md:25` と `src/kernels/cuda/iq_kernels.cu:2443` にも説明上の参照があります。
- 空値・未設定 fallback と `atoi`: `src/kernels/cuda/iq_kernels.cu:4055-4059`。
- グローバル設定、既定値 800、自動選択式: `src/kernels/cuda/iq_kernels.cu:4060-4075,4085-4095`。
- gate/up と down の対応 layout・形状条件、EXPDEC の無効化条件: `src/kernels/cuda/iq_kernels.cu:4077-4084,4151-4191`。
- 固定 block 行数と自動計算の呼び分け: `src/kernels/cuda/iq_kernels.cu:4098-4105,4167-4174`。
- stderr ログ文言と一度だけの記録: `src/kernels/cuda/iq_kernels.cu:4120-4148`。
- API setter による正値上書きと getter: `src/kernels/cuda/iq_kernels.cu:6216-6238`。API の値の意味・setter 条件: `include/strata/kernels/iq_kernels.hpp:119-131`。
- ベンチ CLI の `dec:mN` parse と API 反映: `src/kernels/expdec_bench.cpp:72-107`。ベンチは通常の既定 build に含まれず、明示的な `expdec_bench` target です: `CMakeLists.txt:2510-2512`。
- EXPDEC 概要と前提の資料: `docs/EXPERTDEC.md:1-42`。同資料も既定値 800 と自動 block 数目標を記しています。
