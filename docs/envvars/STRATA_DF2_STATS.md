# `STRATA_DF2_STATS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal backend の DFlash2 実装で、context graph の所要時間、draft の定期統計、serve 時の lineage 探索・復元状況を stderr に出す診断用スイッチです。計算方式や DFlash2 の選択を切り替える変数ではありません。読み取り箇所は `metal/src/engine/dflash2.inc` の4箇所だけで、CUDA/HIP の DFlash2 実装がこの変数を読む箇所はありません。

## 値と判定

4箇所とも `std::getenv("STRATA_DF2_STATS") != nullptr` で設定有無だけを調べます。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効 |
| その他の設定値（`0`、`false` を含む） | 有効 |

文字列比較、数値変換、範囲検査、無効値時の fallback はありません。CLI 引数や他の環境変数による上書きもありません。

各読み取りは関数内 `static const bool` に保存されます。したがって各ログ箇所は初回到達時の値を個別に記憶し、その箇所が到達した後の環境変更では再評価されません。4箇所が初めて評価される時点は同一とは限りません（`metal/src/engine/dflash2.inc:702-703,784-788,903-905,982-984`）。

## 有効になる条件

- Metal の Window 実装で DFlash2 の対応処理が呼ばれる必要があります。DFlash2 drafter の `context()` / `draft()` は Metal decode window に処理を委譲し、window がない場合や bind されていない場合は失敗します（`metal/src/engine/dflash2.inc:1057-1064,1072-1083,1086-1097`）。通常のモデル生成で DFlash2 を選ぶ入口は `--draft dflash2` です（`src/program/generate.cpp:987-995,1157-1165,3572-3585`）。
- context graph の行数ログは、実行した chunk の `nb` が16より大きい場合だけ出ます。小さい chunk では設定してもこのログは出ません（`metal/src/engine/dflash2.inc:684-703`）。
- draft の周期統計は `d.steady > 0` かつ `d.steady % 150 == 0` のときだけ出ます。steady counter は2回目以降の round で、初回の graph 構築時間を計上しない場合に増えます（`metal/src/engine/dflash2.inc:767-788`）。
- stash の履歴比較ログは lineage 復元処理が stash を走査したときに各候補について出ます。復元サマリーは実際に行を再構築し、`from < r_end` で関数が成功経路に進んだ場合に出ます（`metal/src/engine/dflash2.inc:877-905,929-984`; 呼び出し元 `metal/src/engine/dflash2.inc:1114-1128`）。

## 実行時の詳細

有効時に追加される stderr 出力は次のとおりです。

- 17行以上の context chunk ごとに、行数、dispatch 数、graph 構築時間、graph 実行時間を出します（`metal/src/engine/dflash2.inc:700-703`）。
- 150 steady rounds ごとに、GPU の平均時間、`run_graph` の平均時間、graph 前の host 時間を出します（`metal/src/engine/dflash2.inc:782-788`）。
- request の lineage を復元する際、stash 候補ごとの履歴長・floor・request との共通 prefix を出します（`metal/src/engine/dflash2.inc:899-906`）。復元が行われた場合は再構築行数・範囲・時間・stash 数のサマリーを出します（`metal/src/engine/dflash2.inc:979-984`）。

これらは観測用ログで、変数を設定したことで失敗・終了・fallback が発生する分岐はありません。関連して Window の破棄時には DFlash2 round が1回以上あれば集計行を無条件で出します。この終了時サマリーは `STRATA_DF2_STATS` によるものではありません。serve 経路で Window の destructor を通らず終了する場合がある旨は `metal/src/engine/dflash2.inc:785` の注釈にあります。

## 根拠

- 全読み取り箇所と判定、統計ログ: `metal/src/engine/dflash2.inc:702-703,784-788,903-905,982-984`。
- Metal DFlash2 の bind / context / draft 呼び出し経路: `metal/src/engine/dflash2.inc:1044-1097`。
- lineage の復元呼び出し条件: `metal/src/engine/dflash2.inc:1114-1128`。
- DFlash2 の CLI 選択と説明: `src/program/generate.cpp:987-995,1157-1165,3572-3585`。
- 終了時の Window destructor 集計呼び出し: `metal/src/engine/window.cpp:1752-1756`; 集計出力本体: `metal/src/engine/dflash2.inc:843-849`。
