# `strata-hy4-metal --seg`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--seg` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Metal runner のコマンドバッファを segmented mode で実行します。`--prof` も同じモードを有効にしますが、`--seg` は profiling を要求せずにこの実行方式だけを選ぶフラグです。Metal のオフライン推論経路に適用されます。

## 使い方

```sh
strata-hy4-metal --model ./model.strata --tokens ./ids.txt --seg
```

`--model` と `--tokens` は通常のオフライン実行に必要な入力です。上記はコマンド例であり、ここでは実行していません。

## 値と既定値

値を取りません。指定すると真、指定しなければ偽です。引数解析は `--seg` に遭遇したときフラグを `true` にし、同じ指定を複数回しても同じ状態です。値の validation はありません。Metal runner の引数解析で `--seg` を個別に受理し、runner にフラグを渡しています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1521-1525,1725-1728`）。

## 実行時の動作

runner の各 `forward_chunk` 呼び出しで `seg_mode = prof || seg_force` と設定されます。したがって `--seg` または `--prof` のどちらかが有効なら segmented mode になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1296`）。

segmented mode では、`part()` が呼ばれる境界で、それまでに積まれた dispatch 群を `cx.run_graph(ds)` で実行し、dispatch 群を空にします。該当境界は Engram、attention、MLP、head の処理箇所です。GPU 所要時間と section 回数は内部集計 `gpu_total` / `pacc` に加算されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:447-455,1318-1325,1347-1349`）。

通常の非 segmented mode では、prefill が8トークンを超え、cold-experts が無効な場合に7層ごとに dispatch をまとめて実行します。segmented mode ではこのバッチ実行条件から外れます。また、Engram 準備前に dispatch を非同期実行する条件も `!seg_mode` を要求するため、`--seg` によりその非同期経路は使われません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1304-1315,1326-1328`）。

`--seg` 単独では `prof` が真にならないため、prefill/decode 後に `report()` を呼ぶ section timing の表示は有効になりません。表示条件は `prof` であり、`--prof` は `prof` を真にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1521-1524,1814-1817,1968-1974`）。`--prof2` は `prof` と `prof2` の両方を有効にし、さらに演算単位の `op()` 境界でも `part()` を実行します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:456,1521-1524`）。

## 適用条件と副作用

- `--serve` が指定されると、serve 用設定を組み立てて `hy4_serve_main()` に移るため、オフライン runner の `seg_force` は使用されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675`）。
- `--load-only` はモデル読み込み後、runner 構築より前に終了するため、`--seg` の実行効果はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1630-1636`）。
- フラグ自体はファイルやネットワークへの書き込みを行いません。推論本体で GPU command buffer を処理境界ごとに実行するため、通常のバッチ実行・Engram 準備前の非同期実行経路と実行順が異なります。性能上の優劣はこのソース調査からは判断できません。

## 出力とエラー

`--seg` に固有のメッセージやエラー分岐はありません。未知のフラグは `ERR unknown flag ...` を stdout に出し、`unknown arg ...` を stderr に出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608`）。`--model` が指定されない場合も usage を stderr に出し、終了コード 2 です（同 `:1611-1614`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1521-1525` — `--seg` の引数なし parser と初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1725-1728,1291-1296` — runner への受け渡しと `--prof` との mode 判定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:447-455,1318-1328,1347-1349` — segmented mode における dispatch 実行・集計と通常時のバッチ条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675,1814-1817,1968-1974` — `--load-only` / `--serve` の適用範囲と profiling report の条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608,1611-1614` — 未知フラグと必須モデル未指定の失敗経路。
