# `--dspark-conf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 engine CLI） |
| オプション | `--dspark-conf` |
| 別名 | なし |
| 値 | 浮動小数点数として扱う値 `F`。コード上の範囲検証・clamp はない |

## 役割

DSpark speculative decoding で、draft token の sigmoid confidence が採用候補になるための下限を指定します。各 draft の confidence がこの値以上である間、draft をまとめて trunk で検証します。値を高くすると通過する draft が減り得ますが、性能への効果はモデル・GPU・入力に依存し、この調査では測定していません。判定処理は `src/dsv41/ds4_main.cpp:167-203`、confidence の生成は `src/dsv41/ds4_model.cu:6437-6455` にあります。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 1,2,3 --n 64 --dspark-conf 0.65
```

`--dspark-conf` は `--ids` と `--n` を使う通常の生成経路、`--serve`、`--spec-eval` の DSpark 判定に関係します。engine の usage にも `--dspark-conf F` と記載されています（`src/dsv41/ds4_main.cpp:85-93`）。

## 値と既定値

- parser は次の argv を文字列として読み、`std::atof` で `float` に変換します。値を省略すると stderr に `--dspark-conf needs a value` を出し、終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1200-1208,1229`）。
- 値の範囲や形式を検証する処理はありません。数値に変換できない文字列は `atof` の結果として `0` になります。負数や 1 を超える値も parser では拒否・補正されず、そのまま下限比較に渡されます（同 `:1229`、判定 `:181-183`）。
- 省略時の engine 設定値は `0.5f` です（`src/dsv41/ds4_model.hpp:42-48`）。通常生成と `--spec-eval` はこの値を `round` に渡します（`src/dsv41/ds4_main.cpp:1296-1300,1400-1403`）。
- `--serve` では CLI 値が server の既定値になります。各 `GEN` / `GENI` 要求に `dspark_conf=F` を付けると、0 以上の要求値で engine 値を上書きします。要求値が負なら engine 値へフォールバックします（request parser `src/dsv41/ds4_main.cpp:304-315`、適用 `:896-900`）。

## 実行時の動作

`round` は speculative decoding が有効で、残り生成枠が 1 より大きく、モデルに draft block がある場合に DSpark draft を生成します。各 draft の confidence が `conf_min` 以上である間、さらに `room - 1` 枠を超えない範囲で候補を残し、残った候補を trunk で検証します。最初の draft が下限未満なら候補を検証せず、通常の1 token stepに進みます（`src/dsv41/ds4_main.cpp:167-203`）。

通常生成では `--dspark-conf` の値が `round` に直接渡され、`--spec-eval` も同じ engine 設定値を使います。`--serve` は要求ごとに `dspark_conf` を指定できます（`src/dsv41/ds4_main.cpp:1296-1300,1400-1403`、server 経路 `:896-900`）。

## 適用条件と副作用

- `--dspark off` は speculative decoding を無効にするため、この下限による draft 採否は行われません。`--dspark none` は drafter 自体を読み込まない設定です（`src/dsv41/ds4_main.cpp:1224-1229`）。
- `--dspark auto`（既定）では、GPU の空き領域に対して routed experts が大きすぎる場合に DSpark をロードせず、警告を stderr に出します。その場合もこの値による採否は発生しません（`src/dsv41/ds4_model.hpp:42-48`、`src/dsv41/ds4_model.cu:1998-2010`）。
- 採否に使う confidence は draft 段階で計算されます。モデルの draft block がない、残り生成枠が 1 以下、または speculative decoding が無効なら、`--dspark-conf` はその round の生成に影響しません（`src/dsv41/ds4_main.cpp:172-183`）。
- この option 自体がファイルやネットワークへ書き込む処理は確認できません。server の要求値は入力行から読み込まれ、要求単位で閾値として使われます（同 `:304-315,896-900`）。

## 出力とエラー

option 固有の範囲エラーや警告はありません。値が欠けた場合は前述の通り終了コード `2` です。未知の option は `unknown option ...` と usage を stderr に出して終了コード `2` になります（`src/dsv41/ds4_main.cpp:1202-1208,1266-1272`）。モデルの読み込み失敗や draft / verify の失敗は別の経路でエラーを出します（モデル読み込み `:1289-1294`、server `:898-903`、通常生成 `:1400-1405`）。

## 根拠と調査範囲

- `src/dsv41/ds4_main.cpp:85-93` — CLI usage 表記。
- `src/dsv41/ds4_main.cpp:1200-1208,1224-1230` — parser、値変換、DSpark 関連 option との関係。
- `src/dsv41/ds4_main.cpp:167-203` — draft confidence 下限の実際の適用と通常 step への分岐。
- `src/dsv41/ds4_main.cpp:206-218,304-315,896-900` — server 要求の `dspark_conf` と engine 値へのフォールバック。
- `src/dsv41/ds4_main.cpp:1296-1300,1400-1405` — serve、spec-eval、通常生成への値の伝播。
- `src/dsv41/ds4_model.hpp:42-48` — engine 側の初期値と DSpark 設定。
- `src/dsv41/ds4_model.cu:1998-2010,6437-6455` — auto による drafter 無効化と draft 処理。

調査は上記 checkout の source に限定しました。索引上、この CLI は `STRATA_BUILD_DSV41=ON` で生成される optional engine executable です（`docs/cli/README.md:1353-1357`）。同一 revision の既存 CLI help 実行や Release 配布物の確認は行っていないため、Release での配布状況は記載していません。
