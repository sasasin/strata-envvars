# `DS4_MK_SPLIT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSpark の Markov head による draft token 計算を、head を分割して配置した複数 GPU に分散する経路を選びます。対象は `src/dsv41/ds4_model.cu` の DS4 モデル実装です。未設定時は条件が整えば分割経路を使い、`DS4_MK_SPLIT=0` 相当の値を設定すると lead GPU が全行を集める従来経路を使います。

## 値と判定

ロード処理で環境変数を直接読み、`std::atoi` の結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| 値 | 結果 |
|---|---|
| 未設定 | 0 判定にならず、他の条件を満たせば分割経路を有効化 |
| 空文字、数字に変換できない文字列（例: `false`） | `atoi` が 0 を返し、分割経路を無効化 |
| 先頭の空白や符号の後に 0 として読める値（例: `0`, `-0`, `0junk`） | 分割経路を無効化 |
| 先頭の空白や符号の後に非 0 の整数として読める値（例: `1`, `-1`, `1junk`） | 分割経路を許可 |

`atoi` は先頭の空白と符号を認識し、整数部分を読んだ後の文字を無視します。数値として読めない場合の 0 も無効化側です。したがって `DS4_MK_SPLIT=false` は「false として解釈」されるのではなく、変換結果 0 によって分割を止めます。根拠: `src/dsv41/ds4_model.cu:2426-2428`。

## 有効になる条件

環境変数が未設定または `atoi` で非 0 になっても、以下をすべて満たす必要があります。

- モデルに MTP/DSpark ブロックがある（`g.n_mtp > 0`）。
- head の GPU グループに複数 member がある（`head_nm() > 1`）。
- そのグループの全 member で Markov head の行共有バッファ `mk_share` が用意されている。

各 GPU の `mk_share` は Markov head tensor が F16 または BF16 で、期待サイズ `[vocab][rank]` に一致する場合にロードされます。別の型・サイズなどで共有行が揃わなければ `mk_rows` が false になり、この環境変数による分岐は有効になりません。その場合、lead GPU の全行を使う経路が残ります。根拠: `src/dsv41/ds4_model.cu:3750-3775,2426-2428`。

## 実行時の詳細

判定はモデルの `load()` 中、dense weights のロード後に行われます。分割経路を有効にすると、実装は Markov embed tensor が BF16 であることと `[vocab][rank]` のサイズを確認し、host-mapped embed と Markov step 用 slot を確保して embed を読み込みます。読み込み・確保に失敗すると model load は失敗し、embed の形式が違う場合は `the markov embed: not a BF16 [vocab][rank] table`、読み込み失敗時は `the markov embed: read failed` をエラーに設定します。環境変数自体に関するログはありません。根拠: `src/dsv41/ds4_model.cu:1860-1864,2421-2441`。

推論時は `mk_split` が有効で、かつ draft が sampled drafts でない場合に分割経路を使います。head の logits を全 GPU から gather せず、各 GPU が自分の Markov head 行で bias を計算し、その share の argmax を host-mapped slots に置き、全体の選択 token を求めます。`drafts_q` は `temperature > 0` かつ `sample_drafts` の場合に true になり、この sampled draft では分割経路を使わず、head の全 logits を lead GPU に gather して `markov_add` と sampler を実行します。`DS4_MK_SPLIT=0` 相当の値も同じく `mk_split` を立てず、lead GPU に全行を集める従来経路になります。根拠: `src/dsv41/ds4_model.cu:6715-6726,6787-6848,8490-8521`。

`DS4_MK_SPLIT=0` で止めるのは Markov step の分割実行です。GPU ごとの `mk_share` のロード判定・確保はこれより前の per-device dense load にあるため、0 を設定してもその処理自体は抑止しません。根拠: `src/dsv41/ds4_model.cu:3750-3775,2426-2440`。

## 根拠

- 環境変数の判定、Markov embed/slots の準備: `src/dsv41/ds4_model.cu:2421-2441`
- モデル load の入口: `src/dsv41/ds4_model.cu:1859-1864`
- GPU ごとの Markov head share の条件とロード: `src/dsv41/ds4_model.cu:3750-3775`
- sampled draft を除く推論分岐と分散 Markov step: `src/dsv41/ds4_model.cu:6787-6848`
- logits share の gather 条件: `src/dsv41/ds4_model.cu:8490-8521`

`docs/DETAILS.md` も確認しましたが、`DS4_MK_SPLIT` またはこの Markov 分割経路の説明・測定値は見つかりませんでした。このため性能や出力同一性については記載していません。
