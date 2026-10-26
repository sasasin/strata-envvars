# `DS4_ATTN_SPLIT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 の sparse attention で、FP4 形式の圧縮 KV 行を分割して処理する split-KV GPU カーネルを選択します。通常の attention を置き換える実験的な経路で、既定では無効です。対象機能は `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` が無効のときにビルドする独立実行ファイル `strata-dsv41` に含まれます。ビルドオプション自体は既定 OFF です。

## 値と判定

値は `std::atoi` で整数に変換され、結果が 0 以外なら要求を有効とします。文字列全体との比較ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数字で始まらない文字列 | `atoi` の結果が 0 なので無効 |
| `1`、`2`、`-1`、`1tail`、先頭空白の後に非ゼロ整数がある文字列 | `atoi` の結果が 0 以外なら有効 |
| `0`、`0tail`、数値変換できない文字列 | 無効 |

先頭にある空白と符号は `atoi` の変換規則に従い、整数部分より後ろの文字列は判定に使われません。変換結果が `int` の範囲を超える値は、この実装で定義された設定値として扱えません。別の環境変数や CLI 設定による優先順位・上書きはありません。判定値は関数内の `static const bool` に保存され、最初の呼び出し以降、プロセス内で環境変数を変更しても再評価されません。

根拠: `src/dsv41/ds4_kernels.cu:1835-1841`。

## 有効になる条件

値が有効でも、`sparse_attn()` が次の条件をすべて満たす場合にだけ split-KV 経路へ進みます。

- KV の形式が FP4 (`kKvFp4`)。BF16 形式ではこの分岐より前に通常カーネルを実行して戻ります。
- attention rows が生成モードではない（`a.gen == 0`）。
- query 数 `T` が 1〜5。
- attention head 数が 4 で割り切れる。
- 全 query の `nwin + nsel` の最大値が 1〜960。
- 対象 device と stream 用の split scratch を確保できる。

scratch の確保に失敗した場合や条件に合わない場合は、この環境変数の要求は適用されず、後続の通常 sparse attention 経路に進みます。無効化や fallback の専用ログはありません。実行ファイル自体がビルドされていない場合、この環境変数を読む処理もありません（ビルド条件には `STRATA_BUILD_DSV41` と `STRATA_HIP_GFX906` の制限があります）。

根拠: `src/dsv41/ds4_kernels.cu:1842-1862,2054-2080`、`src/dsv41/ds4_kernels.cuh:153-163`、`CMakeLists.txt:797-811`。

## 実行時の詳細

split scratch は初回に device と GPU stream の組ごとに確保し、静的 map に保持します。上限は query 5 個、head ごとに 24 split です。入力行数に応じて `ceil(total_max / 40)` 個の split を起動し、各 split の部分結果を merge kernel で出力にまとめます。確保に失敗した場合は scratch を空にして通常経路に戻ります。

この経路は同じ入力に対して演算の分割と加算順序を変えます。実装コメントも通常経路との最下位 bit の差を記しています。そのため、出力が bitwise 一致するとは限りません。ログ出力や環境変数の値を報告する処理は見つかりませんでした。

呼び出し元では decode / 短い verify window の sparse attention に `AttnRows` と query 数を渡します。prefill 用の生成 rows (`a.gen != 0`) はこの分岐の対象外です（`src/dsv41/ds4_model.cu:7226-7246,9016-9026`）。

## 根拠

- 読み取りと `atoi` 判定、初回値のキャッシュ: `src/dsv41/ds4_kernels.cu:1835-1841`
- scratch の device / stream ごとの割り当てと保持: `src/dsv41/ds4_kernels.cu:1842-1862`
- 分岐条件、split-KV 呼び出し、通常経路への fallback: `src/dsv41/ds4_kernels.cu:2054-2085`
- split 数の決定と部分結果の merge: `src/dsv41/ds4_attn_split.cuh:195-203`
- DSV41 実行ファイルのビルド条件: `CMakeLists.txt:797-811`
- 呼び出し側の attention rows と query 数: `src/dsv41/ds4_model.cu:7226-7246,9016-9026`

`docs/DETAILS.md` と関連資料を検索しましたが、この変数を説明する記述は見つかりませんでした。ソースコメントには測定への言及がありますが、ここでは測定条件を確認できる資料がないため、性能値や一般的な速度効果は記載していません。
