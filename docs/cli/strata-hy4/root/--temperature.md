# `strata-hy4 --temperature`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root、CUDA/HIP） |
| オプション | `--temperature` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で変換される値 |

## 役割

`--draft dfly2` を有効にしたオフライン生成で、確率サンプリングの温度を指定する。温度が 0 以下なら greedy（最大 logit の token を選択）、正なら候補 token の確率分布を温度で調整して選ぶ。`--serve` のリクエスト温度は標準入力の `GEN ... temperature=...` で指定する別経路であり、この CLI 引数の値は ServeOpts に渡されない（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-566`、`engine/src/hy4flash/run/hy4_serve.hip.h:6-8,137-168`）。

## 使い方

```sh
strata-hy4 --model model.strata --tokens prompt-ids.txt --gen 32 --draft dfly2 --temperature 0.7
```

`--draft dfly2` と `--gen` が正数のとき `spec_mode` になり、温度を含む sampling 設定が speculative generation に渡る（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,401-416,701,992-1007`）。

## 値と既定値

- 引数は必須。値がない場合、`ERR --temperature needs a value` を stdout に出して終了コード 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,416`）。
- `atof` の戻り値を `float` に変換して設定し、有限性・正数範囲などの明示的な検証はない（`engine/src/hy4flash/run/hy4_main.hip.cpp:416`）。不正な数値文字列は `atof` の変換結果（通常 0）として扱われ、空文字列も 0 になる。オプションを複数回指定すると、引数走査中に後の値で上書きされる（同 `:375-383,416`）。
- 未指定時の `SampleOpts::temperature` は `0.f`。したがって既定は greedy（`engine/src/hy4flash/run/hy4_dfly2.hip.h:25-34`）。

## 実行時の動作

parser は値を `cli_samp.temperature` に格納する。オフライン生成で `draft == "dfly2"`、`gen > 0`、`--dfly-alloc-only` なしの場合に限り `spec_mode` が有効になり、温度が 0 以下か、他の penalty 設定があるかに応じて `cli_samp` が sampler に渡される。`temperature <= 0` かつ penalty なしなら argmax 経路、正の温度なら確率 sampling 経路を使う（`engine/src/hy4flash/run/hy4_main.hip.cpp:701,992-1007`、`engine/src/hy4flash/run/hy4_spec.hip.h:197-203,240-249`）。

確率分布の計算では候補を最大 64 個に絞った後、logit 差を温度で割って指数化し、正規化する。続いて `--min-p`、`--top-p` の順で候補を絞る（`engine/src/hy4flash/run/hy4_dfly2.hip.h:59-105`）。`--temperature` と併用する場合、これらの他の sampling option によって最終候補も変わる。

正の温度での抽選には `std::mt19937_64` が使われ、`--seed` が指定されていればその値、未指定または 0 なら `20261120` が初期 seed になる（`engine/src/hy4flash/run/hy4_main.hip.cpp:420,997-1000`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:166`）。

`--serve` の場合、main は ServeOpts を作って server 経路へ進む。CLI の `cli_samp` は ServeOpts に設定されず、各 `GEN` リクエストの `temperature=...` がそのリクエストの `SampleOpts` に設定される（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-566`、`engine/src/hy4flash/run/hy4_serve.hip.h:6-8,129-168`）。また、`--draft` の既定は `auto` だが、コメント上は offline CLI runs では drafter を無効にするため、CLI の speculative generation で温度を使うには `--draft dfly2` が必要（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,701`）。

## 適用条件と副作用

- `--draft dfly2 --gen N`（`N > 0`）の speculative offline generation で有効。`--draft` の既定 `auto` の CLI 経路では `spec_mode` が成立しない（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,701`）。
- DFly2 なしの通常 `gen > 0` 経路は token を `k_argmax` で選び、`cli_samp.temperature` を参照しない（`engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1074`）。`--serve` では前述のとおり request 側の値を使う。
- 温度 0 以下は greedy として処理される（`engine/src/hy4flash/run/hy4_dfly2.hip.h:26,33,75-78`）。負数を拒否する validation はない。正の有限値の範囲チェックも確認できない。
- 不正な文字列や NaN / infinity を与えた場合に有用なエラーへ変換する処理は確認できない。これらの値に対するサンプリング結果はソースから確定できないため、利用可能な値として推奨しない。
- `--temperature` 自体によるファイル、ネットワーク、環境変数の変更は確認できない。

## 出力とエラー

不足値は stdout に `ERR --temperature needs a value` を出して終了コード 2。不明な引数は stderr に `unknown arg <値>` を出して終了コード 2（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,498-505`）。温度値の形式や範囲を理由とする専用エラーは実装されていない（同 `:416`）。

## 根拠

- parser・値の変換・引数不足・未知引数: `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,416,498-505`
- 既定値と greedy 判定: `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`
- offline speculative mode の条件と sampler への受け渡し: `engine/src/hy4flash/run/hy4_main.hip.cpp:363,701,992-1007`; `engine/src/hy4flash/run/hy4_spec.hip.h:197-203,240-249`
- 温度による分布計算と他フィルターの順序: `engine/src/hy4flash/run/hy4_dfly2.hip.h:59-105`
- greedy の通常生成経路: `engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1074`
- serve のリクエスト単位設定: `engine/src/hy4flash/run/hy4_main.hip.cpp:544-566`; `engine/src/hy4flash/run/hy4_serve.hip.h:6-8,129-168`

