# `CHAIN_COMB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

この名前を読むコードは `metal/tests/token_chain.cpp` にだけあります。これは実 GGUF の重みで Metal の decode dispatch 列を組み立て、GPU 時間を測るテスト用プログラムです（ファイル先頭コメント、同ファイル `:1-7`）。Strata の通常の engine 実装やサーバーが `CHAIN_COMB` を読む箇所は、この HEAD では見つかりません。したがって通常の Strata 実行に対する設定としては確認できず、以下はテスト用プログラムでの効果です。

## 値と判定

| 状態 | テストプログラムでの判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値を設定 | 有効。値の内容は比較・数値変換されず、`getenv()` が null かどうかだけを見る |

判定結果は `main()` 内で一度 `const bool` に読み込まれます。プロセス起動後に環境を変更しても、その実行中の判定は変わりません。根拠: `metal/tests/token_chain.cpp:178-185`。

## 有効になる条件

`CHAIN_COMB` が設定されていても、テストプログラムの `hc_mode` が `"3"` または `"q8_3"` の場合に限り、MoE combine dispatch を次の `gr_norm` に畳み込む経路が選ばれます。初期値は `"q8_3"` で、`STRATA_HC_Q8` が文字列 `"0"` と完全一致する場合は `"3"` になります。その後 `--hc` があれば引数の文字列で上書きします（`metal/tests/token_chain.cpp:63-80`）。それ以外の `hc_mode` ではこの変数による畳み込みは起きず、combine dispatch は通常どおり追加されます（`--fold-comb` による別の経路は別設定です）。

## 実行時の詳細

MoE 層で combine dispatch を作るとき、`CHAIN_COMB` が設定済みで、かつ `hc_mode` が上記2値なら `comb_pending` を立てます。次の `gr_read()` はそのフラグを見て `gr_norm_comb` pipeline を選び、combine に必要な buffer 引数も dispatch に渡してからフラグを消します。その他の場合、`fold_comb` による別経路が選ばれていなければ combine dispatch を通常の dispatch 列に追加します。根拠: `metal/tests/token_chain.cpp:282-345,605-614`。

このファイル内に `CHAIN_COMB` の専用ログやエラー出力はありません。最後に出力される decode step の時間はテストプログラム全体の測定値であり、この環境変数単独の効果を示す計測値ではありません（`:644-660`）。

## 根拠

- `metal/tests/token_chain.cpp:1-7` — `token_chain` の用途を示すファイルコメント。
- `metal/tests/token_chain.cpp:178-185` — `CHAIN_COMB` の唯一の読み取りと存在判定。
- `metal/tests/token_chain.cpp:282-345,605-614` — combine dispatch の保留・次の norm への統合・通常 dispatch の分岐。
- HEAD 全体での `CHAIN_COMB` 完全一致検索では、このテストファイル以外に読み取りはありません。`token_chain` の実行箇所も同ソースと `metal/src/engine/window.cpp` のコメント以外に見つからず、通常の engine から呼び出される実装としては確認できません。
