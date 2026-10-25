# `--dump-halves`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（索引上の配置: `root/`） |
| オプション | `--dump-halves` |
| 別名 | なし |
| 値 | 必須の出力先パス |

## 役割

各生成位置について、各レイヤーの attention/mixer 側と MoE 側の `block_out`、および両側の `inject` を含む中間値をバイナリに書き出します。レイヤー間の差異を二つの half の境界まで追跡する診断用オプションです。QSA 経路では attention の中間値も同じレコードに含まれます。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --dump-halves /tmp/strata-halves.bin
```

`--no-capture` とは併用できません。通常の captured layer path で実行してください。

## 値と既定値

- `PATH` は次の argv 要素をそのまま受け取ります。値の拡張子・形式・書き込み可能性について、オプション固有の事前 validation はありません。`--dump-halves` の後に値がなければ `--dump-halves needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2421`, `2471`）。
- 省略時は空文字列のままで、ダンプ用ファイルを開きません。明示したパスが空文字列でも同じく無効です。複数回指定した場合は parser が同じ文字列フィールドを順次代入するため、最後の値が使われます（`src/program/generate.cpp:501`, `2471`, `4002`）。
- 指定すると `fopen(PATH, "wb")` で開くため、新規作成または既存ファイルの切り詰めが起きます。開けない場合は `strata generate: cannot write PATH` を stderr に出し、終了コード 1 です（`src/program/generate.cpp:4000-4006`）。

## 実行時の動作

ファイルはヘッダーなしの float 配列です。各生成位置につき、レイヤー番号の昇順で `n_layers` 個の固定長レコードを書きます。レコード長は次の float 数です。

```text
2*n_embd + 2*hc + n_head*head_dim + 5*n_head_kv*head_dim + 8
```

先頭の `2*n_embd` は二つの half の `block_out`、続く `2*hc` はそれぞれの `inject` です。残りの予約領域は QSA 経路の attention、v、pool/indexer 等のダンプ領域です。QSA 以外のモデル・経路で全領域が埋まるとは限りません。型はファイル書き込み側とステージング側で `float` です（`src/program/generate.cpp:3997-4014`, `15972-15974`; stride と領域配置: `src/core/layer.cpp:1435-1453`）。

ステージング領域を layer graph の capture 前に割り当て、`ss.block.dump` に設定します。各 layer の `block_layer_pre` / `block_layer_post` が `block_out` と `inject` をコピーし、QSA の場合はその内部処理も同じ領域へコピーします。コピーは CUDA stream 上の device-to-host 非同期コピーとして enqueue されます。capture したグラフを各位置で replay した後、`n_layers * stride` 個の float をファイルへ書きます（`src/program/generate.cpp:3994-4014`, `src/core/layer.cpp:1128-1131`, `1201`, `1227`, `1293`, `1435-1457`, `1546-1548`, `1614`, `src/program/generate.cpp:15972-15974`）。

## 適用条件と副作用

- オプションは dump コピーを layer graph に capture する方式です。`--no-capture` では出力を記録できないため、組み合わせると `--dump-halves is CAPTURED into the layer graphs...` の診断を stderr に出し、終了コード 2 で拒否します（`src/program/generate.cpp:6989-6995`）。
- `half_dump` が有効な場合、token graph capture と token-graph expert-hit 経路の条件から外れ、layer graph と通常の layer loop を使います（`src/program/generate.cpp:7406`, `7471`）。他の dump と併用する明示的な排他 validation は確認できません。
- pinned host staging buffer は `n_layers * stride` 個の float 分を確保します。確保に失敗すると `strata generate: cannot pin the half-dump staging buffer` を stderr に出し、終了コード 1 です（`src/program/generate.cpp:4007-4011`）。
- 出力先は `wb` で開くため既存内容を保持しません。各位置のレコード書き込み結果と最後の `fclose` の戻り値はこの経路では検査されず、書き込み失敗を明示的に報告する処理は確認できません（`src/program/generate.cpp:15972-15974`, `16853-16858`）。正常終了時は stdout に `halves dumped PATH (N layers x S per position)` を表示します。

## 出力とエラー

確認できた失敗経路は、引数値の欠落（終了コード 2）、出力ファイルを開けない場合（終了コード 1）、pinned staging buffer を確保できない場合（終了コード 1）、および `--no-capture` との併用（終了コード 2）です。未知の引数は `unknown argument: ...` と usage を stderr に出し、終了コード 2 で拒否されます（`src/program/generate.cpp:2785-2795`）。

## 根拠

- 索引とスコープ: `docs/cli/README.md` の `strata-engine` 説明および `--dump-halves` の項目。
- parser と usage: `src/program/generate.cpp:885`, `2418-2421`, `2471`, `2785-2795`。
- ファイル作成、stride、capture 前の staging: `src/program/generate.cpp:3994-4014`。
- データ領域、非同期コピー、QSA の追加領域: `src/core/layer.cpp:1128-1131`, `1201`, `1227`, `1293`, `1435-1457`, `1546-1548`, `1614`。
- 位置ごとの書き込み、終了時表示: `src/program/generate.cpp:15972-15974`, `16853-16858`。
- 適用条件と graph 選択: `src/program/generate.cpp:6989-6995`, `7406`, `7471`。
