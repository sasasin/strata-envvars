# `strata-hy4-metal --moe-tm`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal`（HY4 Flash の Metal runner。トップレベル） |
| オプション | `--moe-tm` |
| 別名 | なし |
| 値 | `atoi` で整数に変換する値。Strata 側の範囲検証なし |

## 役割

MoE の MPP grouped GEMM 経路で使う M タイル寸法を上書きします。0 の場合はチャンク長に応じて自動選択され、正の値は選んだ M 寸法とカーネル名に反映されます。この指定は、Metal 4 MPP が利用可能で、MoE の処理が MPP 経路を選ぶ場合に限って関係します。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --moe-tm 32
```

上の例は、MPP MoE 経路が選ばれる場合に M タイル寸法 32 を要求します。実際に選ばれる経路は MPP の利用可否、処理するトークン数、`--moe-mm-min`、`--no-mpp`、`--moe-tn`、`--no-moe-bucket` によって変わります。

## 値と既定値

- 既定値は `0` です。`moe_tm_arg` の初期値と parser の変換は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1538` にあります。
- 自動選択では `T <= 2560` のとき 32、それより大きいとき 64 を使います（同 `:347,1214`）。ここで `T` は MoE dispatch に渡る処理トークン数です。
- parser は `atoi` で整数化し、`--moe-tm` 専用の範囲検証・エラー処理は行いません（同 `:1538`）。同じ指定を複数回書いた場合は引数ループ中で値を上書きするため、最後の値が残ります（同 `:1504-1538`）。
- 0 以外の値は bucketed 経路の選択条件を外します。負数は正の上書き条件を満たさないためタイル寸法自体は自動選択に戻りますが、値が 0 ではないため同経路を選びません（同 `:1184,1214`）。

## 実行時の動作

parser の値は Runner にコピーされ、MPP MoE の分岐で参照されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1743-1745`）。MPP を利用でき、`T >= moe_mm_min` の場合に grouped GEMM を使います（同 `:1182`）。既定の `moe_mm_min` は 64 です（同 `:337,1491,1752`）。

この分岐では、`--moe-tm 0`、`--moe-tn 64`（既定値）、かつ bucketed MoE が有効（既定）なら複数サイズの bucketed planner と kernels を使います。`--moe-tm` を 0 以外にする、`--moe-tn` を 64 以外にする、または `--no-moe-bucket` を指定すると、単一 TM/TN の planner と grouped GEMM に切り替わります（同 `:338-340,1184-1225`）。

単一タイル経路では、正の `--moe-tm` が TM に使われ、0 以下なら自動値に戻ります。TM と `--moe-tn` から `moe_mm_gu_<TM>_<TN>_<SG>` / `moe_mm_dn_<TM>_<TN>_<SG>` という kernel 名を作ります。`SG` は TM/TN の組み合わせから決まり、planner にも TM を渡します（同 `:1214-1224`）。タイル用 GPU バッファの確保量は少なくとも 64 と自動 TM の大きい方で、さらに正の override があればそれも下回らないように計算します（同 `:557-572`）。

## 適用条件と副作用

- Metal MPP kernels のコンパイルが成功した場合に `mpp_ok` が立ち、失敗すると MPP kernels を利用しない fallback に進みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:530-555`）。MPP を明示的に無効化する `--no-mpp` もあります（同 `:1527,1729`）。
- MoE の `T <= 8` は MPP MoE 分岐より前の `moe2` 経路が優先されます。MPP が使えない場合や `T < moe_mm_min` の場合もこのオプションによる TM 選択は使われず、後続の pair/sorted MoE 経路へ進みます（同 `:1174-1182,1226-1235`）。
- `--moe-tm` 自体が GPU バッファ確保を変更するわけではありませんが、MPP 初期化時に tile override を考慮した作業バッファが確保されます（同 `:557-572`）。
- Metal kernel ソースが明示的に登録している grouped GEMM の TM は 16、32、64 の組み合わせです（`engine/src/hy4flash/metal/hy4_mppmoe.metal:445-451`）。それ以外の整数を指定した場合も CLI は事前検証せず、その値を含む kernel 名を `cx.pipeline` に渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:425-428,1214-1222`）。該当 kernel が見つからない場合の具体的なエラー文・終了コードは、この Strata 側の呼び出し箇所からは確認できません。

## 出力とエラー

このオプションの値に対する個別の警告・エラー出力は parser にありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1609`）。不正な TM/TN の組み合わせについては kernel 名を動的に生成して pipeline 解決を要求するところまでを確認しましたが、その失敗時の表示や終了コードは pipeline 実装側の挙動に依存し、この調査範囲では確定できません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1537-1539` — 値の初期値と CLI parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:337-347,557-572` — Runner の既定値、自動 TM の規則、MPP 用バッファ確保。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1174-1235` — decode/小チャンク、MPP grouped GEMM、fallback の分岐と tile/kernel 選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:425-428,1743-1752` — kernel pipeline 解決と parser 値の Runner への転送。
- `engine/src/hy4flash/metal/hy4_mppmoe.metal:445-451` — grouped GEMM kernel の明示的な TM/TN/SG インスタンス。
