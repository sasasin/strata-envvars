# `strata-hy4-metal --no-moe-bucket`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--no-moe-bucket` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Metal runner が MPP grouped GEMM で MoE を処理するときに使う、128 / 64 / 32 / 16 行単位の bucketed planner を無効にします。A/B 比較用のフラグで、対象経路では通常の単一タイル幅 planner と GEMM kernel を選びます。

## 使い方

```sh
# Metal runner の MoE bucketed 経路を無効にして実行する
strata-hy4-metal --model model.strata --tokens ids.txt --no-moe-bucket
```

## 値と既定値

値は指定しません。parser の初期値は無効化フラグ `no_moe_bucket = false` で、runner 側の `moe_bucket` は既定で `true` です。指定すると `no_moe_bucket` が true になり、runner には `moe_bucket = false` が渡ります。値の validation はありません。同じフラグを複数回指定しても true を再設定するだけです（`engine/src/hy4flash/metal/hy4_metal_main.cpp:340,1492,1539,1745`）。

## 実行時の動作

MoE の各層では、まず `moe2` が有効で入力行数 `T <= 8` なら `moe2` 経路が選ばれ、このオプションは分岐に関与しません。それ以外で MPP kernel が利用可能かつ `T >= moe_mm_min` の場合、通常は bucketed 経路が候補になります。その条件に加えて `moe_bucket` が true、`--moe-tm` が未指定（0）、`--moe-tn` が既定の64のときだけ、bucketed planner と複数サイズの Gate/Up・Down kernel を使います（`engine/src/hy4flash/metal/hy4_metal_main.cpp:337-340,1174-1185`）。

この条件で `--no-moe-bucket` を指定すると、通常の MPP 経路内の `moe_plan` と、`moe-tm` / `moe-tn` から選ぶ単一タイルの Gate/Up・Down kernel に切り替わります。フラグ自体に値やタイル幅を指定する機能はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1213-1226,1537-1539,1743-1745`）。bucketed planner は MoE のルーティング結果を 128 / 64 / 32 / 16 行のグループに分けます（`engine/src/hy4flash/metal/hy4_mppmoe.metal:80-96`）。

## 適用条件と副作用

- 実装対象は `strata-hy4-metal` の Metal runner です。CUDA/HIP および SYCL の runner には、この parser 宣言はありません（Metal parser: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1540`。CLI 索引の scope: `docs/cli/000_cli_tools.md:11`）。
- `moe2` の `T <= 8` 経路、MPP が使えない場合、または `T < moe_mm_min` の場合、このフラグは bucketed 経路の選択に影響しません。既定の `moe_mm_min` は64です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:337,1174-1184`）。
- `--moe-tm` が0以外、または `--moe-tn` が64以外なら、フラグの有無にかかわらず標準 MPP planner 側に入ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1184,1213-1217`）。
- MPP kernel のコンパイルに失敗して利用できない場合、runner は通常 kernel 群へ fallback し、MoE の bucketed MPP 分岐自体を通りません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-555,1182-1184`）。
- このフラグ専用のファイル書き込みや出力はありません。効果は MoE の GPU dispatch 選択に限られ、性能差や推奨設定はこのソース調査からは判断できません。

## 出力とエラー

このフラグについて固有の警告・エラー出力は確認できません。値を誤って付けて余分な引数が未知の引数になった場合など、未知の引数は標準出力に `ERR unknown flag ...`、標準エラーに `unknown arg ...` を出して終了コード2になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:337-340` — `moe_mm_min` と tile override の既定値、`moe_bucket` の初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1174-1226` — MoE 入力行数と MPP 可用性による分岐、bucketed / 標準 planner の dispatch。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1537-1540,1743-1745` — parser 宣言と `Runner` への値の反映。
- `engine/src/hy4flash/metal/hy4_mppmoe.metal:80-96` — bucketed planner の行サイズ区分。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:533-555` — MPP kernel compile の試行と通常 kernel への fallback。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608` — 未知引数の出力と終了経路。
