# `--no-moe2`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（HY4 Metal runner） |
| オプション | `--no-moe2` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

HY4 の MoE 層で、トークン数 `T <= 8` のときに使う distinct-expert decode / verify 経路を無効にします。通常はこの条件で `moe2_plan`、`moe2_gu`、`moe2_dn` と `moe_reduce_h` を使いますが、このフラグを付けるとそれらの専用 dispatch を選ばず、後続の MoE 経路選択に進みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:363,1174-1181`）。

## 使い方

```sh
strata-hy4-metal --model model.strata --engram engram.strata --tokens prompt.ids --gen 16 --no-moe2
```

`--model`、`--engram`、`--tokens` は runner の通常入力です。例はオプションの配置を示すもので、モデル・入力ファイルは実際の環境に合わせてください。runner の usage にもこれらの必須入力が示されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1613`）。

## 値と既定値

値は不要です。parser は `--no-moe2` を見つけると `no_moe2 = true` にします。初期値は `false` で、同じフラグを複数回指定しても真偽値を再設定するだけです。明示的な値の検証処理はありません。フラグの後ろに別の値を単独で置くと、その値は次の parser 周回で未知の引数として失敗します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1492,1504-1506,1550,1603-1609`）。

## 実行時の動作

main は `r.moe2 = !no_moe2` として Runner に設定を渡します。Runner 側の初期値は `true` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:363,1735`）。MoE 層の処理で `moe2 && T <= 8` が成立しない場合、`mpp_ok && T >= moe_mm_min` なら MPP の MoE 経路へ進み、それ以外は pair 経路（`T <= pair_max`）か sorted 経路を使います（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1174-1182,1213-1240`）。

したがって、`--no-moe2` はすべての MoE 実行を止める指定ではありません。既定の `moe_mm_min` は 64、`pair_max` は 4 です。これらの閾値はそれぞれ `--moe-mm-min`、`--pair-max` で設定されるため、フラグを付けた場合でも値や MPP の利用可否に応じて後続経路が変わります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1525,1546,1728,1752,1174-1182,1227-1239`）。`T > 8` の場合は専用分岐の条件に入らないので、このフラグによる経路差はありません（同 `:1174-1182`）。

## 適用条件と副作用

効果が現れるのは HY4 Metal runner が MoE 層を処理し、その処理単位の `T` が 8 以下の場合だけです。これはモデル計算時の GPU kernel dispatch 選択を変えます。parser には `--no-moe2` 固有の値検証や警告はありません。明示的なファイルやネットワーク操作もこのフラグには結び付いていません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1132-1145,1174-1182,1227-1240,1550`）。

## 出力とエラー

このフラグ自体に固有の出力・エラー経路はありません。認識されない引数が渡された場合は `ERR unknown flag <引数>` を stdout に出し、`unknown arg <引数>` を stderr に出して終了コード 2 で終了します。フラグに値を付けた場合、その値が別のフラグとして認識されなければこの経路になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1492,1550` — `no_moe2` の初期値と parser 登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:363,1735` — Runner の既定値と main からの設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1174-1181` — `T <= 8` の専用 MoE dispatch。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1182-1240` — MPP、pair、sorted の代替経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609` — 未知の引数の出力と終了コード。
- 索引上の配置と scope: `docs/cli/README.md:1358-1411`（`strata-hy4-metal` / Metal）。

調査時点の checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更はありません。ソースから確認できるのは dispatch 条件と設定伝達までであり、各経路の性能差は測定していません。
