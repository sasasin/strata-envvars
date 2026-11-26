# `--lookup-chain-min`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--lookup-chain-min` |
| 別名 | なし |
| 値 | `M`。整数として変換され、最小値は 3。 |

## 役割

`--lookup-chain` が MTP のドラフト列の後ろに prompt-lookup の候補をつなぐとき、候補が基づく一致長の最低値をトークン数で指定します。一致長には未検証のドラフトも含まれます。既定値は 3 で、指定値が 3 未満なら 3 に補正されます。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --lookup-chain 4 --lookup-chain-min 5
```

この例では lookup chain を最大 4 トークンまで試し、一致長が 5 トークン以上の候補を受け付ける設定です。トークン列は例示用です。

## 値と既定値

- 値は必須です。省略すると parser の共通値取得処理が `--lookup-chain-min needs a value` を標準エラーに出して終了コード 2 で終了します。
- 既定値は 3 です。
- parser は `std::atoi` で変換した値と 3 の大きい方を採用します。したがって `0`、負数、数値に変換できない文字列は 3 になります。完全な整数形式かどうかの検証や上限値チェックはありません。数値の後ろに文字が続く値も `atoi` の変換規則で扱われます。
- 整数型で表現できない入力の結果は、この parser から保証できません。

## 実行時の動作

オプション単独では候補生成を有効にしません。`--lookup-chain` が 0（既定値）のときは chain の提案分岐に入らず、この下限値は使われません。chain が有効な場合、MTP ドラフトを含む末尾コンテキストを使って候補を問い合わせ、`propose_from_sources` が一致長 `m` と `M` を比較し、`m < M` の候補を破棄します。条件を通った候補のうち最長一致のソースを選び、同じ長さなら先に調べたソースを維持します。候補提案数は `--lookup-chain` の値と検証ウィンドウの残り幅でも制限されます。

通常の生成経路では、最初のウィンドウ、既に suffix lookup のウィンドウを使っている場合、またはドラフトがウィンドウを満たす場合には chain の候補問い合わせを行いません。serving 経路にも同様の条件分岐があります。候補が選ばれても、通常はドラフト policy が確率と一致長、実測コストに基づいてさらに短縮または除外できます。環境変数 `STRATA_LOOKUP_CHAIN_FIXED` が設定されている場合、少なくとも通常生成側の policy によるこの調整を迂回します。

lookup chain は検証ウィンドウに候補を足す投機的な処理です。検証で採用されたトークンだけが出力にコミットされるため、この下限値自体は出力内容を直接変更せず、採用候補数や生成処理に影響します。chain が有効な実行では、chain の候補・採用数が生成結果の統計に表示されます。

## 適用条件と副作用

- `strata generate` の native 実装と SYCL 実装の双方に parser と同じ既定値・下限補正があります。
- `--lookup-chain` が有効で、ドラフト候補に空きがあり、候補の一致長がこの下限を満たす場合にだけ値が実行時の選択に影響します。
- 大きな値は一致条件を厳しくし、候補が採用されない場合があります。ソース上、値の上限補正はありません。
- オプションによるファイル・ネットワーク等への直接の副作用は確認できません。候補選択は検証ウィンドウの幅と処理量に影響し、生成統計に chain の件数が出ることがあります。

## 出力とエラー

- 値を省略した場合は標準エラーに不足メッセージを出し、終了コード 2 で終了します。
- このオプションに不正値専用のエラー経路はなく、`atoi` の変換結果を 3 以上に補正します。
- chain 有効時、通常の `strata generate` は標準出力に `lookup chain` の窓数と候補採用数を表示します。serving は標準エラーに窓数・候補数・採用数を表示します。

## 根拠

- `engine/src/program/generate.cpp:1163-1167` — `--lookup-chain` と下限値の既定値・意味。
- `engine/src/program/generate.cpp:1353-1355` — `strata generate --help` の option 説明。
- `engine/src/program/generate.cpp:3842-3847` — 値がない場合の標準エラーと終了コード 2。
- `engine/src/program/generate.cpp:4125-4126` — parser、`atoi` 変換、3 への下限補正。
- `engine/src/program/generate.cpp:1036-1042` — lookup chain に渡す末尾コンテキストへ未検証ドラフトを加える処理。
- `engine/src/spec/draft_source.cpp:13-33` — 一致長の下限判定、長い一致の優先、同長時の先行ソース優先。
- `engine/src/program/generate.cpp:11722,22769-22786` — `STRATA_LOOKUP_CHAIN_FIXED` 判定、通常生成側の適用条件、候補数制限、policy による追加調整。
- `engine/src/program/generate.cpp:25065-25077` — serving 側の適用条件と候補数制限。
- `engine/src/program/generate.cpp:25167-25204` — 検証結果の一致数に応じた commit と採用統計の計上。
- `engine/src/program/generate.cpp:14254-14256` — 通常生成時の chain 統計表示。
- `engine/src/program/generate.cpp:13264-13266` — serving 時の chain 統計表示。
- `engine/sycl/src/program/generate.cpp:777,922,2100,12713-12724,14075-14086` — SYCL 実装にある同等の既定値、help、parser、候補適用経路。
