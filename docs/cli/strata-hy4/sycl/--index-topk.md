# `strata-hy4-sycl --index-topk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（root） |
| オプション | `--index-topk` |
| 別名 | なし |
| 値 | 整数。`atoi` で変換される。 |

## 役割

HY4 SYCL エンジンの疎な attention で、過去 token の index list を使い始める系列位置のしきい値を指定する。通常の実行と `--serve` の両経路で同じ値が Runner に渡る。しきい値以下の系列位置では因果 attention を使い、超えた位置では IndexPool による選択結果の list を使う。`--no-index` を指定すると indexer 自体が無効になり、この切替は行われない。

## 使い方

```sh
# 通常実行でしきい値を 4096 に指定
strata-hy4-sycl --model model.strata --engram engram.strata --tokens ids.txt --index-topk 4096

# serve モードでも同じ値を指定
strata-hy4-sycl --serve --native model.strata --engram engram.strata --index-topk 4096
```

## 値と既定値

値は `atoi` で `int` に変換される。省略時は `2048`。明示値に対する正数・範囲・モデル設定との整合性の検証は parser に見当たらない。オプションを複数回指定した場合、引数を順に処理して変数を再代入するため最後の値が残る。数値としての妥当性は検証されず、入力の受理範囲や変換失敗時の診断はこの parser からは確認できない。

## 実行時の動作

parser は `--index-topk` の次の引数を `atoi` で読み、`index_topk` に設定する（`engine/src/hy4flash/sycl/sy_main.cpp:104,175`）。通常実行では Runner の `index_topk` に代入され（同 `:283-289`）、serve モードでは `ServeOpts` を経由して Runner に渡る（同 `:226-248`; `engine/src/hy4flash/sycl/sy_serve.h:28-33,262-265`）。

非スライディング窓の attention では、indexer が有効なとき `max_pos`（通常は `p0 + T`）が値を超えると index 選択を実行し、その list を attention に使う。超えない間は因果 attention を使う。選択数の計算にも値を使い、`n_top = index_topk / c.kpool - 1` として IndexPool に渡し、attention の list 上限 `kmax` にも渡す（`engine/src/hy4flash/sycl/sy_graph.h:921-948,992-1028`）。グラフ経路も同じ `max_pos > index_topk` 条件で attention mode を決める（同 `:1246-1254`）。

`--no-index` は別オプションで、Runner の `index_on` を無効にする（`engine/src/hy4flash/sycl/sy_main.cpp:175-176,288-289`）。その場合、非スライディング窓の attention は index list へ切り替わらない（`engine/src/hy4flash/sycl/sy_graph.h:992-1007`）。

## 適用条件と副作用

効果があるのは IndexPool を使う非スライディング窓の attention で、スライディング窓の層にはこの分岐を適用しない（`engine/src/hy4flash/sycl/sy_graph.h:951-1007`）。`--no-index` が有効な場合も適用されない。値は list 用バッファの大きさ、選択数、および attention の list 上限にも使われる（同 `:933-947,1022`; `engine/src/hy4flash/sycl/sy_graph.h:575`）。したがって既定値から変更すると GPU メモリ使用量や選択・attention の計算経路に影響し得るが、性能への効果はソースからは断定できない。

parser には正数などの値検証がない。負数や極端な値を指定した場合の安全な動作は確認できず、ソースだけから推奨範囲を確定できないため、既定値以外の範囲を案内しない。

## 出力とエラー

値がない（最後の引数として指定した）場合、`ERR --index-topk needs a value` を標準出力へ出し、終了コード `2` で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,175`）。値の形式・範囲エラー専用の検証や診断は parser にない。通常の推論出力や初期化失敗の出力形式はこのオプション固有ではないため、ここでは扱わない。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104,175` — 既定値、値の読み取りと整数変換。
- `engine/src/hy4flash/sycl/sy_main.cpp:109-115` — 値省略時の標準出力メッセージと終了コード。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,283-289` — serve / 通常経路での値の引き渡しと `--no-index` の設定。
- `engine/src/hy4flash/sycl/sy_serve.h:28-33,262-265` — serve 設定から Runner への伝播。
- `engine/src/hy4flash/sycl/sy_graph.h:921-948,992-1028,1246-1254` — index 選択条件、選択数、attention mode と list 上限。
- `engine/src/hy4flash/sycl/sy_graph.h:575` — `index_topk` を使う index list バッファ確保。
