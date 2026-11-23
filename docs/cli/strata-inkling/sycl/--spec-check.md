# `--spec-check`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--spec-check` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

同じモデルとプロンプトから通常の greedy decode と DSpark speculative decode を順に実行し、生成 token 列が一致するかを調べる診断モードです。一致しなければ両 token 列も表示し、終了コード 3 を返します。モデルの推論処理を実行するため、help 的な静的確認ではありません。

## 使い方

```sh
strata-inkling-sycl --model ./model.strata --spec-check
```

生成数は `--gen`（既定値 32）、入力 token 列は `--prompt-tokens`（alias `--prompt-ids`。既定値 `1,2,3,4,5,6,7,8`）で指定できます。

## 値と既定値

`--spec-check` は値を受け取りません。parser はこの指定を boolean に設定し、繰り返し指定しても有効状態のままです。parser にこのフラグ固有の validation はありません。モデルの指定が空なら通常の usage を stderr に出して終了コード 1 となり、モデルのロードまたは runner 初期化に失敗した場合もエラーを stderr に出して 1 で終了します。(`engine/src/inkling2/sycl/ink_sy_main.cpp:101-124`, `:166-168`, `:171-203`)

## 実行時の動作

モデルをロードして runner を初期化した後、`--spec-check` が有効なら `run_greedy_decode` を `use_spec=false` と `use_spec=true` で各1回呼びます。両方とも slot 0 をリセットし、同じ prompt を prefill してから最大 `--gen` 個の出力 token を集めます。speculative 経路は DSpark drafter で最大7 token を提案し、target の結果と照合して受理数を数え、不一致部分の slot 状態を rollback します。残り context が足りない場合や提案が得られない場合は通常の1 token decode に進みます。(`engine/src/inkling2/sycl/ink_sy_main.cpp:31-98`, `:236-242`; `engine/src/inkling2/sycl/ink_sy_runner.h:837-838`)

2つの token 列を比較し、stdout に `[SPEC-CHECK]` の一致数、完全一致または不一致、両経路の decode throughput、DSpark の提案受理統計を表示します。不一致時は続けて `plain:` と `spec :` の token 列を出して終了コード 3、一致時は次の処理へ進みます。`--bench` や `--par-sweep` も同時指定されている場合、それらの処理も後続で実行されます。(`engine/src/inkling2/sycl/ink_sy_main.cpp:243-255`, `:257-288`)

`--no-dspark` と併用すると runner の DSpark 機能が無効になります。この場合も比較用の2回目の decode は `use_spec=true` で呼ばれますが、helper は `R.use_dspark` が false なら通常の逐次 decode に切り替えるため、DSpark の有効性・一致性を検査する実行にはなりません。結果表示ラベルは引き続き `dspark` です。モデル自体に DSpark がない場合も runner の `use_dspark` は false になります。(`engine/src/inkling2/sycl/ink_sy_main.cpp:201`, `:240-249`; `engine/src/inkling2/sycl/ink_sy_runner.h:223-230`; `engine/src/inkling2/sycl/ink_sy_main.cpp:53-61`)

## 出力とエラー

正常な比較結果と不一致時の token 列は stdout です。初期化・モデル処理の前段で検出されるモデル指定欠落、probe/load、vision load/encode、runner init の失敗は stderr に出力され、コード上は終了コード 1 です。`run_greedy_decode` 自体は forward failure 時に `false` を返しますが、`--spec-check` 側はその戻り値を確認せず比較へ進みます。その失敗後の比較結果は正常な parity 判定として解釈できません。(`engine/src/inkling2/sycl/ink_sy_main.cpp:41-43`, `:166-203`, `:240-253`)

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — 既定値、オプション parser、関連する `--gen` と prompt の値。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-203` — モデル必須条件、load、runner 初期化と DSpark 有効化。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:31-98` — greedy decode の初期化、逐次 fallback、draft/verify と token 収集。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:236-255` — 比較、結果出力、不一致時の token 列と終了コード。
- `engine/src/inkling2/sycl/ink_sy_runner.h:223-230`, `:837-838` — runner の DSpark 有効条件と draft の context 境界。
