# `PC_QSA_SCORE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`000_envvers.md` に候補として載っていますが、この HEAD の通常実行コードに `PC_QSA_SCORE` の読み取りは見つかりませんでした。名前の参照は `metal/tests/prompt_chain.cpp` のテスト用コードだけです。調査手順ではテスト専用コードを環境変数の実装根拠から除外するため、通常の Strata 実行ファイルがこの変数で動作を変えるとは確認できません。

## 値と判定

通常実行コードに読み取り箇所がないため、未設定・空文字・値の書式・既定値を通常実行時の仕様として定める根拠はありません。

参考として、テスト用 `metal/tests/prompt_chain.cpp` では `std::getenv("PC_QSA_SCORE")` の null 判定を使っています。テスト内では未設定なら GEMM の `qsa_score_mm` pipeline を使い、設定されていれば `qsa_score` pipeline を使います。この判定は値を parse せず、空文字を含む設定済みの値を同じ扱いにします。この記述は当該テストの分岐だけを説明するもので、製品実行時の仕様ではありません。

## 有効になる条件

通常の Strata 実行経路で有効になる条件は確認できません。見つかったテスト内の分岐は Metal の prompt-chain テストに属し、QSA の選択処理で `pos0 + T > QB` の場合にスコア計算 pipeline を選ぶ箇所にあります。テスト専用コードを除外する調査範囲のため、これを Metal backend の通常実行機能や利用者向け設定として一般化できません。

## 実行時の詳細

通常ソース、Strata の文書に `PC_QSA_SCORE` の読み取りや設定方法は見つかりませんでした。起動時・リクエストごとの評価、static cache、子プロセスへの継承についても、Strata の通常実行コード上の根拠はありません。

## 根拠

- `metal/tests/prompt_chain.cpp:357-366` — テスト用コードの参照箇所。環境変数の有無で `qsa_score_mm` と `qsa_score` の pipeline 呼び出しを切り替えます。テスト専用コードのため、通常実行時の実装根拠には採用していません。
- Strata `main` HEAD 全体を `PC_QSA_SCORE` で検索し、上記テスト用コード以外の参照を確認できませんでした。`docs/DETAILS.md` を含む Strata 文書にも説明は見つかりませんでした。

