# `--spec-sabotage`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--spec-sabotage` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

DFly2 speculative decoding の検証用に、drafter が作った候補を疑似乱数の token ID に置き換えます。`SpecCfg` のコメントも `test only` としています。通常の文章生成を目的に使う設定ではありません。Metal runner のみを対象とし、CUDA/HIP と SYCL の同名・類似フラグの有無や挙動はこの文書では扱いません。

## 使い方

```sh
# DFly2 speculative decode の検証用。通常の生成には使わない
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --spec-sabotage
```

## 値と既定値

- 値は不要です。指定すると parser が `scfg.sabotage = true` にします。既定値は `false` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1561`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。
- 同じフラグを複数回指定しても true のままです。値を取らないため、後ろに値らしい引数を置いても消費しません。別の有効オプションでなければ未知引数として stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1603-1609`）。
- 専用の数値 validation はありません。

## 実行時の動作

`Spec::run` が speculative step に入ると、まず通常の `d.draft_tree(...)` を呼びます。失敗した場合はこのフラグによる置換に進まず、`draft failed` として speculative 処理が失敗します。成功後、フラグが有効なら候補木を `Kd + 1` 個の線形列に作り直します。先頭には現在の token を置き、後続には固定初期値から xorshift 更新した値の `100000` 剰余を token ID として入れ、各ノードの confidence を `0.9`、reach を `0.9` の深さ乗に設定します（`engine/src/hy4flash/metal/hy4_metal_spec.h:767-793`）。

この分岐では早期打ち切り閾値 `ecut` が `0` になり、`draft_tree` に渡す Tree 有効値も false になります（同 `:769-770`）。ただし `draft_tree` 自体は置換前に呼ばれます。置換後の候補は通常の speculative 検証へ進みます（同 `:794-826`）。

フラグは `SpecCfg` に保存され、オフラインの speculative mode と Metal serve の `Spec` の両方へ渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1636-1656,1930-1936`、`engine/src/hy4flash/metal/hy4_metal_serve.h:36-38,253-255`）。オフラインでは生成・該当ベンチマークのいずれかが指定され、`--draft off` でなく、モデルに DFly2 必須 tensor があり、chunk が16以上、`--all-logits` なし、画像入力なしの場合に speculative mode になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`）。serve でも DFly2 が有効化され、生成上限が正で画像要求がないリクエストで speculative 経路が選ばれた場合に作用します（`engine/src/hy4flash/metal/hy4_metal_serve.h:233-255,509-517`）。これらの条件が成立しなければこの設定は候補生成に使われません。

## 適用条件と副作用

置換候補の token ID は `xs % 100000` で作られ、モデルの語彙サイズ `V` との比較や範囲補正をするコードはこの生成箇所にありません。そのため ID が語彙外になる可能性があり、後続の Metal 実行が失敗するなど正常な生成を保証しません（`engine/src/hy4flash/metal/hy4_metal_spec.h:776-793`）。調査したソースからは、語彙外 ID を受け取った後の具体的な Metal 側の扱いまでは確認できませんでした。

オフラインで speculative mode が成立した場合、生成 token ID は stdout の `generated ids:` と `--out` 配下の `gen_ids.txt` に出力されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1929-1943`）。serve ではリクエストの生成結果として使われます。フラグ固有のファイル書き換えやネットワーク動作はありません。

## 出力とエラー

- speculative loop 内の `draft_tree` が失敗した場合、offline は `spec: draft failed` を stderr に出し終了コード 1 で終了します（`engine/src/hy4flash/metal/hy4_metal_spec.h:770-773`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1936-1938`）。
- `--spec-sabotage` 固有の値検証・警告・エラー表示はありません。語彙外候補の後続処理がどう失敗するかはソースで特定できませんでした。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1556-1565` — 設定の既定値と Metal parser。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:576-585,767-793` — test-only 設定、adaptive/tree の無効化、候補 ID と confidence の置換、draft 失敗経路。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:794-826` — 置換候補の計数と通常の検証への接続。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1656,1755-1772,1929-1943` — serve 設定への伝達、offline の speculative 有効条件と生成出力。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:36-38,233-255,509-517` — serve 設定の保持、Spec 構築、リクエスト時の speculative 経路。
- `docs/cli/README.md:1440` — Metal scope の `--spec-sabotage` 索引リンク（調査時点）。

調査範囲は上記 commit の Strata 所有 Metal runner、speculative decoding、serve 実装です。Metal 実機での実行や候補 ID の実行時挙動は確認していません。
