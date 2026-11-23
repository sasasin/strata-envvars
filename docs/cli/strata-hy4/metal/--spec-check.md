# `--spec-check`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--spec-check` |
| 別名 | なし |
| 値 | なし（flag） |

## 役割

Metal 版の HY4-Flash で DFly2 の投機的デコードを行う際、受理した各 draft 行の logits を1 tokenずつ再計算し、まとめて計算したときの対応行と bitwise 一致するか調べる診断用 flag です。値の検証・補正や不一致時の生成中断は行いません。

## 使い方

```sh
# DFly2 を含むモデルで、入力 token 列から greedy 生成しながら投機計算の行一致を記録
strata-hy4-metal --model model.strata --tokens prompt_ids.txt --gen 32 --spec-check
```

## 値と既定値

値を取りません。指定時に `SpecCfg::check` を `true` にし、未指定時は `false` です。数値範囲などの validation はありません。parser はこの flag を見つけると次の引数を消費せず処理を続けます。根拠: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1556-1565`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-586`。

## 実行時の動作

投機的デコードの各検証後、受理された経路の logits を保存し、同じ経路を1 tokenずつ再計算します。各再計算行を元の検証行と全語彙ぶん `memcmp` で比較し、不一致なら差分の最大絶対値と位置などを stderr に出します。診断処理のため GPU forward と head の再実行が追加されます。根拠: `engine/src/hy4flash/metal/hy4_metal_spec.h:897-915`。

不一致は `chk_bad` に数えられ、1回の `Spec` 実行につき先頭12件まで `[check] ... row differs ...` の詳細が出力されます。最後の `[spec] check` 集計には再計算行数と bitwise 不一致行数が出ます。不一致そのものは `finish = "error"` にせず、ここで生成を中断しません。再計算中の `forward_chunk` が失敗した場合は `finish = "error"` となり、通常の spec エラー経路に進みます。根拠: `engine/src/hy4flash/metal/hy4_metal_spec.h:901-917,977`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1930-1943`。

## 適用条件と副作用

- 通常実行では、`--gen`、`--bench-m`、または `--par-m` のいずれかが正で、`--draft off` でなく、モデルに DFly2 tensors があり、chunk が16以上、`--all-logits` でなく、画像入力がない場合に `spec_mode` になります。実際に `Spec::run` が呼ばれるのは生成側の分岐です。`--bench-m` と `--par-m` はそれぞれベンチマーク／window parity の分岐を通るため、flag を付けてもこの比較処理には入りません。根拠: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1769,1857-1896,1929-1943`。
- `--serve` では `SpecCfg` が serve 設定に渡されます。サービス側で DFly2 が有効で、生成上限が正、画像入力なしの場合に spec 経路が選ばれます。greedy では比較しますが、temperature・penalty などを使う確率的モードでは `prob_mode` が true となり、比較ブロックの `!prob_mode` 条件により再計算・比較は行われません。根拠: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1656`、`engine/src/hy4flash/metal/hy4_metal_serve.h:233-254,509-522`、`engine/src/hy4flash/metal/hy4_metal_spec.h:722-723,897`。
- 条件を満たさない実行で flag を指定しても parser は受理しますが、チェック処理は呼ばれません。Metal runner では `--draft dfly2` が不可能な条件を stderr に警告する分岐がありますが、flag 自体にはエラーや警告を出す専用処理はありません。根拠: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1560,1760-1761`。
- この flag 固有のファイル書き込みはありません。通常の生成経路では生成 ID ファイル等が既定の動作として書かれます。根拠: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1938-1943`。

## 出力とエラー

比較不一致の詳細は stderr に最大12件、集計は `[spec] check: <行数> window rows recomputed one token at a time, <不一致数> differ bitwise` として stderr に出ます。比較が走らない場合も `cfg.check` 自体が true なら集計行は出ますが、再計算行数は0です。根拠: `engine/src/hy4flash/metal/hy4_metal_spec.h:912-913,977`。

再計算の `forward_chunk` が失敗した場合は spec 実行の `finish` が `error` となり、通常実行では `spec: <理由>` を stderr に出して終了コード1になります。serve では `ERR spec: <理由>` をプロトコル出力に返して終了コード1になります。不一致だけの場合の専用終了コードや警告はありません。根拠: `engine/src/hy4flash/metal/hy4_metal_spec.h:902,916`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1936-1938`、`engine/src/hy4flash/metal/hy4_metal_serve.h:514-518`。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1556-1565` — parser の受理と `SpecCfg` への設定。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:576-586` — `check` の既定値と診断目的。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1772,1929-1943` — 通常実行で spec 経路に入る条件、実行とエラー処理。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:897-917,977` — 再計算、bitwise 比較、不一致ログ、集計および forward 失敗処理。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:233-254,509-522` と `engine/src/hy4flash/metal/hy4_metal_spec.h:722-723` — serve への設定伝達、spec 経路、確率的モードの判定。
