# `CHAIN_ALBE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の開発用 decode 計測プログラム `token_chain` で、GDN の `ssm_alpha` と `ssm_beta` の GEMV を一つの `gemv_cat` dispatch にまとめるかを選びます。参照は `metal/tests/token_chain.cpp` に限られ、Strata の通常の Metal 実行経路 (`metal/src/engine/window.cpp`) はこの変数を読みません。したがって通常の Strata アプリの動作を切り替える設定ではありません。

## 値と判定

値の内容は parse せず、`std::getenv("CHAIN_ALBE") != nullptr` で設定の有無だけを判定します。

| 状態 | `token_chain` での扱い |
|---|---|
| 未設定 | 無効。`ssm_alpha` と `ssm_beta` を別々に `gemv2` で dispatch する |
| 任意の値を設定 | 有効。空文字列や `0` を含め、値にかかわらず `gemv_cat` を使う |

## 有効になる条件

- `token_chain` の実行時に環境変数が設定されていること。
- 計測ループ内で `l % 4 != 3` の layer であること。この条件の外では該当する GDN 投影処理に入らないため、この分岐は使われません。
- `token_chain` が使う Metal kernel 群に `gemv_cat` の対応する型・pipeline があること。ホスト側は `ssm_alpha` の tensor type から `gemvc_<type>_32_1_4` を選びます。

## 実行時の詳細

環境変数は `token_chain` の初期化中、計測ループに入る前に一度読み取られ、`albe` に保存されます。未設定なら各 layer で `ssm_alpha` と `ssm_beta` に対して `gemv2` を個別に呼び、間に dispatch barrier を挟みます。設定時は `ssm_alpha` の重み・出力バッファ `al` と `ssm_beta` の重み・出力バッファ `be` を同じ dispatch に渡し、分割点 `48`、合計出力行数 `96` で `gemv_cat` を一度呼びます。

kernel は前半48行を第1の行列と出力 `al`、後半48行を第2の行列と出力 `be` に割り当てます。kernel のコメントは各行の計算が個別 GEMV と同じで出力が bitwise 一致すると説明しています。これは計測ハーネス内の dispatch 構成の説明であり、この調査では実行・再測定していません。

## 根拠

- `metal/tests/token_chain.cpp:1-6` — `token_chain` が実 GGUF の重みと Metal kernel を使って decode step を計測するプログラムであり、数値検証ではなく時間計測である旨。
- `metal/tests/token_chain.cpp:180-184` — `CHAIN_ALBE` を含む環境変数の読み取りと設定有無による判定。
- `metal/tests/token_chain.cpp:395-424` — layer 条件、二つの個別 GEMV と統合 dispatch の分岐、および統合時の 48/96 行設定。
- `metal/kernels/gemv.metal:162-169,183-205` — `gemv_cat` の二行列・二出力への行の振り分けと出力処理。
- `metal/src/engine/window.cpp:792-794` — 通常の Metal 実行経路では alpha/beta を別々に `gemv` しており、この環境変数の参照はない。

`docs/DETAILS.md` および調査対象リポジトリ内の他の文書に `CHAIN_ALBE` の説明は見つかりませんでした。
