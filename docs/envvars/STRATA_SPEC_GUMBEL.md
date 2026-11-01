# `STRATA_SPEC_GUMBEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

GPU sampler の確率抽選を inverse-CDF 方式から Gumbel-max 方式に切り替える opt-in です。各候補 token の確率で重み付けした値を、`seed`・位置 counter・token ID から決まる指数乱数で割り、最大の token を選びます。通常の sampled pick では `sample_tokens()` がこの設定を sampler parameter に反映します。MTP の coupled draft sampling が別途有効な場合は、draft 側にも同じフラグを渡します。

この値だけでは MTP の coupled draft sampling は有効になりません。coupled draft の有効化には `STRATA_SPEC_COUPLED`、`--coupled-draft`、または同じ機構を使う `STRATA_SPEC_PROB` が別途関係します。

## 値と判定

`env_flag()` は `getenv()` の結果が null でなく、空文字列でもなく、文字列全体がちょうど `0` でないとき true を返します。数値 parse や trim はしません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字列 | 無効 |
| `0` | 無効 |
| `1` | 有効 |
| `00`、`0abc`、`false`、前後に空白のある `0` など | 有効（文字列全体が `0` と一致しないため） |

`gumbel_env()` 内の function-local `static const bool` に初回の判定結果が保存されます。`sample_tokens()` または coupled draft の stage が最初に `gumbel_env()` を呼んだ後にプロセス環境を変更しても再評価されません。根拠: `src/kernels/cuda/sampler.cu:1127-1135`。

## 有効になる条件

- sampled sampling で有効です。`sample_tokens()` は入力 parameter の `gumbel` が false でも、環境判定が true なら true にします。既定の split sampler と `STRATA_SAMPLER_ONE_BLOCK` または split fallback の one-block sampler はこの値を最終抽選で参照します。`STRATA_OLD_SAMPLER` が選ぶ旧 sampler は `p.gumbel` を参照せず、inverse-CDF 抽選のままです。`p.greedy` または `temperature <= 0` の経路も argmax となり、Gumbel 抽選を使いません。根拠: `src/kernels/cuda/sampler.cu:297-435,483-550,555-564,1260-1290`。
- split / one-block sampler の Gumbel-max noise は `(seed, counter, token ID)` から生成され、確率分布は top-k / top-p / min-p と temperature の処理後に抽選へ使われます。根拠: `src/kernels/cuda/sampler.cu:67-81,412-435,520-550`。
- MTP draft の Gumbel 抽選には coupled draft の有効化も必要です。coupled draft は環境変数 `STRATA_SPEC_COUPLED`、`STRATA_SPEC_PROB`、または CLI `--coupled-draft` で制御され、`--no-coupled-draft` は CLI 側の状態を false にします。`STRATA_SPEC_GUMBEL` 自体は coupled draft を起動しません。根拠: `include/strata/core/coupled_draft.hpp:57-79`、`src/program/generate.cpp:653,3139-3140,3499`、`src/core/mtp.cpp:589-590,790`。
- coupled draft が動くと、各 round の `coupled_draft_stage()` がこの flag を device 上の sampler parameter に設定し、draft の pick に使います。draft head の語彙が sampler の上限を超える場合は coupled sampler を設定せず argmax draft に戻ります。根拠: `src/kernels/cuda/sampler.cu:807-817,1338-1343`、`src/core/mtp.cpp:594-608,1245-1255`。
- build 範囲は CUDA/HIP backend の GPU core です。CMake は `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` の範囲で GPU core と kernel target を作り、その kernel target に `src/kernels/cuda/sampler.cu` を含めます。根拠: `CMakeLists.txt:410-416,452-465`。

## 実行時の詳細

通常の生成では、`sample_tokens()` が環境判定を `SamplerParams::gumbel` に OR します。既定の split と one-block sampled kernel はこれを使いますが、`STRATA_OLD_SAMPLER` の旧 kernel は読みません。seed と位置 counter は通常の inverse-CDF 抽選と同様に draw を識別し、Gumbel noise の追加 key に token ID を使います。greedy または温度 0 以下ではこの設定を parameter に反映しても argmax 経路となり、Gumbel 抽選は行いません。

MTP coupled draft の場合は、draft の各 round を stage するときに同じ設定を device parameter へコピーし、coupled draft kernel が token ID ごとの noise を使います。ただし `STRATA_SPEC_PROB` が使う `spec_draft_merge_kernel()` は q からの draft pick を独自の Philox inverse-CDF で行い、`sample_tokens_spec()` / `sample_tokens_proposal()` もこの環境変数を直接読みません。Verifier がそれらの経路を使う場合に Gumbel 設定が自動で伝播するとは限りません。Verifier が通常の `sample_tokens()` に fallback する経路では、同関数の環境判定が使われます。根拠: `src/kernels/cuda/sampler.cu:938-980,1260-1264,1368-1387`、`src/core/verify.cpp:3359-3395`。

環境変数専用のログや無効値警告はありません。文字列 `0` や unset は通常の inverse-CDF 抽選となり、それ以外の非空値は sampled pick を Gumbel-max に切り替えます。通常の sampler kernel 起動に失敗した場合は `sample_tokens launch: ...` を stderr に出して `exit(1)`、Verifier の同期失敗は `verify: the head sampling failed` のエラーになります。これらはフラグの値検査ではなく、該当する一般の sampler / verifier エラー経路です。根拠: `src/kernels/cuda/sampler.cu:1312-1318`、`src/core/verify.cpp:3393-3397`。

## 根拠

- 環境変数の直接読み取りと値判定: `src/kernels/cuda/sampler.cu:1127-1135`。
- 通常 sampled sampler への適用、旧 sampler の非対応、greedy 除外: `src/kernels/cuda/sampler.cu:297-435,483-550,1260-1290`。
- coupled draft の設定・有効条件: `include/strata/core/coupled_draft.hpp:57-79`、`src/program/generate.cpp:653,3139-3140,3499`、`src/core/mtp.cpp:587-608,790,1245-1255`。
- Gumbel noise と抽選: `src/kernels/cuda/sampler.cu:67-81,412-434,520-550`。
- `docs/DETAILS.md:543-546` は `STRATA_SPEC_COUPLED=1` または `--coupled-draft` と `STRATA_SPEC_GUMBEL=1` が一部環境で accepted-draft rate を上げると記載しています。`docs/DETAILS.md:1445` の測定表は `STRATA_SPEC_COUPLED / STRATA_SPEC_GUMBEL` を組み合わせた比較で、Ryzen AI Max+ 395 / ROCm 7.14.1 では accepted drafts 52.8%→59.9%、output 41.1→44.9 tok/s、RTX 3060 では受理率 62.1%→66.9%→68.0% としています。複数設定をまとめた値なので、この環境変数単独の効果とは切り分けられません。
