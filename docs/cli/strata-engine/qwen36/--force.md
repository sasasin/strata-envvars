# `strata` / `strata-q36` `--force`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 10 進 token ID の列。カンマまたは空白で区切る |

## 役割

`--tokens` による単発デコードで、モデルの greedy 出力を次の入力として使う代わりに、指定した token ID 列を順に入力する teacher-forcing 用オプションです。各位置ではその時点の greedy token を出力し、次の推論状態には指定 token を投入します。最後の指定 token を投入した後の greedy 出力も含めて確認できます。

## 使い方

```sh
strata-q36 --model model.gguf --tokens 1,2,3 --force 4,5
```

同じ専用 parser は、Qwen3.6 の GGUF を選んだ `strata` からも呼び出されます。モデルの選択と引数転送は `engine/src/program/generate.cpp:3817`、専用入口は `engine/src/qwen35/q36_main.cpp:5` です。

## 値と既定値

- `--force` は値を 1 個取ります。値がない場合は `strata-q36: --force needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352,5366`）。
- 値は `strtol(..., 10)` で整数列として読み取られ、カンマと ASCII 空白は区切りとして読み飛ばされます（`engine/src/qwen35/q36_engine.cu:4604-4615`）。例: `--force 4,5,6` または `--force '4 5 6'`。
- オプションを省略した場合は強制入力なしです。複数回指定した場合は parser が同じ文字列変数へ代入するため、最後の指定値が残ります（`engine/src/qwen35/q36_engine.cu:5340,5366`）。
- 数値として読めない箇所に達すると、その位置で解析を止めます。先頭から数値を読めない値や空文字列は空列になり、強制入力なしと同じ扱いです。たとえば `12x,13` は `12` まで読み取って終了します。ソースにはこの形式をエラーにする validation はありません（`engine/src/qwen35/q36_engine.cu:4606-4615`）。
- このオプション固有の既定値や token ID の範囲検査はありません。強制列が空でなければ、生成数は列の長さ + 1 に上書きされます（`engine/src/qwen35/q36_engine.cu:5595-5597`）。

## 実行時の動作

`--force` が非空の token 列に解析され、`--tokens` も有効な列を与えた場合、prompt を処理してから各ステップの greedy 出力を記録します。次のステップへ進むときは、強制列にまだ token があればその token を `E.process` に渡し、列を使い切った後は直前の greedy 出力を渡します。したがって出力 `gen:` には、強制列を入力した後の最終 greedy 出力までが含まれます（`engine/src/qwen35/q36_engine.cu:5595-5597,5610-5612,5639-5653`）。

相互作用:

- この処理は `--tokens` の単発デコード経路にあります。`--serve` は先に server loop へ戻り、ベンチマーク指定も先にベンチマーク処理へ戻るため、これらのモードで受理された `--force` は参照されません（`engine/src/qwen35/q36_engine.cu:5561-5564,5595-5597`）。
- 強制列が非空のときは `--n` / `--max-new` の値より列長 + 1 が優先されます（`engine/src/qwen35/q36_engine.cu:5342,5356,5365,5595-5597`）。
- MTP の単発生成分岐は `forced.empty()` を条件に含むため、強制列がある場合はその分岐を使わず、通常の 1 token ごとの処理に進みます（`engine/src/qwen35/q36_engine.cu:5614-5618`）。

## 適用条件と副作用

この値は `--serve` のリクエスト設定や環境変数には転送されず、専用 engine の引数 parser が保持するだけです。対象処理は `--tokens` モードです。解析された token ID は `E.process` へ渡されますが、`--force` 列について ID がモデル語彙の範囲内かを検査する処理は確認できません（`engine/src/qwen35/q36_engine.cu:5595-5597,5639-5649`）。範囲外 ID の下流での扱いは、この parser と呼び出し箇所の確認範囲からは判断できません。

## 出力とエラー

正常な単発デコードでは stdout に `gen:` と生成 token ID 列、stderr に prompt / generation の計時情報が出ます（`engine/src/qwen35/q36_engine.cu:5650-5657`）。欠落値は parser で終了コード 2 になります。値の数値列としての検証エラーや、`--force` 専用の警告は見当たりません。空列に解析された場合は強制入力としては扱われず、`--n` / `--max-new` による通常生成へ進みます（`engine/src/qwen35/q36_engine.cu:4604-4615,5595-5597`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:17-18` — engine のモードと `--force IDS` が tokens/reference interface に属すること。
- `engine/src/qwen35/q36_engine.cu:5340-5418` — parser の値取得、`--force` 登録、欠落値・未知引数の処理。
- `engine/src/qwen35/q36_engine.cu:4604-4615` — token ID 列の分割・整数変換と不正文字での停止。
- `engine/src/qwen35/q36_engine.cu:5595-5657` — 空列判定、生成数の上書き、MTP 分岐、強制 token の投入、出力。
- `engine/src/program/generate.cpp:3817`、`engine/src/qwen35/q36_main.cpp:5` — `strata` からの専用 parser 呼び出しと standalone entry point。
