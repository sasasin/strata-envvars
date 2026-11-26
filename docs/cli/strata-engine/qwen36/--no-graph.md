# `--no-graph`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata-q36`、または Qwen3.6 モデル選択時の `strata` |
| オプション | `--no-graph` |
| 別名 | なし |
| 値 | なし（フラグ） |

## 役割

Qwen3.6 engine の CUDA Graph を使わず、対象の計算本体を通常の stream launch で実行します。graph 有効時との速度差はこのソース調査では測定していません。

## 使い方

```sh
# Qwen3.6 専用 engine でトークン列を処理し、graph を使わない
strata-q36 --model model.gguf --tokens '1,2,3' --no-graph
```

`strata` から Qwen3.6 parser に渡す場合も同じフラグです。Qwen3.6 engine の parser は `--model` / `--native` などとともにこのフラグを受け付けます（`engine/src/qwen35/q36_engine.cu:5339-5372`）。

## 値と既定値

値は取りません。parser 内の `graph` は既定で `true` で、`--no-graph` を指定すると `false` に設定されます。値の validation はありません。複数回指定しても同じ `false` の代入を繰り返すだけです。後から graph を再有効化する対になる CLI フラグは、この parser 範囲では定義されていません（`engine/src/qwen35/q36_engine.cu:5344-5347,5371`）。

## 実行時の動作

parser の `graph` 値は engine 作成時に `E.use_graph` へ渡されます（`engine/src/qwen35/q36_engine.cu:5466-5475`）。`graph_run` は `use_graph` が false のとき graph の capture / instantiate / replay を行わず、渡された処理本体をそのまま呼びます（`engine/src/qwen35/q36_engine.cu:3612-3635`）。通常の単一 token decode と batch row の window はこの経路で graph wrapper を通ります（`engine/src/qwen35/q36_engine.cu:3699-3710,3762-3765,3799-3802`）。MTP の draft/verify でも graph wrapper が使われますが、同じ `use_graph` 判定が適用されます（`engine/src/qwen35/q36_engine.cu:3992-4006`）。

CPU expert pool を使う main hybrid 配置になった場合は、host が各 layer に参加するため、`--no-graph` の指定有無にかかわらず main engine の graph は無効になります。また MTP graph も無効化されます（`engine/src/qwen35/q36_engine.cu:4344-4349`）。

## 適用条件と副作用

このオプションは Qwen3.6 専用 parser の設定です。別の `--no-token-graph` も parser にありますが、これは同じ `graph` 変数を無効化します（`engine/src/qwen35/q36_engine.cu:5357,5371`）。索引では別項目として登録されているため、本書では別名として扱いません。

graph を有効にしたまま CUDA Graph instantiate に失敗した場合、`volta_forever_active()` 条件下では診断を stderr に出し、以降の処理を stream launch に切り替えます（`engine/src/qwen35/q36_engine.cu:3621-3630`）。それ以外の instantiate エラーおよび graph launch など `CK` で検査される CUDA エラーは、stderr に失敗内容を出して終了コード 1 で終了します（`engine/src/qwen35/q36_engine.cu:82-89,3631-3635`）。`--no-graph` は instantiate/replay の経路を避けますが、通常の CUDA 処理に起因するエラーまでは抑止しません。

## 出力とエラー

`--no-graph` 自体に専用の成功メッセージや失敗条件はありません。未知の引数は usage を stderr に出して終了コード 2 になります（`engine/src/qwen35/q36_engine.cu:5412-5417`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5344-5372` — `graph` の既定値と `--no-graph` / `--no-token-graph` の parser 分岐。
- `engine/src/qwen35/q36_engine.cu:3612-3635` — graph 有効時の capture・instantiate・launch と、無効時の直接実行、instantiate fallback。
- `engine/src/qwen35/q36_engine.cu:3699-3710,3762-3765,3799-3802,3992-4006` — decode、batch rows、MTP の graph wrapper 利用。
- `engine/src/qwen35/q36_engine.cu:4344-4349,5466-5475` — hybrid 配置時の graph 無効化と parser 設定の engine への反映。
- `engine/src/qwen35/q36_engine.cu:82-89,5412-5417` — CUDA エラー出力と終了、未知引数の usage / 終了コード。
