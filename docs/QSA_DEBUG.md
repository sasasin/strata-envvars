# `QSA_DEBUG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`QSA_DEBUG` は Metal の `qsa_prompt_parity` テスト実行時に、行列演算版 QSA カーネルが出力バッファへ書いた値の数と、一部の中間値を stdout に表示する診断スイッチです。Strata の実行エンジンではなく、parity テスト専用です。

## 値と判定

値の内容は parse されません。`std::getenv("QSA_DEBUG")` が null でないかだけを確認するため、環境変数が未設定なら診断表示を行わず、空文字を含め何らかの値が設定されていれば表示します。`0`、`false` なども設定されている限り有効です。数値範囲や大文字小文字の扱いはありません。

## 有効になる条件

参照は `metal/tests/qsa_prompt_parity.cpp` の1箇所だけです。Metal parity テストの通常比較経路で、参照 dispatch と行列演算 dispatch を実行した後に診断ブロックへ入ります。`--bench` 経路はその前にベンチマーク処理へ進み、ループを `continue` するため、この診断ブロックは通りません。`QSA_NOFLASH` が設定されている場合も、この診断表示は行われます（同変数は後続の flash 比較を飛ばす別の分岐です）。

## 実行時の詳細

各 `pos0` の比較で `cx.run(mm_ds)` を終えた後、環境変数が設定されていると部分出力バッファ全体を調べます。NaN でない float の個数を「written」として数え、NaN 以外の非有限値を別に数えます。その後、token 5 / head 0 の最初の chunk から `m`、`l`、`acc[0..3]` を取り出し、次の形式で stdout に出します。

```text
debug pos0 %u: %zu of %zu partial floats written (%zu inf); t5 h0: m %g l %g acc %g %g %g %g
```

チェックは各比較ループで都度行われ、値を static cache しません。テストコード内で環境を変更する処理は確認できません。CLI 引数や設定ファイルとの優先順位もありません。

## 根拠

- `metal/tests/qsa_prompt_parity.cpp:23-30`: 対象テストの実行開始と `--bench` / `QSA_NOFLASH` の判定。
- `metal/tests/qsa_prompt_parity.cpp:72-86`: ベンチマーク経路の分岐と、通常経路で比較用 dispatch 後に `QSA_DEBUG` を確認する箇所。
- `metal/tests/qsa_prompt_parity.cpp:87-97`: バッファのカウント対象と stdout の診断内容。
- 調査対象 HEAD 内の `QSA_DEBUG` 完全一致検索ではこの1箇所だけが見つかりました。したがって、ここで確認できる挙動はテスト専用であり、Strata の製品実行時の設定としては確認できません。
