# `--no-token-graph`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family parser、または `strata-q36` |
| オプション | `--no-token-graph` |
| 別名・同等表記 | `--no-graph`（同じ bool を同じ値に設定する。索引では別リンク） |
| 値 | なし。フラグ指定でグラフ実行を無効化 |

## 役割

Qwen3.6 engine の CUDA graph 利用を無効にし、各処理を通常の stream 上で直接実行します。ソースの parser では `--no-token-graph` と `--no-graph` が同じ `graph` bool を `false` にします（`src/qwen35/q36_engine.cu:3741-3765`）。この Qwen3.6 専用 parser は、`strata` がモデル GGUF の architecture を調べて `qwen35moe` なら呼び出すほか、独立実行ファイル `strata-q36` にも使われます（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:776-794`）。

## 使い方

```sh
strata --model /models/qwen3.6.gguf --no-token-graph --tokens '1,2,3' --n 32
```

同じフラグは独立実行ファイルでも受け付けます。

```sh
strata-q36 --model /models/qwen3.6.gguf --no-token-graph --tokens '1,2,3' --n 32
```

`strata` でこの parser に切り替わる条件は、モデル header の architecture が `qwen35moe` であることです。その他のモデルでは通常の engine parser が使われます（`src/program/generate.cpp:2393-2408`）。

## 値と既定値

値を取りません。既定値はグラフ有効（`graph = true`）で、指定すると `graph = false` になります（`src/qwen35/q36_engine.cu:3735-3752`）。明示値、数値範囲、複数回指定の検証はありません。重ねて指定しても bool を `false` にするだけです。直後に値らしい引数を置く構文ではなく、その語は別引数として処理されます。

## 実行時の動作

parser の結果は `E.use_graph` に設定されます（`src/qwen35/q36_engine.cu:3817-3818`）。通常は `graph_run` が初回に CUDA stream の処理を capture して graph executable を作り、以降 graph launch します。`use_graph` が false の場合は capture / graph launch をせず、その場で処理本体を呼び出します（`src/qwen35/q36_engine.cu:2368-2379`）。この分岐は単一 token の decode（`g1`）、batch row の graph（`run_graph_key` 経由）、verify window など複数の呼び出しで使われます（`src/qwen35/q36_engine.cu:2451-2454`、`2504-2507`、`2541-2544`、`2733-2738`）。

## 適用条件と副作用

このフラグは Qwen3.6 parser でだけ認識されます。CMake では `strata-q36` と Qwen3.6 family library の登録が `STRATA_HIP_GFX906` でない場合に限られます（`CMakeLists.txt:776-795`）。

CPU expert pool を使う hybrid 実行では、main layers が hybrid の場合に engine が `E.use_graph = false` に上書きします。この条件では本フラグの指定は実効上重複します。MTP 側も hybrid 設定で graph を無効化します（`src/qwen35/q36_engine.cu:2888-2893`）。その他の実行では、本フラグにより上記の graph capture/replay が行われず、処理本体が各呼び出しで直接実行されます。速度やメモリ使用量への定量的効果はこの調査では測定していません。

## 出力とエラー

このフラグ自体に専用の出力・validation error はありません。parser が未対応の引数を受けた場合は usage を stderr に表示して status 2 を返します。usage の表記は `--no-graph` ですが、parser は `--no-token-graph` も受理します（`src/qwen35/q36_engine.cu:3763-3795`）。`--model` がない場合も stderr にエラーを出し status 2 です（同 `:3797`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3765` — parser、既定値、`--no-token-graph` と `--no-graph` の同一動作。
- `src/qwen35/q36_engine.cu:2368-2379` — graph の capture / instantiate / launch と無効時の直接実行。
- `src/qwen35/q36_engine.cu:2451-2454`, `2504-2507`, `2541-2544`, `2733-2738` — decode、batch row、verify 等で graph 実行関数を使う箇所。
- `src/qwen35/q36_engine.cu:3817-3818`, `2888-2893` — parser 値の engine への反映と hybrid 時の上書き。
- `src/program/generate.cpp:2393-2408`, `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:776-795` — model family による切替、独立 executable、build 条件。

索引は `--no-token-graph` と `--no-graph` を別の文書リンクとして掲載していますが、Qwen3.6 parser では両方が同じ bool に作用します。索引は変更せず、この文書では同等表記として記録しました。
