# `--top-p`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--top-p` |
| 別名 | なし |
| 値 | 浮動小数点数 `F`。有限値で `0 < F <= 1` |

## 役割

sampling 時に、`--top-k` で選ばれた候補を上位から累積確率 `F` に達するまで残す nucleus（top-p）フィルターの閾値です。候補選択はペナルティ適用後・temperature 適用前に行われます。

## 使い方

```sh
strata --tokens "1,2,3" --seed 42 --top-p 0.9
```

`--pack` を省略した場合は `pack/full` が使われます。`--tokens` はこの build の通常生成で必要です。`--seed` は sampling を有効にします。エンジンの usage は `strata generate --pack DIR --tokens "1,2,3" [options]` と案内しています（`src/program/generate.cpp:808-812`）。

## 値と既定値

- 既定値は `0.95` です（`src/program/generate.cpp:422-427`）。
- parser は次の引数を `std::atof` で `float` に変換します。`--top-p` の後に値がなければ `--top-p needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2417-2421,2458`）。
- 全 sampling/resource パラメータの検査で、有限値かつ `0 < top_p <= 1` であることを要求します。違反時は `strata generate: invalid sampling or resource parameter` を stderr に出し、終了コード `2` で終了します。`NaN`、無限大、0、負数、1超は拒否されます（`src/program/generate.cpp:3352-3358`）。
- 同じオプションを複数回指定しても専用の重複エラーはなく、引数走査中に後の値が前の値を置き換えます（`src/program/generate.cpp:2413-2417,2458`）。
- `1` は parser では有効値ですが、sampler では top-p フィルターを無効にします（`include/strata/kernels/sampler.hpp:15-20`）。

## 実行時の動作

parser が設定した値は `SamplerParams::top_p` にコピーされ、各生成位置の sampler 呼び出しへ渡されます（`src/program/generate.cpp:7043-7048,16034-16038`）。sampling カーネルは、ペナルティ適用後の logits から `top_k` 個までの候補を降順に選び、その候補内で安定化した指数値を正規化して累積します。累積値が `top_p` 以上になった候補までを残し、`min_keep`（既定 `1`）より少なくならないようにします。その後 `min_p`、temperature、抽選の順で処理します（`src/kernels/cuda/sampler.cu:342-400`、`include/strata/kernels/sampler.hpp:15-20`）。従って `--top-k` と組み合わせた場合、top-p の累積対象は語彙全体ではなく top-k の候補集合です。

`--greedy` は既定で有効であり、`--top-p` だけを指定しても top-p 抽選にはなりません。`--seed` は `greedy` を無効化し、引数走査順で後から `--greedy` を指定すれば再び greedy になります。さらに `--temperature 0` でも sampler は greedy 経路を使い、top-p を適用しません（`src/program/generate.cpp:423-427,2455-2459`、`src/kernels/cuda/sampler.cu:1252-1263`）。

`--serve` では起動時の `SamplerParams` ではなく要求ごとの設定を使います。テキスト要求に `top_p=F` があればその値を設定し、省略時は要求側の既定 `1.0` です。要求の `temperature` も省略時 `0` で greedy になるため、serve で top-p 抽選を使うには要求側で正の `temperature` も指定します。したがって起動引数の `--top-p` が serve 要求の top-p として使われることは、確認した実装からは読み取れません（`src/program/generate.cpp:7049-7050,12294-12300,12341-12343,13933-13942`）。

## 適用条件と副作用

- 単発生成では非 greedy の sampling 経路で有効です。sampler の既定実装は split 経路で、環境設定や制約に応じて one-block または旧 sampler に分岐しますが、いずれも `SamplerParams` を受け取ります（`src/kernels/cuda/sampler.cu:1116-1120,1264-1289`）。
- オプション自体は候補集合と抽選分布を変え、ファイルを書き換える処理はありません。実際に生成 token を読み戻す CUDA 処理が失敗した場合は `strata generate: reading the sampled token back failed: ...` を出し、終了コード `1` で終了します（`src/program/generate.cpp:16037-16043`）。sampler の kernel launch エラーは `sample_tokens launch: ...` を stderr に出し、終了コード `1` で終了します（`src/kernels/cuda/sampler.cu:1292-1295`）。

## 出力とエラー

非 serve の実行では、sampler 設定の診断として stderr に `sampling temperature=... top_k=... top_p=... seed=...` が出ます。ただし greedy の場合は `sampling greedy` と表示されます（`src/program/generate.cpp:7051-7057`）。不正値・値の欠落の出力と終了コードは「値と既定値」を参照してください。

## 根拠

- parser と既定値・usage: `src/program/generate.cpp:422-427,808-812,2417-2421,2455-2459`
- validation と失敗経路: `src/program/generate.cpp:3352-3358`
- sampler への受け渡しと生成呼び出し: `src/program/generate.cpp:7043-7057,16034-16043`
- sampling の候補選択・top-p 累積処理と分岐: `src/kernels/cuda/sampler.cu:342-400,1116-1120,1239-1297`
- sampler パラメータの既定値: `include/strata/kernels/sampler.hpp:15-20`
- serve 要求単位の設定: `src/program/generate.cpp:12294-12300,12341-12343,13933-13942`

この調査では checkout 内のソースを確認しました。同一 revision の既存 CLI `--help` や Release artifact は実行・照合していません。
