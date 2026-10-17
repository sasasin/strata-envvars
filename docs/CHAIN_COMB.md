# `CHAIN_COMB`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`CHAIN_COMB` は Strata の通常の生成・サーバー実行ではなく、Metal の `metal/tests/token_chain.cpp` にある単発デコード計測ハーネスで、MoE combine を次の HC read の norm に融合するかを切り替えます。同ファイルの冒頭コメントによれば、このハーネスは実モデルの重みを使って Metal kernel の dispatch をまとめた計時用コードで、活性値は合成データであり数値検証用ではありません。リポジトリ全体で `CHAIN_COMB` の参照はこの1箇所だけです。

## 値と判定

| 値 | ハーネスでの判定 |
|---|---|
| 未設定 | 無効 |
| 設定済み（空文字を含む） | 有効 |

判定は `std::getenv("CHAIN_COMB") != nullptr` だけです。値の内容は parse・比較されないため、`0`、`false`、空文字を含め、設定されていれば有効です。値は `main()` 内で一度読み取られます。

## 有効になる条件

`CHAIN_COMB` の分岐が融合を予約するのは、HC read モードが `3` または `q8_3` の場合です。これら以外のモードではこの変数による予約は行われず、MoE combine の dispatch が通常どおり追加されます。

モードは `--hc` 引数で指定できます。指定がないと、`STRATA_HC_Q8` が設定され値が文字列 `0` と完全一致する場合は `3`、それ以外（未設定を含む）は `q8_3` です。したがって既定モードでは `CHAIN_COMB` が設定されていると融合経路になります。`--hc` が `--hc 3` / `--hc q8_3` 以外に指定されると、`CHAIN_COMB` だけでは融合しません。

このハーネスには別の `--fold-comb` オプションもあります。これは3-dispatch以外の HC read 経路で combine を次の HC read に融合するための別分岐です。

## 実行時の詳細

MoE combine の箇所で `CHAIN_COMB` と HC モードの条件が成立すると、combine kernel を dispatch リストへ追加せず、`comb_pending` を立てます。次の HC read では通常の `gr_norm` の代わりに `gr_norm_comb` を選び、MoE combine のバッファ・引数も渡して処理します。対応する Metal kernel のコメントは、`gr_norm_comb` が `moe_combine_sh` の演算を取り込んで combine dispatch を省くことを説明しています。

`CHAIN_COMB` 自体による専用ログ出力はありません。ハーネスは最終的に dispatch 群の計測結果を出力しますが、環境変数の設定有無を表示するコードは確認できませんでした。

## 根拠

- `metal/tests/token_chain.cpp:1-6` — 対象コードが実モデル重みを使う単発デコード計時用で、活性値は合成データであること。
- `metal/tests/token_chain.cpp:65-83` — `--hc` / `--fold-comb` の引数処理。
- `metal/tests/token_chain.cpp:180-188` — `CHAIN_COMB` の設定有無判定、および `CHAIN_ROUTE` など隣接設定。
- `metal/tests/token_chain.cpp:283-296,321-340` — HC read モード分岐、`gr_norm_comb` への切り替え。
- `metal/tests/token_chain.cpp:606-614` — MoE combine 後に融合を予約する条件。
- `metal/kernels/gr2.metal:305-308` — combine 演算と dispatch 省略についての kernel コメント。
