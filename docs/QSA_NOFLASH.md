# `QSA_NOFLASH`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`QSA_NOFLASH` は Metal の `qsa_prompt_parity` テストで flash attention カーネルとの比較を省略する診断用スイッチです。Strata の通常の推論実行経路でこの環境変数を読む箇所は確認できません。参照箇所は `metal/tests/qsa_prompt_parity.cpp` のみです。

## 値と判定

値の内容は parse されません。`std::getenv("QSA_NOFLASH") != nullptr` だけを確認するため、未設定なら false、空文字を含め何か設定されていれば true です。`0` や `false` も設定されているだけで有効になり、大文字小文字、数値形式、値域の判定はありません。判定結果は `main()` の開始時にローカル変数 `noflash` へ読み取られます。

## 有効になる条件

- 対象は Metal parity テスト `qsa_prompt_parity` の通常比較経路です。
- `--bench` が指定された経路では、比較ループ内で `QSA_NOFLASH` を確認する前にベンチマークを実行して `continue` するため、この変数は効果を持ちません。
- 通常比較では、`qsa_attn_mm` と `qsa_attn` の比較およびその結果表示を行った後に判定します。設定時はその `pos0` の flash dispatch と `qsa_flash` 対 `qsa_attn + merge` の誤差計算・結果表示を飛ばします。
- 既に実行された行列演算版と参照版の比較には影響せず、後続の `qsa_score_mm` と `qsa_score` の比較にも影響しません。

## 実行時の詳細

`main()` の冒頭で環境変数の有無を一度読み、`noflash` に保存します。通常経路は `pos0` ごとに行列演算版の比較を行い、`noflash` が true ならその地点で次の `pos0` へ進みます。したがって省略されるのは flash attention の検証だけで、他の parity 検証は残ります。環境変数の実行中の変更を再読込するコードはありません。

## 根拠

- `metal/tests/qsa_prompt_parity.cpp:23-30`: テストの `--bench` 判定と、環境変数の有無を `noflash` に読み取る箇所。
- `metal/tests/qsa_prompt_parity.cpp:72-82`: ベンチマーク経路が比較ループ内の `QSA_NOFLASH` 判定より先に `continue` する箇所。
- `metal/tests/qsa_prompt_parity.cpp:83-118`: 通常経路の参照・行列演算比較、`noflash` による flash dispatch と誤差比較の省略。
- 調査対象 HEAD で `QSA_NOFLASH` を完全一致検索した結果は `metal/tests/qsa_prompt_parity.cpp:26` の1箇所だけでした。このため、ここで説明した動作はテスト専用であり、製品実行時の設定としては確認できません。
