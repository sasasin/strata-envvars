# `GR_DOWN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

## 役割

この名前を環境から読む箇所は Metal の `gr_parity` テストハーネスに限られます。Strata の通常の実行エンジンが `GR_DOWN` を読み取る実装は見つかりませんでした。そのため、利用者向け設定としての役割や実行時効果は確認できません。

## 値と判定

本番コードに読み取り箇所がないため、Strata の実行時設定としての既定値・値の形式・無効値時の処理はありません。

参考として、対象範囲外の `metal/tests/gr_parity.cpp` では、テスト実行時に未設定なら文字列 `8_8`、設定済みなら環境変数の文字列を使い、`sscanf("%d_%d", ...)` で2つの整数を読み取ります。この読み取りはテスト専用であり、通常の Strata 実行時の値規則を示すものではありません。

## 有効になる条件

通常の Strata エンジンで有効になる条件はありません。`GR_DOWN` は候補一覧に含まれますが、今回のソース全体検索では直接の環境変数参照は Metal parity テストだけでした。`STRATA_GR_DOWN_TG`、`STRATA_GR_DOWN_MAX4` など別名の環境変数は実装されていますが、名前も読み取り箇所も異なるため、`GR_DOWN` の挙動の根拠にはなりません。

## 実行時の詳細

`metal/tests/gr_parity.cpp` はハイパーコネクションの GPU 結果を CPU 参照実装と比較するテストです。同ファイルでは `GR_DOWN` の値を down projection の Metal pipeline 名に使います（`metal/tests/gr_parity.cpp:1-5,68-85`）。このテストコードは本番動作の調査対象から除外されるため、pipeline 名の受け付け範囲やテスト結果を Strata の利用者向け設定仕様としては記載しません。

## 根拠

- `metal/tests/gr_parity.cpp:1-5` はファイルを parity テストとして説明しています。
- `metal/tests/gr_parity.cpp:68-85` に `GR_DOWN` の読み取りとテスト用 pipeline 選択があります。
- 候補一覧の `GR_DOWN` は `docs/envvars/000_envvers.md` にあります。
- `docs/DETAILS.md:934,1060,1064` に現れるのは別名の `STRATA_GR_DOWN_TG` であり、`GR_DOWN` の環境変数実装ではありません。

調査上の制限: テスト専用箇所以外に `GR_DOWN` の参照を確認できなかったため、Strata 本番プログラムの環境変数として説明できる動作はありません。
