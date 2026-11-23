# `strata-hy4-metal --mpp-min`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--mpp-min` |
| 別名 | なし |
| 値 | 整数。MPP dense GEMM を使い始める token 行数のしきい値。既定値は `96`。 |

## 役割

Metal runner が prefill 中の dense linear 層で Metal 4 MPP GEMM を選ぶ最小 token 行数を調整します。値が小さいほど少ない行数から MPP 経路の対象になりますが、実際に使われるかは MPP kernel の利用可否、重み形式、scratch 容量にも依存します。

## 使い方

```sh
# prefill の MPP dense GEMM しきい値を 128 token 行にする
strata-hy4-metal --model model.strata --tokens prompt.ids --mpp-min 128
```

## 値と既定値

引数は `atoi` で整数へ変換されます。未指定時は `96` です。parser にこの値の範囲チェックや補正はありません。したがって、0 や負数も parser では拒否されず、実行時の比較条件にそのまま使われます。数値でない値の変換結果についても、Strata 独自の検証・エラー処理はありません。`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1547`

## 実行時の動作

`--mpp-min` の値は runner の `mpp_min` に渡されます。dense linear の入力行数 `M` がこのしきい値以上で、MPP kernel が使用可能、重み形式が `F_Q8ROW` 以外、かつ重みサイズ `N*K` が確保済み scratch 要素数以下の場合に、重みを fp16 scratch に dequantize して MPP GEMM dispatch を追加します。条件を満たさなければ通常の linear 経路へ進みます。`engine/src/hy4flash/metal/hy4_metal_main.cpp:487-509,1751`

MPP kernel は既定では試行されますが、`--no-mpp` が指定された場合は試行されません。Metal 4 MPP kernel の compile に失敗した場合も `mpp_ok` が有効にならず、通常の kernel 群に fallback するため、このしきい値だけでは MPP 経路を有効化できません。`engine/src/hy4flash/metal/hy4_metal_main.cpp:328,530-558,1729`

この値は MoE grouped GEMM のしきい値 `--moe-mm-min` とは別です。MoE 経路は `T >= moe_mm_min` で選択されます。一方、prefill の dispatch 間の並行実行を許可するかは `mpp_ok` と `T >= min(mpp_min, moe_mm_min)` によって決まるため、`--mpp-min` は dense linear 経路だけでなく、この並行実行制御にも影響します。`engine/src/hy4flash/metal/hy4_metal_main.cpp:337,1182-1183,1296`

`--mpp-min` は MPP Flash-MLA の選択条件には使われません。Flash-MLA 側は別の条件（kernel が利用可能か、flash が有効か、`T` が 16 以上かなど）で選択されます。`engine/src/hy4flash/metal/hy4_metal_main.cpp:1016-1022,1067-1070`

## 適用条件と副作用

このオプションは Metal 版 `strata-hy4-metal` の parser に属します。MPP dense GEMM が選ばれた場合、既定の MPP tile または `--mpp-tile` で選ばれた tile kernel を dispatch します。MPP 利用可能時の scratch は初期化時に確保され、しきい値はその確保量を変えません。`engine/src/hy4flash/metal/hy4_metal_main.cpp:341,487-495,557-558`

実際の採用条件に合わない場合、この値によるエラーや警告は確認できません。`--mpp-min` 専用の validation error、警告、出力も parser と処理経路にはありません。未知の option は別経路で stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード `2` になります。`engine/src/hy4flash/metal/hy4_metal_main.cpp:1547,1604-1608`

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1547` — 既定値 `96` と `atoi` を使う parser 登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:328-332,1751` — runner 内の MPP 状態と、parser 値の runner への設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:487-509` — dense linear でしきい値・形式・scratch 条件を判定し、MPP または通常 kernel を dispatch する処理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:530-558,1729` — MPP kernel compile の試行、fallback、および `--no-mpp` の反映。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1182-1183,1291-1297` — 独立した MoE GEMM しきい値と、MPP に伴う dispatch 並行実行制御。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1067-1070` — Flash-MLA が別条件で選択される箇所。
