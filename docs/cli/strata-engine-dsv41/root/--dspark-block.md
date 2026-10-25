# `--dspark-block`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立した DeepSeek-V4.1 engine CLI） |
| オプション | `--dspark-block N` |
| 別名 | なし |
| 値 | 整数。DSpark が1ラウンドで出す draft token 数の上限。 |

## 役割

DSpark speculative decoding の各ラウンドで使う draft token 数を上限指定します。pack が持つ DSpark block 全体のサイズを変更する指定ではありません。モデルから生成された draft と対応する confidence 配列を、指定上限に合わせて切り詰めます。

## 使い方

```sh
strata-dsv41 --pack ./models/example/maya-ds4 --ids 1,2,3 --n 64 --dspark-block 3
```

`--pack` には準備済み pack を指定します。この CLI は `STRATA_BUILD_DSV41` を有効にした build で生成される独立 executable です（`CMakeLists.txt:797-811`）。

## 値と既定値

- parser は値を `std::atoi` で整数化し、`std::max(0, value)` を保存します。負数は `0` になり、整数として解釈できない文字列も `atoi` の結果 `0` になります。厳密な書式・範囲検証やエラー報告はありません（`src/dsv41/ds4_main.cpp:1202-1208,1230`）。
- 値を省略してオプションだけを末尾に置くと `needs a value` を stderr に出して終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1202-1206`）。
- `--dspark-block` を複数回指定すると、parser が `o.dspark_block` を順に代入するため最後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1231`）。
- 省略時の `o.dspark_block` は `0` です。`0` は明示しても上限なしと同じ扱いになり、pack の DSpark block の範囲が使われます（`src/dsv41/ds4_model.hpp:45-48`）。

## 実行時の動作

実行時の上限変数 `max_drafts` は、環境変数 `DS4_DSPARK_MAX` が存在すればその値を `atoi` で読み、存在しなければ `0`（上限なし）で初期化されます。モデル load 時、CLI 値が正数で、かつ `DS4_DSPARK_MAX` が未設定の場合にだけ、`max_drafts` を CLI 値で上書きします。したがって `DS4_DSPARK_MAX` は CLI より優先され、環境変数が `0`、負数、または数値に解釈できない値でも、変数が存在する限り CLI の正数指定は適用されません（`src/dsv41/ds4_model.cu:911-915,2009-2010`）。

draft 生成後、`max_drafts > 0` かつ生成数が上限より多い場合に、draft token と confidence の両配列を同じ長さへ縮めます。pack metadata の `dspark_block_size` はモデル設定の `d_block` として読み込まれ、draft 側のブロック長に使われます。このオプションはその block size 自体を変更せず、出力候補の数を制限します（`src/dsv41/ds4_model.cu:398-429,6447-6452,6457-6465`）。

## 適用条件と副作用

- DSpark drafter が利用可能な pack でのみ draft 数に影響します。モデル load 時に pack の `dspark_block_size` が正で、MTP tensor が揃っている場合に DSpark block を認識します（`src/dsv41/ds4_model.cu:423-429`）。
- `--dspark` の指定や自動判定により `g.n_mtp` が `0` になると、draft 関数は空の候補を返すため、本オプションによる上限調整は実質的にありません（`src/dsv41/ds4_model.cu:1997-2010,6460-6463`）。
- 正の上限が適用されると、各ラウンドで後続の検証に回す draft 候補が減ります。ここでは性能向上や品質への影響を測定していません。
- オプション自体はファイルやネットワークを操作しません。モデル load、GPU 実行など通常の engine 動作に伴う副作用は、この上限指定固有のものではありません。

## 出力とエラー

有効な指定値について、このオプション固有の確認メッセージや警告はありません。値なしの場合は上記の通り stderr に不足を表示し終了コード `2`、未知のオプションの場合も usage を stderr に出して終了コード `2` です（`src/dsv41/ds4_main.cpp:1202-1206,1266-1272`）。無効な数値文字列は拒否されず `0` となるため、pack の既定範囲を使う挙動になります。

## 根拠

- CLI usage と parser、値の変換・不足時の扱い: `src/dsv41/ds4_main.cpp:85-94,1200-1231`
- 既定値および DSpark 関連 option state: `src/dsv41/ds4_model.hpp:42-48`
- pack metadata からの block size と MTP block 認識: `src/dsv41/ds4_model.cu:398-429`
- `DS4_DSPARK_MAX` の初期化と CLI 値の優先順位: `src/dsv41/ds4_model.cu:911-915,1997-2010`
- draft/confidence 配列の上限制御と pack block の利用: `src/dsv41/ds4_model.cu:6437-6465`
- CLI の独立 executable と build 条件: `CMakeLists.txt:797-811`
- 対象 checkout の状態: `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）。

同一 revision の `strata-dsv41 --help` は実行していません。source parser と使用箇所を確認し、索引の `strata-engine-dsv41/root/--dspark-block.md` と一致することを確認しました。配布済み Release binary の有無は調査していません。
