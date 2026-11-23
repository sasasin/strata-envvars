# `--min-p`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--min-p` |
| 別名 | なし |
| 値 | 数値1つ。`atof` で `float` に変換 |

## 役割

DFly2 speculative generation の確率サンプリングで、最大確率候補に対する相対確率が指定値を下回る候補を除外します。通常の CLI オフライン生成は既定で draft が `off` であり argmax 経路を使うため、この値を使うには DFly2 経路を有効にする必要があります（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,701,992-1000,1018-1071`）。

## 使い方

```sh
strata-hy4 --model model.strata --tokens prompt.ids --gen 32 --draft dfly2 --temperature 0.8 --min-p 0.05
```

この例は CUDA/HIP runner のオフライン生成で DFly2 speculative 経路を選び、温度を正にして確率サンプリングを有効にする構文例です。モデル・入力ファイルは実行環境に合わせて指定してください。CLI での `--draft` 既定値は `off` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,416-420,701`）。

## 値と既定値

値は `atof` で読み、`SampleOpts::min_p` に格納されます。既定値は `0.f` です。範囲検証や `[0, 1]` へのクランプはありません。繰り返し指定すると、引数を処理した順で同じフィールドに代入され、最後の値が使われます。数値として解釈できない文字列は `atof` の結果である `0` になり、負値と `0` は min-p の足切りを無効にします（`engine/src/hy4flash/run/hy4_main.hip.cpp:365,375-383,419`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`）。

正の値では、確率上位候補の最大確率 `p[0]` に値を掛けた閾値を用います。値が `1` を超えても拒否されず、先頭候補を残して後続候補を除外します（`engine/src/hy4flash/run/hy4_spec.hip.h:79-92`）。

## 実行時の動作

parser が値を `cli_samp.min_p` に設定し、`--draft dfly2` と `--gen` が正の場合、通常の speculative 経路では `cli_samp` が `Spec::run` に渡されます。sampling 分布の処理順は履歴 penalty、top-k（最大64候補）、temperature softmax、min-p、top-p、再正規化です。min-p の判定は `p[i] >= min_p * p[0]` の候補を連続して残します（`engine/src/hy4flash/run/hy4_main.hip.cpp:701,992-1000`、`engine/src/hy4flash/run/hy4_spec.hip.h:197-211,398-430`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:39-40,79-105`）。

温度が `0` 以下で penalty もない場合、`SampleOpts::greedy()` により sampler 設定自体が speculative sampler に渡されず、argmax の greedy 経路となります。したがって `--min-p` 単独では sampling に切り替わりません（`engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`、`engine/src/hy4flash/run/hy4_main.hip.cpp:997-1000`、`engine/src/hy4flash/run/hy4_spec.hip.h:240-250`）。

`--ab` 比較経路では通常生成側も speculative 側も `cli_samp` を `Spec::run` に渡さず、このオプションはその経路の分布に反映されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:914-965,975-985`）。`--serve` では起動時の `cli_samp` を `ServeOpts` にコピーしません。serve の各 `GEN` 要求は `min_p=<数値>` という要求単位のキーを読み取ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577`、`engine/src/hy4flash/run/hy4_serve.hip.h:159-185`）。

## 適用条件と副作用

- CLI オフライン生成では `--draft dfly2` と正の `--gen` によって `spec_mode` が選ばれる必要があります。`--draft` の既定値は CLI runs で `off` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,701`）。
- 温度が正のときに候補集合を絞り、最終的な抽選分布に作用します。ファイルや設定の書き換えは行いません（`engine/src/hy4flash/run/hy4_spec.hip.h:79-105`）。
- speculative 生成の出力として token ID は標準出力に表示され、`<out>/gen_ids.txt` に書き込まれます。`--min-p` 固有のファイル副作用ではありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:1006-1017`）。

## 出力とエラー

値が不足した場合、共通の `nxt()` が標準出力に `ERR --min-p needs a value` を出して終了コード `2` で終了します。不正な数値文字列や範囲外値に対する専用の validation error、警告、クランプ処理は確認できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,419`）。

speculative generation 自体が失敗すると、`spec: <理由>` を標準エラーに出して終了コード `1` になります。これは min-p 値固有の失敗経路ではありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1005`）。

## 根拠

- parser、値の読込、値不足時の処理、CLI の draft 既定値: `engine/src/hy4flash/run/hy4_main.hip.cpp:363,375-383,416-420`
- `SampleOpts` の既定値と greedy 判定: `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`
- speculative mode の条件とサンプラー引き渡し: `engine/src/hy4flash/run/hy4_main.hip.cpp:701,992-1005`
- 分布の処理順と min-p の閾値: `engine/src/hy4flash/run/hy4_spec.hip.h:197-211,398-430`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:39-40,79-105`
- `--ab` 経路・serve での扱い: `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,914-985`、`engine/src/hy4flash/run/hy4_serve.hip.h:159-185`
- 生成結果の標準出力・ファイル出力と speculative failure: `engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1017`
