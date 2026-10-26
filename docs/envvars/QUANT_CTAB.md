# `QUANT_CTAB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 調査結果

`QUANT_CTAB` は、Strata の通常実行経路で読む環境変数ではありません。製品コードでは Metal shader の function constant の名前として使われています。環境から値を読む `getenv("QUANT_CTAB")` は Metal の parity テストにだけあり、調査手順で除外されているテスト専用コードです。そのため、利用者向けの環境変数としての既定値、値の解釈、実行時効果はありません。

## 候補名が現れる箇所

- `metal/tests/expert_parity.cpp:417` は `std::getenv("QUANT_CTAB") != nullptr` を function constant 23 に渡します。このテスト内では、未設定なら `false`、空文字を含む何らかの値が設定されていれば `true` です。値の内容は parse しません。
- `metal/tests/moe_mm_parity.cpp:104` も同じ設定有無判定を function constant 23 に渡します。
- 製品 shader の `metal/kernels/quant.metal:72-83` では `QUANT_CTAB` を function constant として宣言し、IQ テーブル参照でその bool を使います。これはプロセス環境からの読み取りではありません。

## 製品コードでの環境変数

Metal decode window の製品コードでは `metal/src/engine/window.cpp:70-75` の `metal_ctab()` が `STRATA_METAL_CTAB` を読み取ります。`QUANT_CTAB` はその値を Metal function constant index 23 に渡す際の shader 側の名前です。環境変数 `STRATA_METAL_CTAB` の値判定と適用条件は [STRATA_METAL_CTAB.md](STRATA_METAL_CTAB.md) に記録しています。

## 根拠

- parity テストでの環境読み取り: `metal/tests/expert_parity.cpp:417`, `metal/tests/moe_mm_parity.cpp:104`
- shader の function constant 宣言と参照: `metal/kernels/quant.metal:72-83`
- 製品コードが読む実際の環境変数: `metal/src/engine/window.cpp:68-75,972-977`
