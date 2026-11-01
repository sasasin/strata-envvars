# `--dspark-depth`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 engine CLI） |
| オプション | `--dspark-depth` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。1 未満は 1 に補正 |

## 役割

DSpark speculative decoding の各 round で採用・検証する draft 数の上限を指定します。既定値は 64 です。これはドラフト生成数そのものを直接止める設定ではなく、生成された候補から検証に進める先頭部分の上限です（`src/dsv41/ds4_main.cpp:165, 238-249`）。

## 使い方

pack と入力 token ID を指定する通常実行の例です。

```sh
strata-dsv41 --pack /models/maya-ds4 --ids 1,2,3 --n 128 --dspark-depth 8
```

## 値と既定値

- 省略時は 64（`src/dsv41/ds4_main.cpp:165`）。
- 指定値は `std::atoi` で整数化され、その結果に `std::max(1, ...)` が適用されます。0、負数、空文字列、整数に変換できない文字列は 1 になります。数値の後ろに整数以外の文字がある場合も、`atoi` が読み取った整数部分が使われます（`src/dsv41/ds4_main.cpp:1343`）。
- 同じ option を複数回指定すると、引数を左から走査するため最後の指定が有効です（`src/dsv41/ds4_main.cpp:1307-1315, 1343`）。
- 値を省略すると `--dspark-depth needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1309-1314`）。

## 実行時の動作

`round()` が DSpark を使うとき、採用数 `keep` を増やすループは、生成済み draft 数、出力可能な残り枠 `room - 1`、各 draft の confidence floor、累積 confidence 条件に加え、`g_spec_depth` 未満であることを要求します。採用した先頭 draft だけを `verify()` に渡します。したがって、この option は round ごとの検証候補数に上限を設けます（`src/dsv41/ds4_main.cpp:218-243, 244-249`）。

適用には `spec` が有効、`room > 1`、モデルの `draft_block() > 0` が必要です。`keep` が 0 のときは draft を検証せず通常の1 token step に進みます（`src/dsv41/ds4_main.cpp:218-223, 241-243, 264-270`）。通常の生成と server request、`--spec-eval` は同じ `round()` を呼ぶため、これらの経路でも共通のプロセス全体の上限として働きます（`src/dsv41/ds4_main.cpp:990-994, 1254-1258, 1526-1533`）。

## 適用条件と副作用

- `--dspark off` では speculative drafting が無効になり、この深さ上限は使われません。`--dspark none` は drafter をロードしない指定です（`src/dsv41/ds4_main.cpp:1332-1337`; `src/dsv41/ds4_model.hpp:52-55`）。
- `--dspark-block` は model 側で draft block 数を制限する別の上限です。実際に検証する数はそれにより作られる候補数、`--dspark-depth`、残り出力枠などのうち最も厳しい条件に制限されます（`src/dsv41/ds4_model.hpp:54`; `src/dsv41/ds4_model.cu:2350`; `src/dsv41/ds4_main.cpp:241-243`）。
- `--dspark auto` では Metal build は drafter をロードせず、GPU メモリ条件によっても自動で無効化される場合があります。その場合は上限値を指定しても speculative round に適用されません（`src/dsv41/ds4_model.cu:2326-2349`）。
- この option 自体がファイルやネットワークを操作する処理はありません。変更するのは speculative round で検証に進む draft 数です。これに伴う性能や出力速度の変化量は、ソースから一律には断定できません。

## 出力とエラー

値がある場合、この option 固有の出力はありません。parser は値の数値形式を厳密には検証せず、`atoi` の結果を 1 以上に補正します。値の欠落時は上記の stderr と終了コード 2 になります。`--help` の usage synopsis には `--dspark-depth` が載っていませんが、parser は受理します（`src/dsv41/ds4_main.cpp:101-109, 1343`）。

## 根拠

- parser、値変換、既定値: `src/dsv41/ds4_main.cpp:163-165, 1307-1315, 1342-1344`
- draft 採用条件と検証処理: `src/dsv41/ds4_main.cpp:218-270`
- 通常生成、server、spec-eval からの呼び出し: `src/dsv41/ds4_main.cpp:990-994, 1254-1258, 1526-1533`
- `--dspark` / `--dspark-block` の model 側条件: `src/dsv41/ds4_model.hpp:46-55`, `src/dsv41/ds4_model.cu:2326-2350`
- usage の記載範囲: `src/dsv41/ds4_main.cpp:101-109`
