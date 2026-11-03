# `FNX_PF_GDN_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

strata-split の GDN prompt chunked 経路で、行ごとに再帰計算する既存 kernel と sub-chunk kernel を同じ入力で実行し、出力と終了時の状態の差を stderr に記録する診断フックです。差が大きくても値を判定して処理を中止する比較閾値はありません。

対象の `gdn_prompt()` は split engine の prompt 処理から呼ばれ、非 attention 層の GDN 出力を計算します（`src/split/src/prefill.cu:1199-1205`）。split engine は opt-in のビルドで、Linux CUDA または Linux HIP が対象です（`src/split/CMakeLists.txt:1-7,20-26`）。この関数は `kernels.cu` の `FNX_KPART == 4` 部分にあります（`src/split/src/kernels.cu:1897-1904,1979-1981,2040-2041`）。

## 値と判定

コードは値を parse せず、`std::getenv()` の結果が null かどうかだけを見ます。明示設定された値は空文字を含めすべて有効で、値が `0` でも無効にはなりません。

| 状態 | 診断比較 |
|---|---|
| unset | 無効 |
| 設定あり（空文字を含む任意の文字列） | 有効 |

ただし、この環境変数の読み取り自体が chunked 経路の中にあります。`FNX_PF_GDN_CHUNK` が unset または `1` で chunked が有効な場合にだけ判定されます。`FNX_PF_GDN_CHUNK=0` なら row-by-row 経路へ進み、この診断変数は読まれません。`FNX_PF_GDN_CHUNK` は未設定時に chunked を有効化し、設定値は文字列全体が厳密に `0` または `1` の場合だけ受け付けます。それ以外は `FNX_PF_GDN_CHUNK: 0 or 1, not '<値>'` の例外になります（`src/split/src/kernels.cu:1986-1991,2033-2036`）。

## 有効になる条件

- split engine を組み込んだ Linux CUDA または Linux HIP ビルドであること。split engine 自体が opt-in です（`src/split/CMakeLists.txt:1-7,20-26`）。
- prompt の非 attention 層で `gdn_prompt()` が呼ばれること（`src/split/src/prefill.cu:1199-1205`）。
- `FNX_PF_GDN_CHUNK` が未設定または `1` で、sub-chunk 経路が選ばれること（`src/split/src/kernels.cu:1986-1991`）。
- その経路で初めて `FNX_PF_GDN_CHECK` の判定箇所に到達した時点で、変数が設定されていること（`src/split/src/kernels.cu:2002`）。

CLI 引数による上書きや、他変数による診断比較の閾値変更はこの実装にはありません。`FNX_PF_GDN_CHECK` を設定しても chunked 経路自体は選択しません。

## 実行時の詳細

値はプロセス起動時ではなく、chunked 経路で初めて `gdn_prompt()` がこの判定を通るときに読み込まれ、関数内の `static const bool` に cache されます。その後に環境を変更しても再評価されません。`FNX_PF_GDN_CHUNK` も関数内 static ですが別の判定です（`src/split/src/kernels.cu:1986-1991,2000-2005`）。

診断が有効なら、現在の状態 `S` を device buffer に複製し、行ごとの `k_gdn_pf_rec` を走らせます。その出力と更新後の状態を host vector にコピーし、`S` を保存時点の値に戻してから sub-chunk の準備 kernel と再帰 kernel を実行します。最後に sub-chunk 側の出力と状態も host にコピーして、各々について「最大絶対差 ÷ 参照側の最大絶対値（下限 `1e-30`）」を計算します。比較対象は正規化前の再帰出力と終了状態です（`src/split/src/kernels.cu:2005-2028`）。

診断行は stderr に次の形式で出ます。`C` は prompt chunk の行数です。

```text
gdn check: C <行数>, outputs <相対差>, end state <相対差> (largest difference over largest value)
```

差の大小だけを理由に警告・終了する処理はなく、その後 `k_gdn_pf_norm_own` を起動して通常の後続処理へ進みます（`src/split/src/kernels.cu:2024-2037`）。診断が有効な場合は参照側・比較側の結果を host に移す stream 同期も行います（`src/split/src/kernels.cu:2007-2015,2019-2023`）。一時 device buffer の確保に失敗した場合は `ck_launch("gdn check: alloc")` を呼び、CUDA エラーが確認されれば例外になります。kernel 起動エラーは最終の `ck_launch("gdn_prompt")` で例外になります（`src/split/src/kernels.cu:49-52,2007,2037`）。

## 根拠

- 候補名の全参照: `src/split/src/kernels.cu:2000-2002`。2000-2001 行は用途を述べるコメント、2002 行だけが値を読む実装です。他のソース参照はありません。
- prompt 呼び出し経路: `src/split/src/prefill.cu:1199-1205`。
- 値の読み取り、分岐、比較、ログ: `src/split/src/kernels.cu:1986-2037`。
- CUDA / HIP split build 条件: `src/split/CMakeLists.txt:1-7,20-26`。
- `docs/DETAILS.md` にこの診断変数の記述は見つかりませんでした。同資料には `STRATA_GDN_CHUNKED` の prompt chunked 経路の説明があります（`docs/DETAILS.md:1075,1505`）；これは `FNX_PF_GDN_CHECK` の比較結果や診断出力に関する根拠ではありません。
