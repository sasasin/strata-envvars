# `strata-hy4-metal --tree`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--tree` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

DFly2 speculative decode の候補展開と検証で、Tree-8 の分岐候補を有効にする。Metal runner では既定で有効なため、通常は指定しなくても同じ設定で動く。明示的に無効化する場合は `--no-tree` を使う。

## 使い方

```sh
# DFly2 を指定して生成し、Tree-8 speculative verification を明示的に有効にする
strata-hy4-metal --model SQ64.strata --tokens prompt.ids --gen 32 --draft dfly2 --tree
```

実行時にはモデルとトークン入力が必要である。`--tree` 自体はモデルや出力ファイルを指定しない。

## 値と既定値

- 値を取らず、parser はフラグを見つけると `scfg.tree = true` にする（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1563-1564`）。
- 既定値も `true`（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。したがって単独指定では既定状態から変化しない。
- 引数の重複や `--no-tree` との併用を拒否する検証はない。引数は左から順に処理され、それぞれが同じ設定値を書き換えるため、両方を指定した場合は後に現れた方が有効になる（parser loop: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1507,1563-1564`）。

## 実行時の動作

parser が設定を `SpecCfg` に保持し、serve 実行時の `ServeOpts` に渡す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502-1503,1655-1656`）。オフライン実行では DFly2 が使える場合に `Spec` が同じ設定を受け取る（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1769,1929-1930`）。

オフライン生成で speculative mode になる条件は、生成・計測対象があり、`--draft` が `off` でなく、モデルに DFly2 drafter tensor があり、実効 chunk が 16 以上で、`--all-logits` でも画像入力でもないこと（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1761`）。この条件を満たさない実行では `--tree` は speculative decode の設定として利用されない。`--draft` の既定値は `auto` で、ファイルに drafter があり `--gen > 0` の場合に DFly2 を使う設定である（同 `:1501-1502`）。

speculative decode の各反復は `cfg.tree && !cfg.sabotage` を候補生成処理へ渡す（`engine/src/hy4flash/metal/hy4_metal_spec.h:767-770`）。Tree-8 が有効な場合、greedy 経路では各展開段階の第 1 候補に加えて条件を満たす第 2 候補も候補 frontier に追加する。確率的 sampling 経路でも、分布に複数候補があり残余確率が十分な場合に第 2 分岐を追加する（同 `:482-509,510-542`）。分岐を持つ候補を検証すると、Metal runner は Tree 用の attention / indexer 処理を使い、受理した枝の KV・IndexPool 状態を確定する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:851-883,984-1066,1249-1289`）。

## 適用条件と副作用

- この文書の対象は Metal backend の `strata-hy4-metal` である。CUDA/HIP と SYCL の同名フラグは別 scope で、ここでは扱わない（`docs/cli/README.md` の `strata-hy4` の Metal 節、parser は `engine/src/hy4flash/metal/hy4_metal_main.cpp`）。
- `--no-tree` は同じ `scfg.tree` を `false` にする。木分岐を無効にした場合、greedy かつ early-cut 無効の経路では線形 draft に切り替わる（`engine/src/hy4flash/metal/hy4_metal_spec.h:420-445`）。それ以外の候補生成経路でも、第 2 分岐を追加する条件は `enable_tree` により抑止される（同 `:502-509,527-542`）。
- `--spec-sabotage` が有効な場合は `cfg.tree` の値にかかわらず木候補の生成を無効にする（`engine/src/hy4flash/metal/hy4_metal_spec.h:767-770,776-793`）。
- フラグ専用の追加ファイル・ネットワーク操作は確認できない。効果は speculative decode 内の候補生成と Metal 検証処理に限られる。

## 出力とエラー

`--tree` の値検証や専用エラー経路はない。未知の引数は標準出力に `ERR unknown flag ...`、標準エラーに `unknown arg ...` を出して終了コード 2 になる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608`）。speculative decode 自体の失敗時は `spec: ...` を標準エラーに出して終了コード 1 となるが、これは `--tree` 固有の失敗条件ではない（同 `:1936-1938`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502-1507,1563-1564` — `SpecCfg` の生成、引数走査、`--tree` / `--no-tree` の parser 定義。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:576-585` — `SpecCfg::tree` の既定値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1769,1929-1930` — speculative mode の条件と設定の適用。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:420-445,482-509,510-542,767-770` — tree 無効時の線形経路、分岐候補の生成、設定の呼び出し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:851-883,984-1066,1249-1289` — Tree 用 Metal runner 処理と受理枝の確定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608,1936-1938` — 未知引数と speculative 処理失敗の出力・終了コード。
