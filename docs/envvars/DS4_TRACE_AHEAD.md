# `DS4_TRACE_AHEAD`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`strata-dsv41` のルーティングトレースに、lookahead 予測候補を追加で記録します。通常のルーティング、expert 選択、モデル計算を変更する設定ではありません。トレースファイルが使える場合、layer ごとの route request レコードに予測候補を追記し、レコードの `T` ヘッダーの最上位 bit で拡張レコードであることを示します。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 予測候補を追記しない |
| 任意の値が設定済み | 追記する。値の文字列や数値は parse しない |
| 空文字が設定済み | 追記する（`getenv` は null ではない） |

判定結果は `serve_lane()` 内の関数ローカル `static const bool` に保存されます。最初に条件付き書き込み経路へ入った時に一度だけ読み取られ、その後プロセス内で環境変数を変更しても反映されません。ただし、この判定自体が評価されるのは `DS4_TRACE` のファイルが開けており、かつ MTP でない layer の route request を記録するときだけです。

## 有効になる条件

- `DS4_TRACE` が設定され、指定パスを `"wb"` で開けている必要があります。`DS4_TRACE` が未設定ならトレース記録はなく、この変数の判定にも到達しません。空のパスや開けないパスでは `fopen` が失敗し、同様に記録されません。
- 対象の route request が MTP layer ではない必要があります。
- 拡張は `serve_lane()` の route request レコードに適用されます。チャンク経路のトレースは別形式で書かれ、この変数による lookahead 拡張を追加しません。

この環境変数はトレース出力のみに作用します。記録された候補が実行時に使われるかどうかは制御しません。

## 実行時の詳細

通常の route request レコードは、1 byte の layer、1 byte の `T`、続いて各 token の `l.k_exp` 個の expert ID（int16）です。有効時には `T` の最上位 bit (`0x80`) を立て、通常の expert ID 群の後に次の拡張データを書きます。

1. `na1` と `na2`（各1 byte）。それぞれ `r.na[0]` を `kAhead1`、`r.na[1]` を `kPicks` の範囲に収めた数です。
2. 各 token について、次 layer とその次の layer の予測候補 ID を int16 で記録します。候補数はそれぞれ `na1` と `na2` です。

これらは現在の request に付随している lookahead 候補の記録です。値のファイル書き込みは `fwrite` で行われます。`tools/dsv41/win/cachesim.py` の reader は `T` の最上位 bit を検査し、同じ順で候補数と候補 ID を読み取ります。

チャンク経路の記録は `layer | 0x80`、16 bit の `T`、expert ID 群という別形式です。こちらは `DS4_TRACE_AHEAD` を参照せず、候補データも追加しません。

## 根拠

- `src/dsv41/ds4_model.cu:1157`: `DS4_TRACE` の有無で出力ファイルを `"wb"` で開く。
- `src/dsv41/ds4_model.cu:6481-6506`: MTP 以外の route request を記録する条件、設定有無だけの判定、ヘッダー bit と lookahead 候補の書き込み。
- `src/dsv41/ds4_model.cu:7356-7366`: チャンク経路は別のヘッダー・レコード形式で記録し、`DS4_TRACE_AHEAD` を使わない。
- `tools/dsv41/win/cachesim.py:28-60`: `T` の最上位 bit による拡張判定と候補データの読み取り。

`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。測定値や性能効果は記載していません。
