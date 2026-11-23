# `strata-hy4 --parity-m`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--parity-m` |
| 別名 | なし |
| 値 | カンマ区切りの chunk 幅 `M`（正の整数を指定。実装上の上限は 16） |

## 役割

同じ prompt の末尾位置について、幅 `M` の一括 forward と、各位置を 1 token ずつ forward した結果の logits を比較する診断用オプションです。default の `gemv4+moe_dec4` と `gemv16+moe_dec16` の両方で top-1 一致数、bit 単位の一致数、最大 logit 差、KL divergence を表示します。生成結果を得る通常運転用ではありません。

## 使い方

```sh
strata-hy4 --model model.strata --tokens prompt.ids --parity-m 1,4,8
```

`--model` で HY4 モデルを、`--tokens` で token ID の入力ファイルを指定します。上の幅は例であり、実際には後述の prompt 長・chunk 条件を満たす幅を指定してください。

## 値と既定値

- 値は必須です。`--parity-m` の値は `std::string` に保存され、カンマ位置で分割した各部分を `atoi` で整数化します（`engine/src/hy4flash/run/hy4_main.hip.cpp:371,443,826-831`）。別名はありません。
- 省略時は空文字のままで parity 比較ブランチに入りません（同 `:371,821`）。値として空文字を渡した場合も同じです。
- 各幅の上限は 16 で、最大幅 `Wmax` が 16 を超えると拒否されます。prompt token 数 `T0` は `Wmax + 16` 以上、runner の chunk `r.Tc` は `Wmax` 以上である必要があります（同 `:832-835`）。chunk は `--chunk` と GPU に応じたメモリ計画で決まります（同 `:488,648,692`）。
- parser は各項目の形式や下限を個別検証しません。`atoi` で整数化できない項目は 0 になります。正の幅をカンマで区切って指定してください。幅の重複は除去されず、重複幅の比較が繰り返されます（同 `:826-831,862-863`）。

## 実行時の動作

parser が値を保持し、通常の offline 起動でモデルと runner を初期化して prompt 全体の prefill を終えた後に parity 分岐へ入ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:443,648-705,749-790,821`）。この分岐では expert vcache を flush して凍結し、幅リストを解析します（同 `:821-831`）。

まず prompt 最終位置の `M=1` forward を 4 回行い、最初の結果と後続 3 回の同一性を表示します。次に比較対象の末尾 `Wmax` 位置を逐次 1 token ずつ forward して基準 logits を保存します。各指定幅 `W` ごとに、2 種類の kernel 上限設定（4 と 16）で prefix を復元し、末尾 `W` token を一括 forward します。その logits を逐次実行の対応位置と比較し、top-1 一致数、bit-identical 行数、最大絶対差、mean/max KL を出力します。各幅・各設定の一括 forward と head は 5 回計時され、benchmark 時間と profiling 情報も stderr に出ます（同 `:837-909`）。

この分岐は通常の生成処理へ進まず `0` で終了します（同 `:911-912`）。従って `--gen` を併記してもこの経路では生成しません。`--serve` は server 起動後に戻る別経路で parity 分岐へ到達せず、`--load-only` もモデル load 後に先に終了します（同 `:544-611,658-665`）。`--trace-m` が正なら trace 分岐が parity より前に実行され、その分岐から終了します（同 `:793-817`）。

## 適用条件と副作用

- 対象は索引上 `strata-hy4` とされる CUDA/HIP 実装です。parser と parity 処理は `engine/src/hy4flash/run/hy4_main.hip.cpp` にあり、Metal / SYCL 実装の同名 option を示すものではありません（索引 `docs/cli/README.md:1277-1282`、実装 `engine/src/hy4flash/run/hy4_main.hip.cpp:334,443,821-912`）。
- 通常の offline モデル実行、prompt prefill、GPU forward が必要です。`Wmax > 16`、`T0 < Wmax + 16`、または `r.Tc < Wmax` の場合は診断メッセージを stderr に出し、status 2 で終了します（同 `:832-835`）。
- option 自体がファイルを書き出す処理はありません。ほかの `--dump` / `--save-logits` を指定すると、parity 分岐より前の prefill で `--out` ディレクトリの `logits.npy` に保存する経路があります（同 `:769-778`）。
- `--parity-m` の受理後もモデル読み込みと prefill は先に行われます。従って診断条件の失敗でも、その前段のモデル・GPU 初期化や prefill は実行済みです（同 `:648-705,749-790,832-835`）。

## 出力とエラー

- 1 token 再実行間の差は stdout に `[determinism]` 行として出力され、各幅の比較結果は `[parity]` 行として出力されます。benchmark 時間は stderr の `[bench]` 行です（`engine/src/hy4flash/run/hy4_main.hip.cpp:841-852,872-883,907-909`）。
- 幅・prompt・chunk 条件を満たさない場合は stderr に `parity: need W <= 16, chunk >= W and a longer prompt` を出して status 2 を返します（同 `:832-835`）。parity 中の逐次または一括 forward が失敗すると、該当箇所で status 1 を返します（同 `:845-846,854-855,865-869`）。
- 幅が空・不正・0 以下の場合の明示的な拒否処理はありません。`atoi` による変換後の値をそのまま使うため、有効な比較結果は保証されません（同 `:826-835,862-909`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:371,443` — 値の格納と parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,658-705,749-790` — serve / load-only の分岐、runner 初期化と prompt prefill。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:793-817,821-835` — trace 分岐の優先、parity の前提条件と vcache 処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:837-912` — 基準・一括 logits 計算、比較、計時、出力、終了。
- `docs/cli/README.md:1277-1282` — `strata-hy4` root scope に当該リンクがあること。索引は配置確認にのみ使用。
