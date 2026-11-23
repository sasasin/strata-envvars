# `--no-tree`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--no-tree` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Metal 版 HY4 の DFly2 speculative decoding で、Tree-8 検証用の分岐候補を無効にします。候補列を線形にし、greedy 生成で条件が合えば fused linear draft を使います。通常の逐次生成や DFly2 が選択されない実行には影響しません。

## 使い方

```sh
# トークン ID ファイルを使い、利用可能なら DFly2 speculative decoding を行う
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 64 --no-tree
```

`--no-tree` は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1563` で値を読まず `scfg.tree = false` に設定されます。後続に `--tree` を指定すると再び有効になり、同一フラグを複数回指定した場合も parser の処理順で最後の指定が残ります（同:1563-1565）。

## 値と既定値

このフラグ自体は引数を取りません。設定構造体 `SpecCfg` では `tree` の既定値は `true` です（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。`--no-tree` に数値などを続けると値として消費されず、次の parser 周回で別の引数として扱われます。未知の引数なら `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

Metal parser には反対指定の `--tree` もあり、索引にも両方が個別の項目として掲載されています（`docs/cli/README.md:1417,1446`）。この文書の対象である `--no-tree` について索引との食い違いはありません。

## 実行時の動作

オフライン実行では `--no-tree` の値は `SpecCfg` に保持され、speculative ループから DFly2 の `draft_tree` に `enable_tree = cfg.tree && !cfg.sabotage` として渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502-1503,1563`、`engine/src/hy4flash/metal/hy4_metal_spec.h:767-770`）。Tree が無効のとき、greedy draft は各段で第1候補だけを追加し、第2候補の分岐を追加しません。確率的生成でも各段の分布から候補を作りますが、分岐用の第2候補は追加しません（`engine/src/hy4flash/metal/hy4_metal_spec.h:482-509,510-541`）。従って「speculative decoding を無効にする」フラグではなく、候補木の分岐を止める指定です。

さらに `draft_tree` は、Tree 無効・greedy・早期打ち切り無効の全条件が成立すると `draft_linear` を使い、線形候補を組み立てます（`engine/src/hy4flash/metal/hy4_metal_spec.h:352-353,421-445`）。通常設定では `SpecCfg::early_cut` は `0.08` ですが、実行時に早期打ち切り閾値 `ecut` が渡されるのは adaptive モード・`cut < 0`・sabotage でない場合です（同:584-585,767-770）。そのため既定の adaptive 設定では、`--no-tree` だけで fused 経路になるとは限りません。

分岐候補のない列は通常 chunk forward で検証され、実際に分岐がある場合だけ `forward_chunk` に TreeSpec を渡す分岐が使われます（`engine/src/hy4flash/metal/hy4_metal_spec.h:816-826`）。decode の集計行には `tree=0` と表示されます（同:956-960）。

Metal serve モードでも `scfg` は `ServeOpts::spec` にコピーされ、speculative decoder の `Spec` に渡ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1656`、`engine/src/hy4flash/metal/hy4_metal_serve.h:253-255`）。serve では drafter が使える設定でも、生成上限が正で画像要求でない場合に speculative path が選ばれます（`engine/src/hy4flash/metal/hy4_metal_serve.h:509-514`）。

## 適用条件と副作用

オフラインの speculative mode 判定は、`gen > 0` または `bench-m` / `par-m` が指定され、`--draft` が `off` 以外、モデル manifest に DFly2 tensor があり、chunk が 16 以上、`--all-logits` なし、画像要求なし、という条件です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`）。ただし `bench-m` と `par-m` は speculative decode に入る前にそれぞれ処理を終えるため、その実行結果には `--no-tree` は使われません（同:1857-1896）。実際の speculative generation はその後 `spec_mode` 分岐に進む経路です（同:1929-1943）。条件を満たさない場合も通常経路などに進み、この設定は使われません。`--draft off` を選ぶと speculative mode 自体が無効です。

フラグは GPU の実行モードや出力ファイルを直接変更しません。副作用は speculative decode の draft・検証方法の変更に限られます。Metal 用 parser に限定した確認であり、CUDA/HIP や SYCL 版の同名・類似オプションの挙動はこの文書の対象外です。

## 出力とエラー

このフラグ専用の validation や失敗経路はありません。speculative mode で DFly2 の draft が失敗すると `spec: draft failed` 等を stderr に出し、オフライン生成は終了コード 1 になります（`engine/src/hy4flash/metal/hy4_metal_spec.h:770-773`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1930-1940`）。serve では `ERR spec: ...` を protocol 出力してその要求を失敗扱いにします（`engine/src/hy4flash/metal/hy4_metal_serve.h:510-517`）。これらは speculative 処理の失敗経路であり、`--no-tree` 固有のエラーではありません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502-1503,1563-1565` — `SpecCfg` の生成と `--no-tree` / `--tree` の parser。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:352-353,420-445,576-585,767-770` — 既定値、条件付き linear draft、Tree 設定の使用。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:482-541,816-826,956-960` — 分岐候補の生成、分岐有無による検証経路、実行時表示。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1675,1755-1762,1929-1943` — serve への設定伝達、offline の有効条件、speculative generation。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:233-255,509-517` — serve 側の drafter 選択、`SpecCfg` 伝達、speculative path と失敗処理。
- `docs/cli/README.md:1368-1450` — `strata-hy4-metal` の索引 scope、`--no-tree` と反対指定 `--tree` のリンク（調査時点の行番号）。
