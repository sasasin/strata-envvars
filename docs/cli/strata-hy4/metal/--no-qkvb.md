# `strata-hy4-metal --no-qkvb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal` |
| オプション | `--no-qkvb` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

Metal 版 HY4 runner で、decode / verify の小さい token batch に対して使う、量子化済み `kv_b_proj` の直接処理を無効にします。無効化すると、量子化重みを FP16 scratch に展開してから通常の行列積カーネルで処理する経路になります。対象の分岐は `Runner::attention_layer` 内にあります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1007-1024,1088-1101`）。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.txt --gen 32 --no-qkvb
```

`--no-qkvb` は単独で指定し、値を続けません。モデルと token 入力を指定する通常の Metal runner 呼び出しに加えます（引数解析: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1542,1611-1614`）。

## 値と既定値

値・別名はありません。parser は起動時に `no_qkvb = false` と初期化し、フラグを読むと `true` にします。未指定なら `Runner::qkvb_on` は既定の `true` のまま、Runner へは `!no_qkvb` が渡ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:335,1490-1491,1541,1747`）。複数回指定しても同じ真偽値を設定するだけです。値の validation はありません。

## 実行時の動作

attention の token 数 `T` が 8 以下で、かつ `--no-qkvb` を指定していない場合、量子化重みを直接読む `mla_prep_q_dec_*` と `mla_vup_dec_*` を使います。指定すると `use_qkvb` が偽になり、`split_kvb_t_*` で量子化 `kv_b_proj` を FP16 の `wk_scr` / `wv_scr` に展開し、query 側を `mla_prep_q_mm`、value 側を `mla_vup_mm` で処理します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1007-1024,1088-1101`）。各カーネルは量子化形式の `kv_b_proj` を直接読む経路と、FP16 展開データを使う経路として定義されています（`engine/src/hy4flash/metal/hy4_kvb.metal:5-13,57-63,117-153,155-158,229`）。

この切り替えは `T <= 8` のときだけ直接経路の選択に影響します。`T > 8` ではフラグ未指定でも `use_qkvb` が偽となり、同じ FP16 scratch 経路に入ります。さらに `T >= 32` では MPP Flash が使用可能かつ有効な場合、query / value 側で `mla_prep_q_mpp` / `mla_vup_mpp` が選ばれます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1009-1024,1091-1101`）。

## 適用条件と副作用

このオプションは `strata-hy4-metal` の parser にだけ定義されています。`strata-hy4` CUDA/HIP や他 backend への適用は確認していません（Metal parser: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1542`）。

モデル読込後、runner は FP16 scratch 領域を確保し、全 layer の `kv_b_proj` が S4 / S5 / S6 / S8 のいずれかであることを検査します。この初期化・形式検査は `--no-qkvb` の有無に関係なく実行されるため、このフラグは scratch の確保を省かず、対応外形式を許可もしません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:629-635`）。フラグは処理経路を切り替えますが、ファイルやモデル設定を書き換える処理は見当たりません。

## 出力とエラー

このフラグ自体に専用の出力・validation error はありません。値なしのフラグとして認識され、同じ引数解析で未認識引数が来た場合は `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出し、終了コード 2 で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1541,1603-1609`）。モデルが指定されない場合も usage を stderr に出して終了コード 2 です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1614`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1541,1747` — フラグの初期値、parser 登録、Runner への値の反映。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1007-1024,1088-1101` — `T <= 8` での直接量子化経路と、無効時の FP16 scratch / matrix 経路。
- `engine/src/hy4flash/metal/hy4_kvb.metal:5-13,57-63,117-153` — 直接 decode / verify カーネルと、重みを FP16 scratch に展開するカーネル。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:629-635,1603-1609,1611-1614` — scratch 確保と形式検査、未知引数およびモデル未指定時の失敗経路。
