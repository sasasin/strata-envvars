# `--no-idxsg`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--no-idxsg` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

IndexPool のスコア計算で既定の `simdgroup_matrix` カーネルを選ばず、通常経路では `idx_score`、tree speculative decoding 経路では `idx_score_tree` を使います。IndexPool 自体を無効にする `--no-index` とは別の指定です。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens ids.txt --no-idxsg
```

## 値と既定値

値は不要です。parser はフラグを読むと `no_idxsg` を `true` にし、Runner の `idxsg_on` にはその否定値を設定します。したがって未指定時は `idxsg_on=true` で `simdgroup_matrix` scorer が有効、指定時は無効です。同じフラグを複数回指定しても boolean を `true` にするだけです。数値などの値を消費せず、個別の範囲検証もありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1542,1748`）。

## 実行時の動作

IndexPool が使われる層・chunk では、通常経路のスコア計算を `idx_score_sg` から `idx_score` へ切り替えます。tree speculative decoding では `idx_score_sg_tree` から `idx_score_tree` へ切り替えます。どちらの経路も、その後の top-k 選択は同じ `idx_select` / `idx_select_tree` を呼びます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:868-895`）。実装コメントでは `idx_score_sg` は scalar scorer と同じ計算をしつつ pooled reads を減らすカーネルとして説明されています（`engine/src/hy4flash/metal/hy4_kvb.metal:290-295`、tree 版は `engine/src/hy4flash/metal/hy4_dfly2b.metal:279-281`）。このフラグによる性能差はソース調査だけでは判断できません。

切り替えは `idx_select` が呼ばれる箇所に限られ、IndexPool が無効な場合、SWA 層の場合、または処理位置が `index_topk` 以下の場合はスコア計算が行われず、この指定によるカーネル選択も発生しません。IndexPool の呼び出し条件は `!swa && index_on`、選択開始条件は `end_pos > index_topk` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1041`）。

`--no-index` は `index_on` を無効にする別オプションです。`--no-index` と `--no-idxsg` を同時に指定すると IndexPool 処理自体が迂回され、scorer の選択は使われません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1520,1723-1724,1032-1041`）。

`--serve` 経路では `ServeOpts` に `idxsg_on` 相当の項目がなく、Runner に渡す値もありません。serve 用 Runner は既定値 `idxsg_on=true` のままなので、`--serve --no-idxsg` を指定しても scorer は無効化されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1648`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,219-226`）。

## 適用条件と副作用

Metal 実装 `strata-hy4-metal` のオプションです。GPU に渡す IndexPool scorer のカーネル選択を変えます。別のモデル設定、ファイル、ネットワーク、プロセスを変更する副作用はこのフラグの処理にはありません。parser は `--no-idxsg` の後続値をこのフラグの値として扱いません。別の引数として解析され、未対応の引数なら `ERR unknown flag ...` を標準出力、`unknown arg ...` を標準エラーに出して終了コード 2 で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1542,1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:336` — Runner の `idxsg_on` は既定で有効。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1542,1748` — parser と Runner 設定への反映。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:868-895` — 通常/tree scorer の分岐と共通の top-k 選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1041` — scorer が実行される条件。
- `engine/src/hy4flash/metal/hy4_kvb.metal:290-295`、`engine/src/hy4flash/metal/hy4_dfly2b.metal:279-281` — simdgroup scorer の役割に関する実装コメント。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1648`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,219-226` — serve 経路でこの設定が Runner に渡らないこと。
