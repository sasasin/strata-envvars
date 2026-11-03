# `DS4_UNPICKED_STAT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 V4.1 の chunk 実行で、各 chunk の各通常モデル layer について、chunk 内のどの row からも選択されなかった expert の割合を集計し、プロセス終了時に stderr へ出す診断用環境変数です。expert の選択・計算・読み込みを変更する分岐には使われず、統計の記録だけを有効にします。

## 値と判定

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | 統計を記録しない（既定） |
| 空文字を含む、何らかの値が設定済み | 記録する |

実装は `std::getenv(...) != nullptr` の有無判定です。値の文字列比較、数値変換、範囲検査はありません。そのため `1` 以外の値や空文字も有効で、無効値としての fallback はありません。CLI 引数や他の環境変数との優先順位・上書き処理もありません。根拠: `src/dsv41/ds4_model.cu:11773-11774`。

## 有効になる条件

統計が記録されるのは、DS4 V4.1 の `forward_chunks()` が layer の chunk を処理し、`mi == 0` の profile 集計箇所に到達した場合です。通常の `Model::feed()` は `chunk > 0` かつ入力 token 数 `n >= chunk_min` のとき chunk 経路を選びますが、`logits_rows <= kWin` で `pick_path(n)` が偽なら window 経路になります。`feed_mark()` と `feed_marks()` にも chunk 経路の条件があります。根拠: `src/dsv41/ds4_model.cu:14862-14875,14877-14912`。

MTP drafter layer は `!l.mtp` 条件で除外されます。したがって、設定しても chunk 経路が選ばれない実行や、該当箇所に到達しない実行では集計値は増えません。根拠: `src/dsv41/ds4_model.cu:11773-11775,2854-2859`。

## 実行時の詳細

環境値は `mi == 0` の集計箇所に初めて到達したときに、関数内 `static const bool` として一度だけ評価されます。その後プロセス内で環境を変更しても再評価されません。各 layer で expert id ごとの row-bound 区間を調べ、区間が空でない expert 数 `n_picked` を数えます。設定が有効で通常 layer なら、`T` rows の chunk と `l.n_exp` experts に対して `n_exp - n_picked` を「未選択 expert 数」、`n_exp` を総 expert 数として、chunk-layer 件数とともに rows 数 `T` ごとに加算します。集計 map は mutex で保護されます。根拠: `src/dsv41/ds4_model.cu:11760-11775,809-817`。

グローバル集計オブジェクトの destructor は終了時、各 rows 数について次の形式を stderr に出します。割合は `100 * 未選択 expert 数の合計 / 総 expert 数の合計` です。該当する集計がなければその rows 数の行は出ません。

```text
ds4 unpicked: chunks of <rows> rows: <chunk-layers> chunk-layers, <percent>% of a layer's experts picked by none of them
```

根拠: `src/dsv41/ds4_model.cu:809-825`。

## 根拠

- `src/dsv41/ds4_model.cu:11760-11775` — expert の row-bound 集計、環境変数の存在判定と通常 layer のみの記録。
- `src/dsv41/ds4_model.cu:809-825` — rows 数単位の集計式、mutex、終了時の stderr 出力。
- `src/dsv41/ds4_model.cu:14862-14875,14877-14912` — feed / feed_mark / feed_marks から chunk 経路へ入る条件。
- `src/dsv41/ds4_model.cu:2854-2859` — MTP layer の識別。
