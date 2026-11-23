# `strata-hy4-metal --spec-cut`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal、root） |
| オプション | `--spec-cut` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で変換される値。Strata 側の範囲検証なし |

## 役割

DFly2 speculative decoding の適応的な検証幅を、推測ノードの confidence と比較する閾値で決める。値が 0 以上の場合はコストモデルによる幅選択を使わず、confidence が閾値を超えるノードを木の順に検証対象へ含め、最初に閾値以下となる箇所で止める。負値は閾値選択を無効にして既定のコストモデル選択に戻す。Metal runner の `SpecCfg` 既定値は `-1.f` である（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1558`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-580,642-657`）。

## 使い方

```sh
# DFly2 を使う通常の生成で confidence 閾値を 0.4 にする
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --spec-cut 0.4
```

この指定が検証幅に作用するのは speculative decoding が有効な経路です。通常生成では `--gen` などの実行指定に加え、ドラフターがモデル内にあり、chunk が 16 以上で、`--all-logits` ではなく、画像要求がないことが必要です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`）。

## 値と既定値

- 引数を `atof` で `float` に変換して `scfg.cut` へ代入します。Strata の parser に数値範囲、有限値、書式の検証はありません。変換できない文字列も parser では拒否せず、変換結果が `0` なら閾値選択が有効になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1558`）。
- 既定値は `-1.f` です。`cut < 0` では閾値分岐に入らず、コストモデルで検証幅を決めます。`cut >= 0` では `node_conf[m] > cut` の間、幅を進めます（`engine/src/hy4flash/metal/hy4_metal_spec.h:579,642-657`）。
- 同じ引数を複数回指定すると、parser が順に同じフィールドへ代入するため最後の値が残ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1558`）。
- 値を省略した場合の専用 validation はありません。parser の `nxt` は次の `argv` を直接参照する実装です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1558`）。省略時の安全なエラー処理はソースから確認できません。

## 実行時の動作

parser は値を `SpecCfg.cut` に格納し、通常生成では `Spec` の構築時にその設定を渡します。`choose_m` は最初に `adaptive` を確認するため、`--spec-fixed` を併用すると固定幅を返し、`--spec-cut` は検証幅に作用しません。適応モードで `cut >= 0` の場合は `node_conf` を閾値と比較して幅を選び、負値の場合は各候補幅の推定スループットを比較するコストモデルを使います（`engine/src/hy4flash/metal/hy4_metal_spec.h:642-657`）。

confidence は DFly2 の confidence head から取得され、生成木の各ノードに記録されます。閾値はその並びに沿って比較され、最初に `node_conf[m] <= cut` となった位置で止まります（`engine/src/hy4flash/metal/hy4_metal_spec.h:392-418,420-445,546-568,642-647`）。

適応コストモデルによる実測窓の更新は `cut >= 0` でスキップされます。また `--spec-early` に相当する早期打ち切り値は `adaptive && cut < 0 && !sabotage` の場合だけ draft 処理へ渡されるため、`--spec-cut` を 0 以上にするとその早期打ち切りは無効になります（`engine/src/hy4flash/metal/hy4_metal_spec.h:694-696,767-770`）。

`--serve` 経路でも parser の設定を `ServeOpts.spec` に渡し、サーバーが speculative decoding を有効にした場合は同じ設定で `Spec` を作ります。サーバー側での有効条件は `--draft` が `off` でなく、モデルに drafter があり、chunk が 16 以上であることです（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1657`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,233-254`）。

## 適用条件と副作用

- 閾値による検証幅選択は適応モードかつ speculative decoding が実際に使われる場合に限られます。ドラフターが使われない通常経路ではこの値を参照しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1760-1762,1929-1936`）。
- `--spec-cut` 自体はファイルやネットワークを操作しません。speculative 生成経路では通常の出力として生成 ID を標準出力へ出し、`<out-dir>/gen_ids.txt` に書き込みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1936-1943`）。
- 0 以上の値について有効範囲の制限や clamp はありません。値が confidence の取り得る範囲外の場合の結果は、上記の比較式に従います。NaN 等の特殊値に関する明示的な検証もありません。

## 出力とエラー

`--spec-cut` 専用の成功メッセージや validation error はありません。変換後の値が受理され、speculative 経路の実行時エラーは `spec: <理由>` を標準エラーへ出して終了コード 1 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1936-1940`）。モデル指定がない場合は usage を標準エラーへ出し終了コード 2、未登録のフラグは `ERR unknown flag ...` を標準出力と標準エラーへ出し終了コード 2 です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1613`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506,1556-1565`: Metal CLI の引数処理、`SpecCfg` の生成、`--spec-cut` の parser 登録。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:576-586,642-657,694-696,767-770`: 既定値、閾値に基づく検証幅選択、コストモデル更新と早期打ち切りとの相互作用。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:392-418,420-445,546-568`: confidence head の値取得と draft 木ノードへの confidence 記録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1929-1943`、`engine/src/hy4flash/metal/hy4_metal_serve.h:233-254`: 適用条件、通常生成・serve 経路での `SpecCfg` の利用。
