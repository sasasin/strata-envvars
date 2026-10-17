# `GR_PRELOAD`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

この名前を環境から読むのは Metal の parity / benchmark 用プログラム `metal/tests/gr2_parity.cpp` だけです。通常の Strata 実行ファイルがこの変数を読み取る実装は確認できません。そのため、ここで説明するのはテストプログラムの挙動であり、Strata 本体の実行設定ではありません。

## 値と判定

コードは `std::getenv("GR_PRELOAD")` の null 判定だけを行い、値を parse しません。

| 状態 | `q8 == 0`（BF16）時の down pipeline 名 |
|---|---|
| 未設定 | `gr_down3_<F>_<tt>_<rps>` |
| 設定あり（空文字を含む任意の値） | `gr_down3b_<tt>_<rps>` |
| `q8 == 1`（Q8_0） | 変数の設定有無にかかわらず `gr_down3_<F>_<tt>_<rps>` |

ここで `F` は BF16 側では `30`、Q8_0 側では `8` です。判定に数値変換、文字列比較、大小文字の処理はありません。`GR_PRELOAD=0` や空文字も「設定あり」として扱われます。

## 有効になる条件

効果があるのは `metal/tests/gr2_parity.cpp` を実行した場合だけで、さらに同プログラムのループで BF16 側（`q8 == 0`）を処理するときに限られます。ベンチマーク引数 `--bench` の有無はこの pipeline 名の選択条件ではありません。Strata の通常のアプリケーション経路における効果はありません。

## 実行時の詳細

テストプログラムの `main()` は各 `q8`, `tt`, `rps` の組み合わせについて down pipeline 名を組み立て、`cx.pipeline()` に渡して取得します。`GR_PRELOAD` が設定されている BF16 経路では、pipeline 名が `gr_down3b_<tt>_<rps>` に切り替わり、通常名に含まれる `F` が入りません。Q8_0 のときはこの分岐を通らず、環境変数は結果に影響しません。

このファイルには `GR_PRELOAD` に応じて専用ログを出す処理はありません。後続の parity / benchmark 出力はテスト全体の結果であり、環境変数専用の診断出力ではありません。選択された pipeline 名が実際に取得できるかどうかは `cx.pipeline()` および Metal runtime 側の処理に依存するため、その外部・別実装の挙動はここでは説明しません。

## 根拠

- `metal/tests/gr2_parity.cpp:1-6,30-35`: ファイルの目的と、テストプログラムの `main()`、`--bench` 判定。
- `metal/tests/gr2_parity.cpp:71-83`: BF16 / Q8_0 の分岐と `GR_PRELOAD` の null 判定、pipeline 名の組み立て、`cx.pipeline()` への受け渡し。

リポジトリ全体の `GR_PRELOAD` 検索では、この2参照以外は見つかりません。いずれも `metal/tests/` 内のテスト専用コードであるため、この変数に Strata 本体の環境変数としての挙動は確認できません。
