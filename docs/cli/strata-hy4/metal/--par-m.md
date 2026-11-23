# `strata-hy4-metal --par-m`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--par-m` |
| 別名 | なし |
| 値 | 整数。既定値は `0` で、正の値を指定すると比較対象の末尾トークン数 `W` になる。ソースに範囲検証はない。 |

## 役割

プロンプト末尾の `W` トークンについて、1 トークンずつ処理した場合と `W` トークンをまとめて処理した場合の logits を比較する Metal runner の診断モードです。各行の logits が bit 単位で一致するか、最大絶対差はいくつか、top-1 が一致するかを出力します。通常の生成ではなく、prefill 後に比較して終了します。

## 使い方

入力トークンファイルに16個以上のトークンがある例です。`--par-m` の値は入力トークン数以下にしてください。

```sh
strata-hy4-metal --model model.strata --tokens ids.txt --par-m 16
```

## 値と既定値

`--par-m` は `atoi` で整数に変換され、初期値は `0` です。省略時、`0`、負数、または整数として読めない値では `par_m > 0` の比較処理に入りません。オプションを複数回指定すると、parser が順に代入するため最後の値が使われます。変換結果の範囲、入力トークン数との大小は検証されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491, 1504-1506, 1574, 1857`）。

## 実行時の動作

モデルをロードしてトークンファイルを読み込み、通常の prefill を終えた後に比較します。`W = --par-m`、開始位置を `p0 = T0 - W` とし、末尾の各位置を順番に1トークンずつ実行して logits を保存します。その後、同じ範囲を1チャンクとして実行し、対応する logits 行ごとに bit 単位の一致、最大絶対 logits 差、top-1 一致を比較します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1701-1705, 1789-1817, 1857-1879`）。

比較ブランチは `--bench-m` や通常の生成処理より先に評価され、最後に `return 0` します。そのため `--gen` を同時に指定しても、このブランチでは生成しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1857-1882, 1898-1944`）。一方、`--draft` が既定の `auto` で、モデルに DFly2 の重みがあり、runner の chunk が16以上で、`--all-logits` と画像入力を使わない場合、parser 後の `spec_mode` 判定に `par_m > 0` が含まれるため、比較前に DFly2 の初期化も行われます。`--draft off` などでその条件を外せます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1501, 1601-1602, 1755-1772`）。

## 適用条件と副作用

正の `W` がプロンプト長 `T0` を超えると `p0` が負になります。ソースはこの条件を検査せず、負の位置を使って `forward_chunk` に渡すため、その入力では有効な比較範囲は保証されません。`W` の上限検証もありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1857-1869`; `forward_chunk` は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1295`）。

このモードはMetal版 `strata-hy4-metal` の parser に定義されています。比較中は推論処理を実行し、標準出力と標準エラーに診断結果を出します。比較ブランチからは `top5.txt` の通常終了時書き込みや後続の生成処理へ進みません。なお、prefill 中に `--dump` または `--save-logits` も指定した場合は、通常どおり `out_dir/logits.npy` の保存処理が先に実行されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1802-1809, 1857-1880, 1978-1981`）。

## 出力とエラー

各行の比較結果を標準エラーに `[par-m] row ...` 形式で出し、集計を標準出力に `[par-m] W=...` 形式で出して `0` を返します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1871-1880`）。`--par-m` 専用の範囲エラーや値の検証はありません。共通の引数処理では、モデル未指定時に usage を標準エラーへ出して `2`、未知の引数ではメッセージを出して `2` を返します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1614`）。モデルや runner の初期化失敗など、比較前の共通処理が失敗した場合はその経路のエラーを出して終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1620-1623, 1762-1771`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491, 1504-1506, 1574` — `par_m` の初期値、引数の整数変換、parser 定義。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1772` — `par_m` を含む DFly2 適用条件と初期化。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1857-1880` — 比較処理、出力、正常終了。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1295` — 比較から呼ぶ `forward_chunk` が受け取る位置とトークン数。
