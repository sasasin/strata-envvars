# `--min-p`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（HY4 Metal runner） |
| オプション | `--min-p` |
| 別名 | なし |
| 値 | 数値を1つ。`float` に変換され、明示的な範囲検証・クランプはない |

## 役割

確率サンプリング時に、上位候補の確率を最大候補の確率に対する比率で足切りする値です。Metal runner では、主に DFly2 speculative generation のサンプラーに作用します。

## 使い方

```sh
strata-hy4-metal --model model.strata --engram engram.strata --tokens prompt.ids --gen 32 --temp 0.8 --min-p 0.05
```

この例は DFly2 を利用可能なモデルと設定で speculative generation が選ばれる場合に `--min-p` が使われます。モデルや chunk などの条件で speculative 経路が使われない場合、通常のオフライン生成は greedy argmax 経路です。

## 値と既定値

`--min-p` の値は `atof` で読み、`float` として `SampleOpts::min_p` に格納します。既定値は `0.f` です。オプションの繰り返し指定は引数を順に処理して同じフィールドへ代入するため、最後の値が残ります。値の検証や `[0, 1]` へのクランプはありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1503-1506,1567-1571`、`engine/src/hy4flash/metal/hy4_metal_spec.h:15-24`）。

`min_p <= 0` では足切り分岐が無効です。値が正なら足切りが有効になり、1 より大きい値も拒否されず、確率上位の先頭候補だけが残ります。数値として解釈できない文字列は `atof` により通常 0 として扱われます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1570`、`engine/src/hy4flash/metal/hy4_metal_spec.h:77-80`）。

## 実行時の動作

引数は `cli_samp.min_p` に保存されます。speculative モードは `--gen` 等に加え、draft が off でないこと、モデルに drafter があること、chunk が16以上であること、`--all-logits` でないこと等を条件に選ばれます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`）。speculative 経路ではサンプラー設定を `Spec::run` に渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1930-1938`）。`--ab` 比較モードでは plain と speculative の両方へ同じ設定を渡します（同 `:1898-1914`）。

サンプリング分布では、履歴ペナルティ適用後に top-k（最大64候補）を選び、temperature softmax で確率化した後に min-p を適用します。最大確率 `p[0]` に対し `min_p * p[0]` 以上の候補を残し、その後 top-p を適用して残った候補を再正規化します（`engine/src/hy4flash/metal/hy4_metal_spec.h:29-30,49-95`）。temperature が0以下なら top-k の先頭を返す greedy 分岐で戻るため、min-p は使われません（同 `:64-66`）。

通常のオフライン生成（speculative モードでない `--gen`）は logits の argmax を使い、`cli_samp` を参照しません。その経路では `--min-p` は生成結果に作用しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1967`）。また `--serve` 起動時には `cli_samp` が `ServeOpts` にコピーされません。serve の各要求では `GEN ... min_p=F ...` のような要求内キーを読み、要求ごとの `SampleOpts` に設定します（同 `:1636-1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:91-96,121-144`）。

## 適用条件と副作用

- `--min-p` 自体は確率分布の候補数と重みを変えます。ファイルや設定を書き換える処理はありません。
- speculative sampling では draft 検証の分布にも設定が渡ります。`Spec::run` は `samp` が greedy でなく、またはペナルティが有効な場合に確率モードにします（`engine/src/hy4flash/metal/hy4_metal_spec.h:716-733`）。
- オフライン通常生成および `--serve` の起動引数では適用されません。serve では各 `GEN` 要求の `min_p=` を指定してください（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674,1944-1967`、`engine/src/hy4flash/metal/hy4_metal_serve.h:5,127-144`）。

## 出力とエラー

`--min-p` に固有の validation error や警告はありません。parser は指定値を `atof` で変換して格納します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1567-1571`）。speculative generation 自体が失敗した場合は `spec: <理由>` を stderr に出して終了コード1になりますが、これは min-p 値の検証エラーではありません（同 `:1935-1940`）。

## 根拠

- parser と既定値: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1503-1506,1567-1571`、`engine/src/hy4flash/metal/hy4_metal_spec.h:15-24`
- sampler の適用順・閾値・greedy 条件: `engine/src/hy4flash/metal/hy4_metal_spec.h:29-30,49-95`
- speculative モード条件・サンプラーの引き渡し: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1898-1914,1929-1941`
- 通常オフライン生成での未使用: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1967`
- serve 起動引数と要求単位の値: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:5,91-96,121-144`
