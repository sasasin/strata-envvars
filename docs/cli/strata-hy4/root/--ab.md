# `strata-hy4 --ab`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--ab` |
| 別名 | なし |
| 値 | 整数として `atoi` で読み取る比較ラウンド数 |

## 役割

Hy4-Flash の生成時に、通常の greedy decode と DFly2 speculative decode の速度・生成トークン列を同一プロンプトで比較する。指定した正のラウンド数だけ両方式を交互に実行し、速度比や生成列の一致 prefix などを表示する。

## 使い方

```sh
# model.strata と tokens.txt を使い、両方式を3ラウンド比較する
strata-hy4 --model model.strata --tokens tokens.txt --gen 32 --draft dfly2 --ab 3
```

## 値と既定値

- 値は必須で、次の argv を `atoi` で整数に変換する。既定値は `0`。
- 明示的な範囲検証やエラー処理はない。`0`、負数、整数に変換できない文字列は `ab_rounds > 0` の条件を満たさず、A/B 比較ループを実行しない。数値の一部だけを含む文字列は `atoi` の変換規則に従う。
- 値を省略すると `ERR --ab needs a value` を stdout に出し、終了コード `2` で終了する。

## 実行時の動作

parser は `--ab` の値を `ab_rounds` に格納するだけで、比較を実行するのは `ab_rounds > 0 && spec_mode` の場合である。`spec_mode` は `--draft dfly2`、`--gen` が正、かつ `--dfly-alloc-only` ではない場合に成立する。したがって `--ab` だけでは比較モードにならず、条件を満たさない場合は通常の実行経路へ進む。

比較経路では prompt prefill 後に VRAM expert cache を flush して凍結し、最後の最大16 prompt token を再実行して状態を復元する。その後、各 round で通常 greedy decode と DFly2 decode を同じ prompt・設定から実行し、token/s、speedup、生成 token 数、同一 prefix 長などを stdout に出し、DFly2 の詳細統計を stderr に出す。これは実際にモデルを複数回実行する比較処理であり、単なる計画表示ではない。

`--ab-sab` も指定すると、各 round の通常比較に加えて、draft をランダム置換する sabotage 設定の DFly2 実行を追加し、結果を stdout に出す。`--spec-exact` や `--spec-inv` などの speculative 設定も比較経路に引き継がれる。比較後は通常の生成分岐を通らず、共通の後処理へ進む。`top5.txt` は `--out` のディレクトリ（既定 `.`）に書き込まれる。prefill 中に `--dump` または `--save-logits` が有効なら `logits.npy` も保存される。比較分岐自体は `gen_ids.txt` を書かない。

## 適用条件と副作用

- 対象は `strata-hy4` の CUDA/HIP 実装 `engine/src/hy4flash/run/hy4_main.hip.cpp`。索引上の `strata-hy4-metal` は別コマンドスコープであり、この文書の対象外。
- 実行にはモデル読み込み、prompt prefill、GPU 上の複数回 decode が必要。モデル初期化や prefill が失敗すれば比較ループに到達しない。
- `--ab-sab` 単独、または `--ab` が正でない場合、sabotage 比較も起動しない（sabotage 処理は A/B ループ内にある）。
- 比較分岐の `restore`、greedy の `forward_chunk`、または speculative run が失敗すると、stderr にエラーを出して終了コード `1` となる。

## 出力とエラー

- 各通常比較ラウンドは stdout に `[ab]` 行を出力し、`--ab-sab` を併用したラウンドは追加で `[ab-sab]` 行を出力する。speculative の詳細レポートは stderr。
- `--ab` の値がない場合は stdout に `ERR --ab needs a value`、終了コード `2`。
- 比較中の状態復元失敗は stderr の `ab restore: ...` と終了コード `1`。greedy decode 失敗は `forward: ...`、speculative decode 失敗は `spec: ...` を stderr に出し、いずれも終了コード `1`。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:373-384` — `ab_rounds` の既定値、引数不足時の出力と終了コード、次引数の取得。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:401-410, 431-432, 485-505` — `--draft`、`--gen`、`--ab`、`--ab-sab` の parser 定義、未知引数の失敗経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701-705, 914-920` — `spec_mode` の成立条件、A/B 分岐、cache 凍結と prompt 状態復元の準備。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:929-990` — 復元、greedy/DFly2 の反復比較、`--ab-sab` の追加実行、出力とエラー処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:777-778, 1002-1017, 1106-1109` — prefill 時の logits 保存条件、通常 speculative 経路の `gen_ids.txt` 保存、共通後処理の `top5.txt` 保存。
- `docs/cli/README.md:1279-1283` — `strata-hy4` のトップレベル (`root/`) と本オプションの索引上の配置。
