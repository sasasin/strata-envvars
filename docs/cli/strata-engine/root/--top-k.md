# `--top-k`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数。Terminal CLI の `strata` wrapper とは別） |
| オプション | `--top-k N` |
| 別名 | なし |
| 値 | 整数。通常経路では `N >= 0`。サンプラーが実際に使う候補数は最大 64 |

## 役割

サンプリング時に、logit の高い順に残す候補トークン数を指定します。通常の `src/program/generate.cpp` 経路で `SamplerParams` に設定され、通常 decode と speculative verifier に渡されます（`src/program/generate.cpp:7043-7048,16167-16170`）。

## 使い方

非 Qwen3.6 モデルで、トークン ID 列を入力して seed 付き sampling を使う例です。`<pack-dir>` と `<token-ids>` は利用環境の値に置き換えます。

```sh
strata --pack <pack-dir> --tokens <token-ids> --seed 42 --top-k 12
```

エンジンの usage は `--top-k N` として掲載しています（`src/program/generate.cpp:878-881`）。`--top-k` 自体は sampling を有効化しません。通常の初期状態は greedy で、`--seed` が greedy を解除します（`src/program/generate.cpp:423-427,2455-2459`）。

## 値と既定値

- 省略時は `20`（`src/program/generate.cpp:423-427`）。
- parser は `std::atoi` で読み込み、通常経路では負数を拒否します。負数を含むサンプリング／リソース設定エラーは stderr に `strata generate: invalid sampling or resource parameter` を出し、終了コード `2` で終了します（`src/program/generate.cpp:2457,3352-3359`）。
- `--top-k` の値が欠けている場合は stderr に `--top-k needs a value` を出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420,2457`）。
- 0 は受理され、サンプラーでは「制限なし」と同じく 64 候補になります。1〜63 は指定数、64 以上は 64 候補です。さらに語彙サイズが 64 未満なら語彙数までに制限されます（`src/kernels/cuda/sampler.cu:336-340`）。
- parser は `atoi` を使い、整数の厳密な書式検証を個別には行いません（`src/program/generate.cpp:2457`）。

## 実行時の動作

サンプリング経路では、logit bias や反復 penalty を適用した値から上位候補を選び、その候補列に top-p を適用し、続いて min-p、temperature、乱数による選択へ進みます。top-k の同値 logit は token ID の小さい順に選ばれます（`include/strata/kernels/sampler.hpp:1-6,15-29`; `src/kernels/cuda/sampler.cu:342-345,354-364,383-390`）。

通常の起動時は `greedy = true` です。`--seed` を指定すると sampling に切り替わり、`--greedy` は greedy に戻します。両方を指定した場合は parser が引数を左から処理するため、後に現れた方が最終状態を決めます。また `--temperature 0` でもサンプラーは greedy 選択になります（`src/program/generate.cpp:423-427,2455-2459,7043-7048`; `include/strata/kernels/sampler.hpp:19`; `src/kernels/cuda/sampler.cu:1350`）。

`--serve` ではサンプラー設定はリクエストごとに設定されます。起動時の `--top-k` は `SamplerParams` に入りますが、serve の通常リクエスト sampling は request fields から別の `req_sp.top_k` を設定するため、起動時指定がリクエスト値を一律に上書きするとは確認できません（`src/program/generate.cpp:7043-7050,12294-12300,13933-13952`）。

## 適用条件と副作用

- 通常の非 serve 生成では、sampling が有効なときに候補リスト幅を制御します。既定の greedy、`--greedy`、または temperature が 0 以下の経路では top-k による確率分布の絞り込みは行われません（`src/program/generate.cpp:423-427,2455-2459,7051-7057`; `src/kernels/cuda/sampler.cu:1350`）。
- 選択された値は speculative verifier にも設定され、MTP draft sampling が有効な場合はそちらにも渡されます（`src/program/generate.cpp:16167-16170`）。
- Qwen3.6 ファミリーは `--native` / `--model` のモデル情報によって専用 parser に振り分けられます（`src/program/generate.cpp:2393-2407`）。その parser には CLI `--top-k` の分岐がなく、serve 以外では未知引数として usage を出し終了コード `2` になります。serve では `--serve` を parser が先に読んで serve mode になっている場合、未知の `--...` 引数を「このエンジンの option ではない」と stderr に出して値とともに読み飛ばす処理があります（`src/qwen35/q36_engine.cu:3742-3748,3782-3795`）。このファミリーの GEN リクエストには別途 `top_k=N` フィールドがあり、既定 20 で sampling に使われます（`src/qwen35/q36_engine.cu:3011-3016,3452-3467`）。
- オプション自体はファイルやネットワークを操作しません。候補選択は CUDA sampler の処理で行われます（`src/kernels/cuda/sampler.cu:336-364`）。

## 出力とエラー

非 serve の sampling 設定は stderr に `strata generate: sampling ... top_k=...` と表示されます。表示される値も 0 または 64 超の場合は 64 に正規化されています。greedy または temperature 0 以下では `strata generate: sampling greedy` と表示されます（`src/program/generate.cpp:7049-7057`）。

通常 parser で負数を指定すると前述の終了コード `2` の validation error になります。オプション値の欠落も終了コード `2` です。Qwen3.6 の未知 option 時の挙動は上記の専用 parser の節を参照してください。

## 根拠

- parser の既定値、usage、値取得、validation: `src/program/generate.cpp:418-427,878-881,2416-2421,2455-2459,3352-3359`
- sampling parameter への設定、ログ、serve 時のリクエスト単位設定、speculative verifier/draft への適用: `src/program/generate.cpp:7043-7057,12294-12300,13933-13952,16167-16170`
- 候補数の上限・候補選択・sampling chain: `include/strata/kernels/sampler.hpp:1-6,15-29`; `src/kernels/cuda/sampler.cu:336-390,1350`
- Qwen3.6 への分岐と専用 parser: `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3011-3035,3742-3795`

調査は parser と利用箇所をソース上で確認して実施しました。同一 revision の既存 CLI `--help` は補助実行していません。build、テスト、GPU 実行、性能測定は行っていません。
