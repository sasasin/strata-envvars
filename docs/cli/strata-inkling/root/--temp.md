# `--temp`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP、トップレベル） |
| オプション | `--temp` |
| 別名 | なし |
| 値 | 数値文字列。`std::atof` で `float` に変換される |

## 役割

トップレベルの直接生成モードで、次 token を選ぶ際の temperature を指定します。値が 0 以下なら greedy（logit 最大の token を選択）、正なら temperature を適用した確率からサンプリングします。値は CLI の直接生成にだけ使われ、`--serve` の request sampling や `--bench` などの評価モードには反映されません（`engine/src/inkling2/ink_main.cpp:377,540-550,571-575,595-605`; `engine/src/inkling2/ink_serve.h:52-67,85-104`）。

## 使い方

```sh
strata-inkling --native ./model.strata --prompt-ids 200002,200004,100,200010 --gen 8 --temp 0.7
```

## 値と既定値

- 値は `std::atof` で読み取られ、`float` に変換されます。コード上に範囲検査や有限値検査はありません。数値として解釈できない文字列は `atof` の変換結果（通常 0）となり、greedy 経路になります（`engine/src/inkling2/ink_main.cpp:484-485`; C/C++ ランタイムの変換詳細は Strata ソースの調査対象外）。
- 省略時は `cli_temp` の初期値 `0.0f` が使われ、greedy です（`engine/src/inkling2/ink_main.cpp:377,595-597`; `engine/src/inkling2/ink_serve.h:66,85-91`）。
- 値を省略すると parser の `next()` が `missing value after --temp` を stderr に出し、終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:379-384,484-485`）。同じオプションを複数回指定した場合、ループ内で `cli_temp` が順に代入され、最後の指定値が残ります（同 `:379-385,484-485`）。

## 実行時の動作

parser は値を `cli_temp` に保存します。直接生成経路では `SampleOpts` の `temperature` に設定し、各生成 step の `sample_logits()` に渡します（`engine/src/inkling2/ink_main.cpp:484-485,575-605`）。temperature が 0 以下なら最大 logit の token を選びます。正なら上位 token を最大 128 個に絞り、既定 `top_k=64` までの logits を temperature で割って softmax 相当の確率を作り、その分布から乱数抽選します（`engine/src/inkling2/ink_serve.h:52-67,85-104,120-129`）。直接生成の乱数器 seed は固定値 `42` です（`engine/src/inkling2/ink_main.cpp:595-601`）。

この値は `--serve` の request parser が読む `temperature=...` とは別です。serve mode は CLI の `cli_temp` を渡さず `run_serve_loop()` に進み、各 request の sampling 設定は protocol key/value から設定されます（`engine/src/inkling2/ink_main.cpp:571-573`; `engine/src/inkling2/ink_serve.h:307-319`）。また `--bench` は `cmd_bench()` に別の引数群を渡し、`cli_temp` を参照しません（`engine/src/inkling2/ink_main.cpp:547-550`; benchmark 内の greedy argmax: 同 `:225-241`）。

## 適用条件と副作用

- `--temp` の設定が生成結果に反映されるのは、parser の mode 選択を通過して直接 CLI 生成に到達した場合です。`--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval`、`--dump-ref`、`--bench` は先に個別処理へ分岐します（`engine/src/inkling2/ink_main.cpp:544-550`）。
- 直接生成では model の読み込み、backend 初期化、slot 確保、prompt prefill と decode が行われます。生成 token ID はカンマ区切りで stdout に逐次出力されます。EOS/EOT token で生成を止めます（同 `:556-579,586-613`）。
- `--serve` を指定した場合、この option 自体の値は serve request に引き継がれません。serve request 側の `temperature` が sampling を決めます（`engine/src/inkling2/ink_main.cpp:371-378,571-573`; `engine/src/inkling2/ink_serve.h:307-319`）。

## 出力とエラー

`--temp` 固有の値検証エラーや温度範囲エラーは見つかりませんでした。数値変換後の値は直接生成 sampling に使われます。直接生成中の model open、backend init、slot allocation、prefill、decode の失敗は、それぞれ stderr にエラーを出して終了コード 1 を返します。option の値変換そのものは明示的な失敗経路を持ちません（`engine/src/inkling2/ink_main.cpp:484-485,556-579,591-613`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:377` — temperature の省略時初期値。
- `engine/src/inkling2/ink_main.cpp:379-384,484-485` — 引数消費、値変換、欠落値の失敗。
- `engine/src/inkling2/ink_main.cpp:544-550,571-575,595-613` — 各モードの分岐と、直接生成への適用・出力。
- `engine/src/inkling2/ink_serve.h:52-67,85-104,120-129` — greedy 判定、temperature による sampling の実装。
- `engine/src/inkling2/ink_serve.h:307-319` — serve request が別途 temperature を読み取る処理。
