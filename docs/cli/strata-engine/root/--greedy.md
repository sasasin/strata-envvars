# `--greedy`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--greedy` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常の生成経路で、次のトークンを確率抽選ではなく argmax（logit が最大の token ID）で選びます。この経路では `--greedy` を省略した場合も greedy です。サンプリングを有効にする `--seed` を指定した場合は、オプションの並び順にも注意してください。

## 使い方

```sh
# --model にモデルを指定し、token ID から greedy 生成する
strata --model MODEL --tokens 1,2,3 --greedy --max-new 16
```

## 値と既定値

- 値や別名はありません。parser はこの引数を見つけると `greedy` を真にします。フラグ自体に追加の値検証はありません。
- 既定値は真です。`--greedy` を付けなくても通常の生成は greedy になります。
- `--seed S` は seed を設定すると同時に `greedy` を偽にして sampling を有効化します。parser は引数を左から処理するため、`--greedy --seed 7` は sampling、`--seed 7 --greedy` は greedy です。後に現れた方のフラグが最終モードを決めます。同じフラグの反復にも同じ規則が適用されます。
- `--greedy` に値を続ける構文はありません。余分な値や `--greedy=...` は未知引数として扱われ、usage を stderr に出して終了コード 2 になります。

## 実行時の動作

通常の生成では parser の `greedy` と `seed` を sampler parameter にコピーし、各生成位置で `sample_tokens` を呼びます。sampler は `greedy` が真、または温度が 0 以下なら greedy kernel の経路を選び、候補の argmax を返します。そのため `--temperature 0` 以下でも sampling は greedy になります。`--seed` が有効で温度が正の場合は sampling 経路になり、seed が抽選系列に使われます。`--top-k` と `--top-p` は greedy を解除しません。

`--serve` では要求ごとに `temperature` から sampler parameter を作ります（省略時の要求温度は 0）。この要求別設定が使われるため、root の `--greedy` は serve 要求の sampling mode を指定する手段ではありません。Qwen3.6 family の parser にも `--greedy` の受理箇所がありますが、そこでは token 入力が常に greedy であるとして何もしません。この文書は索引上の `strata-engine/root`、すなわち `engine/src/program/generate.cpp` の parser scope を対象とします。family parser の同名項目は [`qwen36` scope の文書](../../qwen36/--greedy.md)を参照してください。

## 適用条件と副作用

- 非 serve の通常生成では、起動時に stderr へ `strata generate: sampling greedy` と出力します。sampling が選ばれた場合は温度・top-k・top-p・seed を表示します。serve はこの起動時 sampling 表示を行いません。
- `--greedy` 自体はファイルや設定を書き換えません。生成 token は通常の生成処理の出力経路に渡されます。
- sampler の実装は CUDA の `sampler.cu` にあります。この調査では GPU を実行して挙動を実測していません。

## 出力とエラー

`--greedy` 単独に固有の validation error はありません。余分な値や誤記など parser が認識しない引数では `unknown argument: ...` を stderr に出し、usage を表示して終了コード 2 で終了します。生成中に sampler token の readback に失敗した場合は別の実行時エラーとして終了コード 1 になります。

## 根拠

- `engine/src/program/generate.cpp:756-765` — option state と既定値（`greedy = true`）。
- `engine/src/program/generate.cpp:1280-1282` — help 表示上の説明と関連 sampling 引数。
- `engine/src/program/generate.cpp:3842-3849,3881-3885` — 左からの引数処理、`--greedy` と `--seed` の値・状態変更。
- `engine/src/program/generate.cpp:4268-4274` — 未知引数の stderr、usage 表示、終了コード 2。
- `engine/src/program/generate.cpp:10635-10649` — sampler parameter への反映、温度条件、serve 以外での sampling 状態表示。
- `engine/src/program/generate.cpp:18827,18951-18966` — serve 要求の温度既定値と要求別 sampler parameter。
- `engine/src/program/generate.cpp:24398-24408` — 通常生成位置での sampling 呼び出しと token readback 失敗経路。
- `engine/src/kernels/cuda/sampler.cu:1273-1284` — `greedy` または温度 0 以下で greedy kernel を選ぶ分岐。
- `engine/src/qwen35/q36_engine.cu:5339-5364` — Qwen3.6 family parser の別 scope で `--greedy` を no-op として受理する箇所。
- `docs/cli/README.md:1036-1048,1106,1244-1260` — `strata-engine` root と qwen36 の階層、および両 scope の索引登録。
