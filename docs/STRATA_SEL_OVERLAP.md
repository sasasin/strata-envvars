# `STRATA_SEL_OVERLAP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

prefill の QSA（query selective attention）で、隣接する query が選んだ cell の重複を診断し、stderr に出します。選択結果や attention の計算を変更する設定ではありません。CUDA 実装と SYCL 実装の両方に同じ診断があります。

計測単位は16 queryのタイルです。各タイルについて query ごとの選択幅の合計を基準に、タイル内で重複を除いた選択 cell 数を加算し、`100 * タイル内ユニーク cell 数の合計 / 選択幅の合計` を表示します。したがって、値が小さいほどタイル内の query 間で選択が共有されています。タイルをまたいだ重複はまとめて除きません。

## 値と判定

| 値 | 診断 |
|---|---|
| 未設定 | 無効 |
| 設定あり（空文字を含む） | 有効 |

数値変換や文字列比較はなく、`std::getenv(...) != nullptr` の有無だけで判定します。`0`、`false`、任意の文字列も、環境変数が存在すれば有効です。判定は関数内の `static const bool` に保存されるため、最初の判定後にプロセス内で環境変数を変更しても反映されません。

## 有効になる条件

値が設定されていても、prefill 中に QSA 層の選択処理へ到達する必要があります。実際の集計は `qsa_index == 0`、つまりその prefill chunk の最初の QSA 層だけで行います。後続の QSA 層では繰り返しません。

各 chunk の `T` query のうち、完全な16 queryタイルだけを対象にします。端数の query は除外します。完全なタイルがない場合も診断行は出ますが、分母が0のため表示値は `0.0%` です。

## 実行時の詳細

通常の QSA 選択 (`qsa_block_topk`) が終わった後、選択 ID 配列全体を device から host へコピーし、CUDA では stream を同期、SYCL では queue を wait します。その後、各16 queryタイルの選択幅分だけ ID を集めて sort/unique し、次の形式で stderr に出力します。

```text
strata prefill: selection overlap at <p0>: 16-query tiles read <percent>% of the cells one query at a time does
```

診断を有効にすると、このコピー・同期・CPU 集計が prefill に追加されます。そのため prefill 時間の観測に影響しますが、コード上では集計結果を選択配列や attention へ戻していません。

## 根拠

- `src/prefill/prefill.cpp:2774-2795`: top-k 選択後の環境変数判定、device-to-host コピーと同期、16 query単位の unique 集計、stderr 出力。
- `sycl/src/prefill/prefill.cpp:3031-3059`: SYCL 側の対応処理。queue の `memcpy` 後に `wait()` します。
- `src/prefill/prefill.cpp:1233-1257`: 選択幅 `m.cap` と選択 ID バッファの確保。
- `docs/DETAILS.md` を含むリポジトリ内 Markdown を検索しましたが、この環境変数の用途や測定値を説明する記述は確認できませんでした。上記は調査対象 HEAD の実装から確認できる内容です。
