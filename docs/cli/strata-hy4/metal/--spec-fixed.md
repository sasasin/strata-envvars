# `strata-hy4-metal --spec-fixed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--spec-fixed` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

DFly2 の speculative decode が有効な実行で、検証するドラフト木の幅を適応的に選ぶ動作を止め、各ドラフト木の全ノードを検証対象にします。ドラフト長そのものを指定するオプションではありません。ドラフト長は `--spec-k` が設定します。

## 使い方

未使用の出力ディレクトリを指定した例です。モデル・prompt のファイルは実行環境に合わせて用意してください。

```sh
strata-hy4-metal --model ./model.strata --tokens ./prompt.txt --gen 32 --spec-fixed --out ./run-fixed
```

## 値と既定値

- `--spec-fixed` 自体は値を取らず、parser は `SpecCfg::adaptive` を `false` にします。同じフラグを複数回指定しても同じ代入が繰り返されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1556-1558`）。
- 省略時は `SpecCfg::adaptive` の初期値 `true` です（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。
- 値の範囲 validation はありません。フラグの後ろに値を置くと、その値は別の引数として扱われ、未知引数として失敗します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1556-1558,1604-1609`）。

## 実行時の動作

- `Spec::choose_m()` は `adaptive == false` の場合、confidence やコストモデルによる幅の選択を行わず、ドラフト木のノード数 `tr.M` を返します。呼び出し側はその値を検証幅 `T` とし、木を `T` ノードに切り詰めてから検証します（`engine/src/hy4flash/metal/hy4_metal_spec.h:642-657,792-799`）。
- 固定モードでもドラフト木の最大長は別設定です。`--spec-k` の既定値は 5 で、`Spec` の初期化時に 1〜7 に補正されます。残り context に収まらない場合はその実行の `Kd` が縮み、1 未満や drafter が利用できない場合は通常の1トークン生成に進みます（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585,620-626,748-765`）。起動直後の校正用2ステップも通常生成です（同 `:620-625`）。
- 固定モードでは `--spec-cut` の confidence 閾値による幅選択も適用されません。`choose_m()` は `!adaptive` を先に判定して全ノード数を返します（同 `:642-648`）。また、適応モードでのみ記録する性能に基づく backoff も行われず（同 `:694-714`）、適応モードかつ `--spec-cut` 未指定の場合だけ渡される early-exit 閾値も 0 になります（同 `:767-770`）。`--no-tree` など、ドラフト木の構成を変える設定は別途作用します。

## 適用条件と副作用

このフラグだけでは speculative decode を有効化しません。Metal runner では、生成・ベンチマーク・window parity のいずれかが要求され、`--draft off` ではなく、モデル manifest に DFly2 の必要 tensor があり、runner の実効 chunk (`r.Tc`) が16以上で、`--all-logits` がなく、画像入力がない場合に `spec_mode` になります。指定された `--chunk` と入力長から実効 chunk を作ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1713-1715,1755-1762`）。この条件を満たさない場合、フラグは設定されても speculative decode の経路で使われません。

固定モードを選ぶこと自体によるファイル書き込みはありません。通常の `spec_mode` 生成経路では、生成 ID を標準出力へ表示し、`--out` 配下の `gen_ids.txt` にも書き込みます。`--ab` 比較経路では初回に `gen_ids_plain.txt` と `gen_ids_spec.txt` を書き込みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1929-1943,1898-1927`）。出力ファイルが既にある場合の扱いは、ここで確認した `std::ofstream` の生成箇所からは別途の上書き保護を確認できません。

## 出力とエラー

- `spec_mode` では `Spec::report()` が stderr に `adaptive` または `fixed` を含む統計を出します。`--spec-fixed` の実行では `fixed` と表示されます（`engine/src/hy4flash/metal/hy4_metal_spec.h:956-965`）。
- speculative run 内で plain forward または draft が失敗すると `finish == "error"` になり、呼び出し側は stderr に `spec: <理由>` を出して終了コード 1 を返します（同 `:754-773`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1930-1941`）。
- parser が認識しない引数（フラグの後ろに誤って置いた値を含む）は stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609`）。

## 根拠

- parser と設定値への代入: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1556-1558`。
- adaptive の既定値、固定モードの全幅選択、`--spec-cut` との優先関係: `engine/src/hy4flash/metal/hy4_metal_spec.h:576-585,642-657`。
- context によるドラフト長調整、通常生成への切り替え、early-exit 条件: `engine/src/hy4flash/metal/hy4_metal_spec.h:748-775`。
- backoff 抑止と統計出力: `engine/src/hy4flash/metal/hy4_metal_spec.h:694-714,956-965`。
- Metal runner の実効 chunk と speculative decode が有効になる条件、失敗時の終了、生成結果の出力: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1713-1715,1755-1772,1898-1943`。
- 索引上の scope は `strata-hy4-metal` の Metal parser（`engine/src/hy4flash/metal/hy4_metal_main.cpp`）で、掲載先は `strata-hy4/metal/--spec-fixed.md` です（`docs/cli/README.md:1358-1361,1433-1439`）。

調査は parser、speculative decode 実装、および runner の該当経路に限定しました。CLI の `--help` は実行していません。
