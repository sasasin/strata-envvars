# `strata --seed`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン。非Qwen3.5経路） |
| オプション | `--seed` |
| 別名 | なし |
| 値 | `S`: `std::atoll` で読み取られた符号付き整数を `uint64_t` に変換。範囲検証なし |

## 役割

非Qwen3.5モデルの生成時にサンプリングを有効にし、Philox 乱数の seed を指定します。乱数は seed と生成位置から決まるため、同じ設定・入力・実装上の条件で生成列を再現するために使えます。既定は greedy 生成で、`--seed` を指定すると `--greedy` を解除します。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --seed 42
```

`--seed` は `--tokens` を使う通常の生成で指定します。`--temperature` が 0 以下の場合は greedy 生成になります。

## 値と既定値

- 値は必須です。値を省略すると `--seed needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3843-3847`）。
- 既定値は `0` ですが、既定では `greedy = true` のため seed はサンプリングに使われません（`engine/src/program/generate.cpp:756-765`）。
- parser は `std::atoll` の戻り値を `uint64_t` に変換し、範囲・書式の検証をしません。したがって不正な数値文字列は `atoll` の変換結果（通常 0）、負数は符号なし値への変換結果として扱われます。範囲外値の挙動は保証されていません（`engine/src/program/generate.cpp:3881-3885`）。
- 同じオプションを複数回指定すると後の値が残ります。`--seed` と `--greedy` の両方を指定した場合も引数順に上書きされ、最後に処理された方が greedy/sampling の状態を決めます（`engine/src/program/generate.cpp:3881-3883`）。

## 実行時の動作

parser は seed を `Options` に格納すると同時に greedy を解除します。生成準備時に `Options` の greedy、seed、top-k、top-p、temperature を `SamplerParams` へ転送し、非serve生成ではサンプリング設定を stderr に表示します（`engine/src/program/generate.cpp:10635-10649`）。通常の生成ループは各生成位置を Philox の counter として設定して sampler を呼びます。Philox は seed と counter（生成位置）から draw を得るため、推測生成経路でも位置ごとの draw を一致させる設計です（`engine/src/program/generate.cpp:24398-24408`、`engine/src/kernels/cuda/sampler.cu:40-64,416-434`）。

`--greedy` は後続の `--seed` によって解除でき、逆に後続の `--greedy` はサンプリングを止めます。seed を指定しても `--temperature 0` 以下なら sampler は greedy として扱います。top-k / top-p / temperature は同じ `SamplerParams` に渡されます（`engine/src/program/generate.cpp:3881-3885,10635-10649`、`engine/include/strata/kernels/sampler.hpp:15-27`）。

`--serve` では CLI の `SamplerParams` はリクエスト生成には使われず、リクエストごとの `seed=N` キーで seed を受け取ります。キーを省略した場合は steady-clock 時刻を seed にします。したがって serve 起動時の `--seed` は個々の serve リクエストの seed を固定しません（`engine/src/program/generate.cpp:10641-10649,18824-18830,18921,18951-18966`）。

## 適用条件と副作用

- `strata-engine` の共通入口は、Qwen3.5 モデルと判定すると `engine/src/qwen35` の parser に引数をそのまま渡します（`engine/src/program/generate.cpp:3804-3818`）。Qwen3.5 側の通常の `--tokens` / benchmark 経路には CLI `--seed` の parser 分岐がなく、serve 以外では未知引数として usage を表示し終了コード 2 になります。Qwen3.5 の serve 起動では未知の `--` オプションを警告して無視するため、起動時の `--seed` は有効になりません（`engine/src/qwen35/q36_engine.cu:5339-5368,5405-5417`）。同エンジンの serve リクエスト seed は `GEN ... seed=N` キーで扱います（`engine/src/qwen35/q36_engine.cu:5025-5045,5169-5189`）。
- 非Qwen3.5の `--serve` では起動時 `--seed` はリクエスト単位の sampling に反映されません。リクエスト側で `seed=N` を指定してください（上記「実行時の動作」参照）。
- seed による再現性は sampler の乱数 draw を固定するものです。異なるモデル、入力、sampling 設定、ビルド・実行条件をまたいだ出力一致までは保証されていません。

## 出力とエラー

通常の非serve生成では sampling が有効で temperature が正の場合、stderr に temperature、top-k、top-p、seed が記録されます。greedy 状態または temperature が 0 以下なら `sampling greedy` と表示され、seed はログに出ません（`engine/src/program/generate.cpp:10641-10649`）。値そのものに対する専用の validation error はありません。値がない場合のエラーは「値と既定値」を参照してください。

## 根拠

- `engine/src/program/generate.cpp:756-765` — オプション状態と既定値。
- `engine/src/program/generate.cpp:3843-3847,3881-3885` — 値取得、変換、sampling/greedy 切替。
- `engine/src/program/generate.cpp:3804-3818` — Qwen3.5 へのモデル別振り分け。
- `engine/src/program/generate.cpp:10635-10649,24398-24408` — sampler への引き渡し、起動ログ、生成位置 counter。
- `engine/src/kernels/cuda/sampler.cu:40-64,416-434` — Philox の seed/counter 利用。
- `engine/src/program/generate.cpp:18824-18830,18921,18951-18966` — serve リクエストごとの seed と未指定時の seed。
- `engine/src/qwen35/q36_engine.cu:5339-5368,5405-5417` — Qwen3.5 CLI の引数処理と未知オプション経路。
- `engine/src/qwen35/q36_engine.cu:5025-5045,5169-5189` — Qwen3.5 serve リクエスト seed の処理。
