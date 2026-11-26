# `--adapt-decay`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root parser） |
| オプション | `--adapt-decay` |
| 別名 | なし |
| 値 | 浮動小数点数。有限値 `0..1`（両端を含む） |

## 役割

適応型 expert cache が各適応処理の後に routing 使用数を何倍に減衰させるかを指定します。値が小さいほど過去の使用数の影響が早く薄れ、`0` は直前までの累積を消し、`1` は減衰しません。これは expert residency の選択に使う使用数の設定で、適応型 tier が有効な経路でのみ作用します（`engine/include/strata/program/adapt_decay.hpp:2-5,13-20`、`engine/src/program/generate.cpp:15342-15346,15349-15379`）。

## 使い方

```sh
strata --adapt-decay 0.85 --adapt-every 4 --adapt-swaps 96 ...
```

`...` はモデル等の通常の `strata` 引数に置き換えます。`--adapt-every` と `--adapt-swaps` は適応処理の有効化・周期・交換数を指定する別オプションです。

## 値と既定値

- 既定値は `0.7` です（`engine/src/program/generate.cpp:1052`、同じ parser を持つ SYCL 実装では `engine/sycl/src/program/generate.cpp:695`）。
- finite かつ `0 <= 値 <= 1` の場合は float に変換して採用します。`0` と `1` も有効です（`engine/include/strata/program/adapt_decay.hpp:11-20`）。
- parser は値を `std::atof` で変換し、専用 helper が変換結果を検証します。数値文字列全体の厳密な構文検査は parser にありません（`engine/src/program/generate.cpp:4059`）。
- 範囲外または NaN / infinity は拒否終了せず、stderr に警告を出して `0.7` に置き換えます（`engine/include/strata/program/adapt_decay.hpp:15-20`）。
- 値を省略すると parser の `next` が `--adapt-decay needs a value` を stderr に出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3846`）。同じオプションを複数指定した場合は parser が各出現を順に処理して値を代入するため、最後に処理された値が残ります（`engine/src/program/generate.cpp:3842-3847,4059`）。

## 実行時の動作

適応処理時には routing usage を snapshot し、その後も保持する累積 usage の各要素にこの係数を掛けます。次回以降の適応処理では減衰後の値が使われます（`engine/src/program/generate.cpp:15342-15346,15804-15812,25188-25191`）。候補 expert と resident expert の使用数比較に基づいて cache の入れ替えを行う処理であり、減衰率はその後の比較値に影響します（`engine/src/program/generate.cpp:15349-15379`）。同じ減衰処理は speculative loop にもあります（`engine/src/program/generate.cpp:25188-25191`）。

適応 usage は `--adapt-every > 0` かつ `--adapt-swaps > 0` で、GPU 側に resident slot があり全 expert が resident ではない場合など、利用可能な cache 経路で初期化されます。tier が無効または該当 cache 経路がなければ、この値を使う適応処理は行われません（`engine/src/program/generate.cpp:15000-15002,24563-24570`）。

相互作用として、mid-coverage の適応既定値が適用されると、値を明示していない場合に decay は `0.92` になります。明示した `--adapt-decay` は `adapt_decay_given` に記録され、この補正を抑止します。mid-coverage は resident slot の割合が 15%〜65% の範囲で、適応 tier が有効な場合に判定されます。`STRATA_ADAPT_MID=1` / `0` で有効・無効を指定でき、未設定などの場合の build 既定は CUDA で有効、HIP で無効です（`engine/src/program/generate.cpp:1053,4059,12145-12163,14945-14964,24558-24568`、`engine/include/strata/core/adapt_coverage_rules.hpp:20-38`）。関連: [`STRATA_ADAPT_MID`](../../../envvars/STRATA_ADAPT_MID.md)。

SYCL parser にも同じ値と helper validation があり、usage 減衰に使われます（`engine/sycl/src/program/generate.cpp:695,2053,8844-8848,9287-9292,14183-14188`）。この実装では `adapt_decay_given` による mid-coverage 上書き抑止を確認できません。したがって上記 `0.92` の明示値優先の説明は `engine/src/program/generate.cpp` の parser / 経路についてのものです。

## 適用条件と副作用

このオプションは cache residency の適応に使う累積 routing usage を変更し、適応処理が行われるごとにその値を縮小します。単独では適応 tier を有効化しません。適応の周期・交換数を無効にする設定や、適応用 usage が作られない実行条件では、decay の効果もありません（`engine/src/program/generate.cpp:15000-15002,15342-15346,15349-15379,24563-24570`）。

## 出力とエラー

- `0..1` の範囲外または非有限値は parser エラーにならず、stderr に `strata: --adapt-decay ... is not between 0 and 1; using 0.7 ...` の警告を出して続行します（`engine/include/strata/program/adapt_decay.hpp:15-20`）。
- 値がない場合は stderr に不足を表示し、終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- mid-coverage の既定値変更が実際に起きた場合、通常 parser 経路は stderr に変更前後の decay を含む適応既定値のメッセージを出します（`engine/src/program/generate.cpp:12159-12163,14960-14964`）。非 serve decode 経路ではこの補正箇所からの個別メッセージは確認できません（`engine/src/program/generate.cpp:24558-24568`）。

## 根拠

記載した実装は調査対象 commit のソースで確認しました。主な根拠は `engine/src/program/generate.cpp:1052-1053,3842-3847,4059,12145-12164,14945-14964,15000-15002,15342-15379,15804-15812,24558-24570,25188-25191`、validation helper の `engine/include/strata/program/adapt_decay.hpp:11-20`、適用条件の `engine/include/strata/core/adapt_coverage_rules.hpp:20-38`、SYCL 実装の `engine/sycl/src/program/generate.cpp:695,2053,8844-8848,9287-9292,14183-14188` です。
