# `strata-hy4 --all-logits`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、root） |
| オプション | `--all-logits` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると有効 |

## 役割

トークン列をオフラインで処理する際、通常は最後の prefill chunk の末尾位置だけで計算する logits を、同じ chunk 内の全位置について計算します。各位置の top-5 は標準出力に出ます。全 vocabulary の logits 行列そのものを標準出力へ出すオプションではありません。

## 使い方

```sh
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --all-logits --out ./hy4-all-logits
```

CUDA/HIP 版でモデルとトークン ID ファイルを指定して実行します。例の出力先は実行結果用のディレクトリです。

## 値と既定値

- 引数 parser は `--all-logits` の有無を boolean に設定します。値の変換や数値範囲の validation はありません。省略時は `false`、複数回指定しても `true` のままです（`engine/src/hy4flash/run/hy4_main.hip.cpp:351,491`）。
- このフラグに値を付ける構文はありません。未知の引数は `unknown arg` を stderr に出し、終了コード 2 で終了します（同 `:498-505`）。

## 実行時の動作

- オフライン実行では prefill を chunk 単位で進めますが、logits head を呼ぶのは最後の chunk です。通常は `first = T - 1` として末尾位置だけを計算するところ、このフラグが有効で speculative mode でなければ `first = 0` となり、最後の chunk の全 `T` 位置を計算します。したがって、入力列全体ではなく最後の chunk が対象です（`engine/src/hy4flash/run/hy4_main.hip.cpp:758-777`）。
- `head(T, first)` は `T - first` 行分の出力容量を確保し、その位置範囲の logits を計算します。容量が足りない場合は GPU logits buffer と `hfin` buffer を必要な行数まで再確保します（`engine/src/hy4flash/run/hy4_graph.hip.h:178-186,3455-3466`）。初期容量は 16 行で、全 logits 用に必要になれば拡張します（同 `:1481`）。
- 計算後、全行を GPU から host にコピーし、各行について位置番号と top-5 token ID / logits 値を標準出力へ出力します。通常の出力ファイル `top5.txt` にも同じ top-5 一覧を書きます（`engine/src/hy4flash/run/hy4_main.hip.cpp:89-97,772-788,1106-1109`）。
- `--all-logits` 単独では全 logits 行列をファイルに保存しません。`--dump` または `--save-logits` も指定した場合に、計算対象行列を `--out` で指定した場所の `logits.npy` に float32、形状 `(行数, vocabulary 数)` で書きます（`engine/src/hy4flash/run/hy4_main.hip.cpp:777`; NPY 書き込み処理は `engine/src/hy4flash/run/hy4_graph.hip.h:77-97`）。

## 適用条件と副作用

- `--serve` の場合、parser はフラグを受理しますが serve 設定へ渡さず、オフライン prefill の `first` 判定にも到達しません。そのため serve 実行ではこのフラグの効果はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611,758-770`）。
- `--draft dfly2` と `--gen N`（`N > 0`）を指定すると speculative mode になり、`first` の条件により `--all-logits` を指定しても末尾位置だけを計算します（同 `:701,769-770`）。
- 最後の prefill chunk 内の全位置分を計算・GPU から host へコピーするため、行列と処理量は対象行数および vocabulary 数に応じて増えます。GPU buffer は必要行数に応じて拡張されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:769-775`; `engine/src/hy4flash/run/hy4_graph.hip.h:178-185,3455-3466`）。
- オフライン実行では、フラグの有無にかかわらず `top5.txt` を `--out` の下に書きます。`--dump` / `--save-logits` を併用すると `logits.npy` も書き込みます（`engine/src/hy4flash/run/hy4_main.hip.cpp:777,1106-1109`）。

## 出力とエラー

- `--all-logits` に固有の validation error はありません。モデル指定がなくオフライン実行に入った場合は usage を stderr に出して終了コード 2 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-615`）。
- logits 行列の NPY 保存は `fopen` に失敗してもエラーを出さず、そのまま戻ります（`engine/src/hy4flash/run/hy4_graph.hip.h:85-86`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351,375-505` — `all_logits` の既定値、引数解析、未知引数の失敗経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611,701,758-777` — serve 分岐、speculative mode 判定、最終 prefill chunk の logits 範囲、host copy と保存条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-97,178-186,1481,3455-3466` — NPY writer、GPU buffer の動的拡張、head が計算する行範囲。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:89-97,1106-1109` — top-5 表示形式と `top5.txt` 出力。
