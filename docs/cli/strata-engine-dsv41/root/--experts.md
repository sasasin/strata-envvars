# `--experts`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立した DeepSeek-V4.1 engine executable） |
| オプション | `--experts` |
| 別名 | なし |
| 値 | routed expert 数を表す整数、または小文字の `auto` |

## 役割

各 token について router が選ぶ routed expert 数を指定します。モデルが本来選ぶ数より小さくすると、選ばれた expert の routing weight はその選択集合内で正規化されます。`auto` または未指定では、選択 GPU の VRAM と integrated GPU の有無による faster-mode rule が適用されます。

## 使い方

```sh
strata-dsv41 --pack /models/maya-ds4 --ids 1,2,3 --n 16 --experts 6
```

`--experts auto` を指定すると、既定の faster-mode rule を明示的に使います。`--pack` と実行モード（例では `--ids`）も必要です（usage: `src/dsv41/ds4_main.cpp:85-93`）。

## 値と既定値

- オプション値は必須です。parser は `auto` だけを特別扱いし、その他の文字列を `std::atoi` で整数化して最低 `1` に丸めます。したがって `0`、負数、整数に変換できない文字列は `1` になり、厳密な数値形式検証はありません（`src/dsv41/ds4_main.cpp:1200-1207,1230-1233`）。
- 変換後の数がモデルの `num_experts_per_tok` より大きい場合、実行時にモデル本来の数へ上限丸めされます。最小値は `1` です（`src/dsv41/ds4_experts_rule.hpp:17-25`）。
- 未指定時の内部値は `-1` で、`auto` も `-1` にします。モデルの本来の選択数が1以下ならその値を保ちます。それ以外では、integrated GPU がある場合、または選択 GPU 群の総 VRAM が16 GiB以下の場合は5、それ以外はモデル本来の選択数を使います（`src/dsv41/ds4_model.hpp:45-49`、`src/dsv41/ds4_experts_rule.hpp:14-25`）。モデルごとの本来の数は pack の `num_experts_per_tok` から読み込みます（`src/dsv41/ds4_model.cu:404-410`）。
- 値を省略すると `--experts needs a value` を stderr に出して終了コード2です。同じオプションを複数回指定すると最後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1207,1230-1233`）。

## 実行時の動作

モデル load 時、trunk の最初の layer で GPU 群の総 VRAM と integrated GPU の有無を調べ、指定値または自動ルールで選択数を決めます。決定値は全 trunk layer の `k_exp` に適用されます。モデル本来の数より少ない場合、stderr に `experts per word: N (...)` と full-quality 用の数を表示します（`src/dsv41/ds4_model.cu:2038-2064`）。

決定された数は router の top-k 数として使われ、token ごとにその数だけ expert ID と weight が出力されます。kernel は選択された expert の重みを合計で割り、`route_scale` を掛けて routing weight を計算します。その後の expert 実行と出力合成も `k_exp` 個を処理します（`src/dsv41/ds4_kernels.cu:501-548`、`src/dsv41/ds4_model.cu:7273-7284,9151-9187`）。

環境変数 `DS4_TOPK` が設定され、`atoi` で得られる値が `1..model_k` の範囲なら、その値が `--experts` と自動ルールの結果を上書きします。範囲外や有効な整数に変換されない値は無視されます（`src/dsv41/ds4_experts_rule.hpp:62-69`）。この環境変数はソースコメント上テスト用です。

DSpark の MTP layer は pack の `dspark_num_experts_per_tok` を使い、このオプションによる trunk の `experts_used` を適用しません（`src/dsv41/ds4_model.cu:2040-2045,2063-2069`）。DSpark の有効・無効は別途 `--dspark` などで制御されます。

## 適用条件と副作用

- この parser は独立 executable `strata-dsv41` のものです。CMake の `STRATA_BUILD_DSV41=ON` で target が定義されます（`CMakeLists.txt:797-811`）。索引もこの独立 CLI を `strata-engine-dsv41/root` に分類しています（`docs/cli/README.md:1373-1388`）。Release での配布有無はこの調査では確認していません。
- expert 数を減らすと router の選択集合が短くなり、残った expert の weight が再正規化されます。モデル標準の選択数による出力との同一性は保証されません。実測なしに速度向上幅は断定できません。
- 明示的な数値は最大でもモデル本来の数に丸められ、少なくとも1です。VRAM 条件による自動選択は model load 時に一度決まり、実行中に再評価される処理は確認できません。
- `--experts` 自体がファイルを書き換える処理は確認できません。モデルの load・推論に伴う他の処理や profile 保存は別の設定・経路です。

## 出力とエラー

- 値の欠落は stderr に `--experts needs a value`、終了コード2です。未知の option は `unknown option ...` と usage を stderr に出し、終了コード2です（`src/dsv41/ds4_main.cpp:1200-1207,1266-1276`）。
- 自動ルールまたは明示数がモデル本来の数より少ない場合、stderr に選択数と full-quality 用の `--experts N` を表示します。明示値がモデル本来の数と等しいときは full-quality の行を表示します（`src/dsv41/ds4_model.cu:2055-2062`）。
- option 固有の値 validation error はありません。モデルの load が失敗した場合は `maya-ds4: <理由>` を stderr に出し、終了コード1で終了します（`src/dsv41/ds4_main.cpp:1293-1297`）。

## 根拠

- 索引の階層・option リンク: `docs/cli/README.md:1373-1388`
- usage と parser、値変換、unknown option の失敗経路: `src/dsv41/ds4_main.cpp:85-93,1200-1207,1230-1233,1266-1276`
- 内部既定値、モデル metadata の本来の選択数、自動ルールと clamp: `src/dsv41/ds4_model.hpp:42-49`、`src/dsv41/ds4_model.cu:404-410,2038-2064`、`src/dsv41/ds4_experts_rule.hpp:14-25`
- `DS4_TOPK` の優先順位と範囲確認: `src/dsv41/ds4_experts_rule.hpp:62-69`
- router weight の計算と `k_exp` の利用: `src/dsv41/ds4_kernels.cu:501-548`、`src/dsv41/ds4_model.cu:7273-7284,9151-9187`
- MTP layer への適用条件: `src/dsv41/ds4_model.cu:2040-2045,2063-2069`
- optional executable の build 条件: `CMakeLists.txt:797-811`

