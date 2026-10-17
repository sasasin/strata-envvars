# `QSA_TOPK`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`QSA_TOPK` は Metal の QSA テストプログラムで top-k カーネルを選ぶための環境変数です。設定されていれば `qsa_topk`、未設定なら `qsa_topk2` を選びます。調査対象 HEAD で完全一致検索したところ、環境変数を読む実装は `metal/tests/qsa_parity.cpp` と `metal/tests/token_chain.cpp` の2箇所だけでした。Strata の通常の Metal engine が読む箇所は確認できず、通常利用時のカーネル切り替えスイッチではありません。

## 値と判定

どちらのテストプログラムも `std::getenv("QSA_TOPK")` の null 判定だけを行います。値の変換や文字列比較はありません。

| 状態 | 選択される pipeline |
|---|---|
| 未設定 | `qsa_topk2` |
| 設定あり（空文字を含む） | `qsa_topk` |

したがって `QSA_TOPK=0` や `QSA_TOPK=false` も設定ありとして扱われます。値の内容、大文字小文字、数値としての妥当性は見ません。

## 有効になる条件

この分岐は `metal/tests/qsa_parity.cpp` と `metal/tests/token_chain.cpp` の中にあり、各テストプログラムを実行するときだけ評価されます。`qsa_parity` のファイル冒頭は QSA の GPU 処理を CPU reference と比較・計測するプログラムと説明し、`token_chain` は実 GGUF の重みを使って Metal kernel の decode step を計測するプログラムと説明しています。これらのテスト用途の選択を通常の生成処理に適用する根拠はありません。

通常の Metal engine の `window.cpp` は `QSA_TOPK` を読まず、pipeline helper に `qsa_topk2` を指定し、見つからない場合の fallback として `qsa_topk` を渡します。従って通常経路では v2 を優先し、v2 が使えない場合に v1 へ fallback する実装です。この fallback は環境変数による選択ではありません。

## 実行時の詳細

両テストでは pipeline を組み立てる際に環境変数を一度確認します。選ばれた pipeline は以降のテスト dispatch に使われます。実行中に環境変数を変更して再評価する処理はありません。

`qsa_topk` と `qsa_topk2` はどちらも QSA 用の選択 kernel です。`qsa.metal` の説明では、各 token について最大2051 cellを選び、範囲内なら全 cell、超える場合は score 上位 cell を選択します。`qsa2.metal` の説明は `qsa_topk2` を同じ選択処理の別実装としており、radix pass の桁選択を parallel suffix scan で行います。この説明は kernel の役割を示すもので、`QSA_TOPK` による出力同一性や性能差をこの調査で独立測定したものではありません。

専用ログや警告はありません。値が無効として拒否される経路もありません。

## 根拠

- `metal/tests/qsa_parity.cpp:1-6,41-47` — テストプログラムの目的と、設定有無による `qsa_topk` / `qsa_topk2` の選択。
- `metal/tests/token_chain.cpp:1-8,243-249` — decode 計測プログラムの目的と、同じ選択条件。
- `metal/src/engine/window.cpp:745-757` — 通常 engine の選択条件と pipeline 指定。環境変数ではなく `qsa_topk2` 優先、`qsa_topk` fallback。
- `metal/kernels/qsa.metal:11-15,180-200` — `qsa_topk` の役割と選択範囲。
- `metal/kernels/qsa2.metal:1-7,121-145` — `qsa_topk2` が同じ選択の別実装であること。
