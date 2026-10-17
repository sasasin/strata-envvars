# `CHAIN_CTAB`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`CHAIN_CTAB` は通常の Strata 生成・サーバー実行を制御する環境変数ではありません。参照は Metal の `metal/tests/token_chain.cpp` にある単発デコード計測ハーネスだけです。このハーネスでは、routed MoE gate/up kernel に quantization table を使う方法を選び、選択を Metal function constant 23（`QUANT_CTAB`）として pipeline に渡します。

`metal/kernels/quant.metal` では function constant が真なら i-quant grid と sign table を定数配列から参照し、偽なら threadgroup table を参照します。コメント上は両者の値は同じで、真の場合は threadgroup への表コピーと開始時の barrier wait がありません。これは kernel 側の機構の説明であり、製品実行に `CHAIN_CTAB` が反映されることを意味しません。

## 値と判定

ハーネスは `std::getenv("CHAIN_CTAB")` の存在と、取得値が文字列 `"0"` と完全一致するかを判定します。`ctabf` は `CHAIN_CTAB` が未設定であるか、設定値が `"0"` 以外なら真です。

| 環境変数の状態 | `ctabf` | function constant 23 |
|---|---:|---:|
| 未設定 | 真 | 真（定数配列を参照） |
| 空文字 | 真 | 真（定数配列を参照） |
| `0` | 偽 | 偽（threadgroup table を参照） |
| `00`、`false`、`1` など `0` と異なる文字列 | 真 | 真（定数配列を参照） |

数値変換や先頭文字判定ではなく、文字列全体の完全一致です。したがって `00` や `0 ` は無効化値ではありません。大文字小文字による特別扱いもありません。

## 有効になる条件

この環境変数の読み取りは `token_chain` 実行ファイル内だけです。ソース全体の完全一致検索では、製品の `metal/src/engine/window.cpp` やその他の通常実行コードで `CHAIN_CTAB` を読む箇所は確認できませんでした。通常実行側の `window.cpp` にも function constant 23 を設定する処理があります。そちらは別変数 `STRATA_METAL_CTAB` を関数内の `static` 値として読み、未設定または文字列 `"0"` 以外なら有効にします。従って、通常実行の同じ機構を切り替える変数は `CHAIN_CTAB` ではなく `STRATA_METAL_CTAB` です。

そのため `CHAIN_CTAB` を設定しても、通常の Strata CLI やサーバーの gate/up kernel 選択が変わるとはコードから確認できません。影響するのは `metal/tests/token_chain.cpp` のハーネスで該当 dispatch が実行される場合です。

## 実行時の詳細

ハーネスの `main()` は `ctabf` を一度計算します。その後、routed gate/up 用の pipeline を作る際に、真偽に応じた `#ct` の cache key と `mtl::Constants().b(23, ctabf)` を渡します。環境変数をプロセス起動後に変更した場合に再評価する処理はありません。

`CHAIN_CTAB` 専用のログ出力は確認できませんでした。ハーネス冒頭の説明では、実 GGUF 重み上の Metal dispatch 時間を測る一方、活性値は合成データで数値検証用ではないとされています。このため、この変数の説明から正確性や性能差を一般化することはできません。

## 根拠

- `metal/tests/token_chain.cpp:1-6` — 対象は Metal kernel 群を実重み上で dispatch する単発デコード計測ハーネスで、数値検証ではない。
- `metal/tests/token_chain.cpp:186-188` — `CHAIN_CTAB` の完全一致判定と既定値。
- `metal/tests/token_chain.cpp:579-585` — routed gate/up pipeline の cache key と function constant 23 への値の指定。
- `metal/kernels/quant.metal:65-76` — `QUANT_CTAB` が真の場合の定数配列参照、偽の場合の threadgroup table 参照。
- `metal/src/engine/window.cpp:65-73,864-875` — 通常実行経路では `STRATA_METAL_CTAB` を static cache し、function constant 23 に渡す。
