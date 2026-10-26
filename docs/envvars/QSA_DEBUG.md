# `QSA_DEBUG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

この名前を読む箇所は `metal/tests/qsa_prompt_parity.cpp` のみで、Metal の QSA prompt parity テストが行列ユニット用カーネルの書き込み状況を標準出力へ追加表示するための診断フックです。テスト専用コードにあるため、通常の Strata 実行ファイルの QSA 動作を制御する環境変数としては確認できません。

## 値と判定

コードは `std::getenv("QSA_DEBUG")` の戻り値が null でないかだけを判定します。値の文字列や数値は parse しません。

| 状態 | 動作 |
|---|---|
| 未設定 | 追加の `debug ...` 行を出さない |
| 空文字を含む設定済みの値 | 追加診断を出す |
| その他の設定済みの値（`0`、`false` などを含む） | 追加診断を出す |

判定は `qsa_prompt_parity` の各 position の反復で行われ、static cache されません。テスト実行中に環境が変更された場合は次の反復で再判定されますが、通常はプロセス起動前に設定する使い方です。

## 有効になる条件

`metal/tests/qsa_prompt_parity.cpp` をビルドして実行し、通常比較経路で `cx.run(mm_ds)` を実行した後に限り、このフックのコードに到達します。`--bench` 経路は先に測定して `continue` するため、この診断箇所を通りません。`QSA_NOFLASH` が設定されていても、診断表示自体はそれより前に実行されます。

製品側ソースに `QSA_DEBUG` の読み取りは見つかりませんでした。従って、サーバーや通常の Strata 実行ファイルに設定しても Strata 所有コード上の動作変化は確認できません。

## 実行時の詳細

比較用の `mm_ds` を実行した後、テストは `part` バッファ内の `T * NCH * QH * (QD + 2)` 個の float を走査します。NaN 以外の要素数を「written」、NaN 以外で有限でない要素数を `inf` として数え、position、件数、割合の分母、および token 5 / head 0 の最初の chunk にある `m`, `l`, `acc[0..3]` を次の形式で stdout に出します。

```text
debug pos0 %u: %zu of %zu partial floats written (%zu inf); t5 h0: m %g l %g acc %g %g %g %g
```

この出力はテストの中間バッファ診断です。カーネルの選択、計算結果、比較許容値を変える処理ではありません。

## 根拠

- `metal/tests/qsa_prompt_parity.cpp:1-4` — ファイルの説明と `qsa_prompt_parity [--bench]` のテスト実行形式。
- `metal/tests/qsa_prompt_parity.cpp:72-86` — bench 経路が `continue` すること、およびカーネル実行後の設定有無判定。
- `metal/tests/qsa_prompt_parity.cpp:87-96` — 診断値の計数と標準出力の書式。
- `metal/tests/qsa_prompt_parity.cpp:98-108` — 後続の相対誤差比較と pass/fail 判定。診断ブロックの値は比較判定に使われない。
- `docs/DETAILS.md` と `docs/QSAROWS.md` を `QSA_DEBUG` で照合しましたが、この名前の説明はありません。これらの資料にある `STRATA_QSA_ROWS` 等の製品機能とは別です。
