# `strata --temperature`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。サブコマンドなし） |
| オプション | `--temperature` |
| 別名 | なし |
| 値 | 浮動小数点数。有限かつ 0 以上 |

## 役割

通常の非サーバー実行で、候補 token の logit を温度でスケーリングし、サンプリング分布の集中度を調整します。温度 0 は greedy と同じ経路になります。温度が正でも既定の `--greedy` 状態は解除されないため、確率的サンプリングを使うには `--seed` を指定します。

## 使い方

```sh
# token ID を指定して実行し、seed 42 で温度 0.7 のサンプリングを行う
strata --tokens 1,2,3 --seed 42 --temperature 0.7
```

`--tokens` はこのビルドで必須の事前トークン化入力です。実際のモデル実行には既定 `pack/full` または適切な `--pack` も必要です。

## 値と既定値

- 省略時は `1.0` です。parser は値を `std::atof` で `float` に変換し、専用の重複指定拒否はありません。複数回指定した場合、引数走査で後に現れた値が残ります。
- 有限の 0 以上を受け付けます。負数または非有限値は `invalid sampling or resource parameter` を stderr に出して終了コード 2 で拒否されます。
- 値を省略すると `--temperature needs a value` を stderr に出し、parser 内で終了コード 2 になります。
- 温度 0 は sampler の greedy 経路です。正の値でも、通常実行では `--greedy` が既定で有効なため、`--seed` を指定しなければ greedy のままです。`--seed` は sampling を有効にし、後続の `--greedy` は再び greedy を指定します。

## 実行時の動作

通常実行では parser の温度を sampler parameter にコピーし、生成 token ごとに logits から token を選択します。サンプラーは `top-k` で候補を絞り、`top-p`（および有効な場合は `min-p`）を適用してから温度スケーリングした分布を作り、Philox の乱数で token を選びます。したがって `--temperature` は `--top-k` / `--top-p` と同じ選択処理に作用しますが、それらの候補制限を置き換えません。

`--greedy` が有効、または温度が 0 以下なら sampler は greedy kernel に進みます。正の温度で greedy が無効の場合にだけ確率的サンプリング経路を通ります。起動時の stderr には `sampling greedy` または温度・top-k・top-p・seed を含む sampling 設定が表示されます（非 serve 実行）。

`--serve` では温度はリクエストごとの `temperature=F` キーから設定され、キーがないリクエストは温度 0 の greedy です。起動時の `--temperature` は serve リクエストの温度設定には使われません。

## 適用条件と副作用

この値はエンジン内の token 選択に適用され、単独でファイルやネットワーク状態を変更しません。serve モードの各リクエストに対する値は、そのリクエストの `temperature=F` が担います。推奨温度や性能・出力品質への定量的効果は、確認したソースからは判断できません。

## 出力とエラー

- 値がない場合は parser が stderr に不足を表示して終了コード 2。
- 値が負または非有限の場合は `strata generate: invalid sampling or resource parameter` を stderr に出して終了コード 2。
- 不明な引数は `unknown argument: ...` と usage を stderr に出して終了コード 2。

## 根拠

- `engine/src/program/generate.cpp:756-765` — `Options` の `greedy=true`、`temperature=1.0f` などの初期値。
- `engine/src/program/generate.cpp:1280-1283` — help usage の `--greedy` 既定・`--seed` による sampling 有効化・sampling option の掲載。
- `engine/src/program/generate.cpp:3842-3848,3881-3885` — option loop、値不足時の終了、`--greedy` / `--seed` / `--temperature` の parser。
- `engine/src/program/generate.cpp:4268-4274` — 未知引数の stderr、usage、終了コード 2。
- `engine/src/program/generate.cpp:5267-5275` — 温度の有限性・非負 validation と共通エラー経路。
- `engine/src/program/generate.cpp:10635-10649` — sampler parameter への反映、非 serve 起動時の sampling 状態表示。
- `engine/src/program/generate.cpp:18824-18830,18901-18903,18951-18966` — serve のリクエスト単位 sampling option、温度未指定時 0、SamplerParams の組み立て。
- `engine/src/kernels/cuda/sampler.cu:384-435,1260-1289` — 候補選択後の温度スケーリングと、greedy / sampling kernel の分岐。
