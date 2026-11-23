# `--index-topk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--index-topk` |
| 別名 | なし |
| 値 | 整数。IndexPool の選択開始位置と、選択したキー位置リストの上限に使われる |

## 役割

長い系列を処理するとき、疎な attention 層が参照するキー位置を IndexPool で選択する境界値を指定する。系列の終端位置がこの値を超えると選択リストを使い、それまでは因果 attention を使う。既定値は `2048`。`--no-index` を併用すると IndexPool 選択自体が無効になる。

## 使い方

```sh
# 通常の推論で、IndexPool の境界を 2048 に指定する（既定値と同じ）
strata-hy4 --model model.strata --tokens prompt.txt --index-topk 2048

# サーバーモードで、境界を 4096 に指定する
strata-hy4 --serve --model model.strata --index-topk 4096
```

## 値と既定値

- 値は `atoi` で整数に変換される。既定値は `2048`。
- このオプション固有の範囲検証、最小値・最大値への補正は parser にない。したがって、ソースから安全な有効範囲は確定できない。IndexPool の選択処理では `index_topk / kpool - 1` を選択数に使い、確保サイズや attention の `kmax` にも値を使うため、通常は正の整数を指定する必要がある。
- 同じオプションを複数回指定した場合、引数列を順に処理して変数へ代入するため、最後の指定値が残る。
- 値を省略すると `nxt()` が標準出力へ `ERR --index-topk needs a value` を出して終了コード `2` で終了する。数値としての妥当性を検査する個別エラー経路はない。

## 実行時の動作

parser は値を `index_topk` に設定し、`--serve` の場合は `ServeOpts` に渡す。通常の推論では `Runner::index_topk` に設定される。両経路とも `--no-index` の有無は別の `index_on` / `no_index` フラグで伝わる。

疎な層では、処理チャンクの終端位置 `end_pos` が `index_topk` を超える場合に IndexPool のキー位置選択を行い、attention を `MLA_LIST` モードにして `kmax = index_topk` を渡す。閾値以下では因果 attention のまま。窓付き attention 層はこの分岐の対象外。選択カーネルは各トークンについてスコア上位の pool を選び、その pool 内の位置と自身の pool までの位置をキーリストとして出力する。

`--no-index` を併用した場合は IndexPool 選択が無効になり、値が指定されていても上記のリスト選択条件を満たさない。

## 適用条件と副作用

- 対象は `strata-hy4` の CUDA/HIP 実装。Metal と SYCL にも同名オプションが索引掲載されているが、別 parser・別実装なので本書では扱わない。
- 指定値は推論と `--serve` の双方で使われる。値に応じて疎な層の attention が使うキー位置数と IndexPool 関連バッファのサイズが変わる。
- `--no-index` は選択の適用を切り替える別オプションであり、`--index-topk` の指定順で上書きされない。

## 出力とエラー

確認できた専用エラーは値の欠落時の標準出力メッセージと終了コード `2`。値の範囲や数値形式を拒否する `--index-topk` 固有の validation は見つからなかった。後続の GPU 実行時に不適切な値がどう失敗するかは、ソースから一律には特定できないため記載しない。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:352` — 既定値 `2048`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,494` — 値の消費方法、欠落時エラー、`atoi` による変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-563,695-696` — serve / 通常推論への値と `--no-index` の引き渡し。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-49,306-310` — serve 側の設定と Runner への伝播。
- `engine/src/hy4flash/run/hy4_graph.hip.h:220-221,1642-1650` — Runner の既定値・意味、IndexPool バッファ確保。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2018-2045,2127-2165` — 上位 pool 選択と、閾値超過時のリスト attention への切替。
- `engine/src/hy4flash/run/hy4_indexer.hip.h:142-157` — 選択済み pool と現在位置までのキーリスト生成。
- `engine/src/hy4flash/run/hy4_graph.hip.h:3050-3061` — グラフ実行経路における閾値判定と `kmax`。
