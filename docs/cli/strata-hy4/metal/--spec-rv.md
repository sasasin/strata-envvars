# `strata-hy4-metal --spec-rv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--spec-rv` |
| 別名 | なし |
| 値 | 整数。DFly2 の各 draft slot で扱う候補数。既定値 256、上限 1024。0 以下は全語彙の lm_head を使う経路。 |

## 役割

DFly2 speculative decoding の draft token 候補数を調整します。正の値では各 slot の候補を指定数（最大 1024）に絞り、候補の中から次の draft token を選びます。0 以下では候補数を使う絞り込みを行わず、draft token ごとに全語彙の lm_head を評価します。この値は speculative decoding が有効な実行でのみ使われます。

## 使い方

```sh
# 入力 token 列を使って生成し、DFly2 の候補数を 128 にする
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --draft dfly2 --spec-rv 128

# 候補絞り込みを無効にし、draft token ごとに全語彙を評価する
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --draft dfly2 --spec-rv 0

# Metal server の speculative decoding に同じ設定を渡す
strata-hy4-metal --model model.strata --serve --draft dfly2 --spec-rv 128
```

## 値と既定値

- parser は次の引数を `atoi` で整数変換し、`SpecCfg.rv` に代入します。オプション自体に別名はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1562`）。
- `SpecCfg.rv` の既定値は 256 です（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。
- DFly2 は `NC = min(rv, 1024)` を使います。`NC > 0` の場合は候補 top-N を作る経路、`NC <= 0` の場合は全語彙の lm_head を計算する経路です。そのため 1024 より大きい値は 1024 に制限され、0 および負値は絞り込みなしになります（`engine/src/hy4flash/metal/hy4_metal_spec.h:342-348,373-379,410-414`）。
- parser 後にこの値の範囲検査やエラー出力はありません。文字列の不正形式や値の省略に対する詳細な挙動は、このコードだけからは保証できません。整数値を明示してください（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1562`）。

## 実行時の動作

parser の値は `SpecCfg` に保持され、`Spec` の構築時に `DFly2.rv` へコピーされます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1562`; `engine/src/hy4flash/metal/hy4_metal_spec.h:620-625`）。DFly2 は draft backbone の後に `NC` 個の候補 ID を作ります。`NC > 0` ならその候補について scoring を行い、linear draft 経路では候補の argmax を次 token とします。`NC <= 0` なら各 slot で lm_head を全語彙に適用して argmax を取ります（`engine/src/hy4flash/metal/hy4_metal_spec.h:342-348,352-379,392-417`）。

Metal の offline 実行では、生成・benchmark・parity のいずれかがあり、`--draft off` でなく、モデルに DFly2 tensor があり、chunk が 16 以上、`--all-logits` でなく、画像入力もない場合に speculative mode が有効です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1754-1761`）。通常の生成分岐は `Spec` に `scfg` を渡して実行します（同:1929-1943）。`--draft off`、条件不一致、または画像入力の場合、この値は speculative decoding に使われません。

`--serve` では parser の `scfg` が `ServeOpts.spec` に渡され、server 側で `Spec` を生成する際に使用されます。server の speculative path は有効な DFly2 があり、要求の token limit が正で画像入力がない場合に選ばれます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`; `engine/src/hy4flash/metal/hy4_metal_serve.h:233-254,510-514`）。

## 適用条件と副作用

- モデルに DFly2 drafter tensor がない場合は DFly2 自体を初期化できません（`engine/src/hy4flash/metal/hy4_metal_spec.h:195-198`）。offline の `--draft dfly2` では適用できない旨を stderr に出します。`auto` では speculative mode 条件を満たさず、通常の生成経路になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1769,1944-1966`）。
- server でも `--draft dfly2` を指定して DFly2 を利用できない場合は protocol error を出し、終了コード 2 で戻ります（`engine/src/hy4flash/metal/hy4_metal_serve.h:233-251`）。
- 候補 ID の生成と scoring / 全語彙 lm_head 計算は Metal runner の処理に含まれます。ファイル出力など `--spec-rv` 固有の副作用は確認できません。生成自体の出力ファイルは他の処理で作られます（例: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1938-1943`）。

## 出力とエラー

`--spec-rv` の値自体を拒否する範囲検査・専用警告・専用エラー経路は parser にありません。DFly2 の初期化に失敗した場合は offline 実行で `dfly2: <理由>` を stderr に出して終了コード 1 となり、server で明示的に `--draft dfly2` を要求していた場合は protocol error と終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1767-1770`; `engine/src/hy4flash/metal/hy4_metal_serve.h:244-251`）。

## 根拠

- parser と既定の `SpecCfg`: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1499-1502,1556-1565`; `engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`。
- 候補数の上限、top-N 生成、候補 scoring と全語彙 fallback: `engine/src/hy4flash/metal/hy4_metal_spec.h:342-348,352-379,392-417`。
- 値を DFly2 に反映する箇所: `engine/src/hy4flash/metal/hy4_metal_spec.h:620-625`。
- offline の適用条件・生成分岐・初期化失敗: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1754-1772,1929-1943`。
- server への設定伝達と適用条件: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`; `engine/src/hy4flash/metal/hy4_metal_serve.h:233-254,510-514`。
