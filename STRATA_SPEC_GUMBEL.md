# `STRATA_SPEC_GUMBEL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

サンプラーが通常の inverse-CDF 抽選を行う代わりに、Gumbel-max 法で token を選ぶかを制御します。各候補 token の確率 `p_i` を、その token ID・seed・位置から決めた指数乱数 `E_i` で割り、`p_i / E_i` が最大の候補を選びます。候補集合が変わっても共通 token の乱数が変わらないため、coupled draft と target の候補集合が異なる場合に選択を一致させやすくする意図です。

この変数は coupled draft が無効でも、CUDA sampler の通常の非 greedy 抽選に適用されます。したがって単独で設定しても、確率分布は保ったまま、seed と位置に対する具体的な抽選結果が変わります。coupled draft との組み合わせでは draft 側にも同じ選択法を渡します。

## 値と判定

値を数値や真偽値として parse せず、共通 helper `env_flag()` が文字列全体を判定します。

| 環境変数の状態 | Gumbel 選択 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 文字列がちょうど `0` | 無効 |
| 上記以外の非空文字列（例: `1`, `true`, `false`, `00`, `0abc`, ` 0`） | 有効 |

大文字小文字、空白、数値としての妥当性は検査しません。`env_flag()` は `e != nullptr && *e != '\0' && std::strcmp(e, "0") != 0` を返します。`gumbel_env()` の結果は関数内 `static const bool` に保存されるため、初回評価後にプロセス環境を書き換えても反映されません。CUDA sampler のプロセス内で最初に `gumbel_env()` を呼ぶ `sample_tokens()` または `coupled_draft_stage()` の時点で値が確定します。

## 有効になる条件

- 通常の sampler では、CUDA sampler の `sample_tokens()` が `p_in.gumbel || gumbel_env()` を設定します。`temperature > 0` かつ `greedy == false` の抽選で Gumbel 分岐を使います。`greedy` または `temperature <= 0` の場合は greedy 経路に進み、このフラグは選択結果に使われません。
- `STRATA_SPEC_COUPLED` または `STRATA_SPEC_PROB` により coupled 用の draft 処理が構成される場合、`coupled_draft_stage()` は環境判定値を device 側の `SamplerParams.gumbel` にコピーします。coupled draft sampling の merge kernel は同じ Gumbel 選択を使います。通常の coupled draft 自体は `STRATA_SPEC_COUPLED`（または `--coupled-draft`）が必要です。
- `sample_tokens_spec()` の専用 rejection-sampling 経路は `STRATA_SPEC_GUMBEL` を直接判定せず、verify 用の抽選は Philox の一様乱数による累積確率選択です。この専用経路から通常 `sample_tokens()` に fallback した場合、その呼び出し側の Gumbel 判定は適用されます。
- 変数の直接読み取りは `src/kernels/cuda/sampler.cu` にあります。CMake ではこのファイルが CUDA kernel library に含まれ、gfx906 の HIP 互換構成では CUDA-shaped source を HIP 経由でビルドします。SYCL 用の複製 `sycl/src/kernels/cuda/sampler.dp.cpp` には Gumbel の環境変数参照がなく、通常の SYCL sampler は別経路です。`docs/DETAILS.md` は ROCm での実測も掲載していますが、その測定環境が現 HEAD のどの HIP ビルド経路に対応するかは、ここで確認したソースから特定できません。

## 実行時の詳細

通常 sampler は各行について、penalty、top-k、top-p、min-p、temperature を適用して候補確率を作ります。Gumbel が有効なら、候補ごとに `gumbel_exp(seed, counter + row, token_id)` を計算し、確率をその値で割った比の最大を選びます。指数乱数の hash 入力は `(seed, counter, token ID)` で、counter は `p.counter + row` です。Gumbel が無効なら Philox の一様乱数から inverse-CDF 抽選します。split sampler と one-block sampler の両方にこの選択分岐があります。

coupled draft では host が環境を読むのではなく CUDA sampler 内の `gumbel_env()` が値を取得し、stage kernel が request の device-side sampler params に設定します。draft merge は draft vocabulary の subset index を元の token ID に戻して Gumbel hash に使うため、target 側と同じ token ID が同じ noise を得ます。

この値を読み取る処理自体はログを出しません。無効値に対する警告や fallback もありません。既定では無効です。

## 文書・測定値との照合

`docs/DETAILS.md` は `STRATA_SPEC_COUPLED=1` と併用した場合に draft と target の候補集合で同じ token noise を共有する仕組みとして説明しています。また、Ryzen AI Max+ 395 / Radeon 8060S / Linux / ROCm 7.14.1 での測定（UD-Q4_K_XL、`--spec 4 --mtp`、temperature 1.0、top-p 0.95、top-k 20 等）と、RTX 3060 の測定を掲載しています。これらは文書に記載された条件下の値です。現 HEAD のコードでは通常の `sample_tokens()` も環境変数を直接読むため、フラグの作用範囲は docs の coupled 用途の説明より広いです。ROCm 測定条件と現 HEAD の実装経路との対応は、ソース上の読み取り箇所だけからは特定できません。

## 根拠

- 共通 env 判定と初回値のキャッシュ: `src/kernels/cuda/sampler.cu:1108-1115`。
- 通常 sampler への適用と greedy 分岐: `src/kernels/cuda/sampler.cu:1239-1254`。
- split sampler の Gumbel / inverse-CDF 選択: `src/kernels/cuda/sampler.cu:411-432`。
- one-block sampler の Gumbel / inverse-CDF 選択: `src/kernels/cuda/sampler.cu:520-545`。
- Gumbel hash と token ID を含む乱数生成: `src/kernels/cuda/sampler.cu:66-80`。
- coupled stage が値を params に転送: `src/kernels/cuda/sampler.cu:806-813,1317-1321`。
- coupled draft の候補 ID を hash に使う箇所: `src/kernels/cuda/sampler.cu:534-540`。
- MTP から coupled draft sampler を呼ぶ箇所: `src/core/mtp.cpp:999-1009`。
- CMake の CUDA sampler 登録と backend 構成: `CMakeLists.txt:58-72,333-345`。
- 専用 rejection-sampling 経路が通常の inverse-CDF 抽選を使う箇所: `src/kernels/cuda/sampler.cu:1347-1362,963-982`。
- 設計説明と測定条件: `docs/DETAILS.md:114-126`。
