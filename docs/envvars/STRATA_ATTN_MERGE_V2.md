# `STRATA_ATTN_MERGE_V2`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

QSA decode attention の chunk 結果をまとめる merge kernel を選びます。`0` は `attn_merge_kernel`、0 以外は `attn_merge_v2_kernel` です。対象コードは `src/kernels/cuda/qsa_decode_attn.cu` にあり、単一 query、batch、slot、batch rows の decode attention から呼ばれます。これは実際の処理を切り替える環境変数です。

## 値と判定

`attn_merge_v2()` の初回呼び出し時に値を読み、関数内の `static const int` に保存します。プロセスの起動時ではなく、最初に merge 選択が必要になった時点で評価されます。その後に環境を変更しても再評価されません。

| `STRATA_ATTN_MERGE_V2` | 判定 |
|---|---|
| 未設定または空文字 | `STRATA_ATTN_DAILY` に従う |
| 空でない文字列 | `std::atoi` の結果が 0 なら標準 merge、0 以外なら v2 merge |

空でない値は文字列全体の真偽判定ではなく、`atoi` で10進整数に変換した結果で判定します。先頭の空白と符号は整数変換の規則に従い、数字の後の文字列は変換を止めます。したがって `1anything` や `-1` は v2、`0anything` や `true` は標準 merge になります。数字を含まない値は `atoi` が 0 を返すため標準 merge です。整数の範囲検証や clamp はありません。

## 有効になる条件

この設定を読む実装は `src/kernels/cuda/qsa_decode_attn.cu` です。CUDA build では明示設定がなければ `STRATA_ATTN_DAILY` が既定値になります。`STRATA_ATTN_DAILY` は値がちょうど1文字の `1` の場合だけ有効です。`STRATA_ATTN_MERGE_V2` が空でない値なら、この既定を `atoi` の結果で上書きします。

HIP build では `daily_attn()` が常に `false` を返すため、`STRATA_ATTN_MERGE_V2` が未設定または空なら標準 merge が選ばれます。空でない明示値による上書きは同じ `attn_merge_v2()` 内で行われます。検索した SYCL 側の実装にはこの環境変数の読み取りはありません。

## 実行時の詳細

`attn_merge_v2_kernel` は step record の幅から実データがある chunk 数を求め、その範囲だけを merge します。また、複数 chunk の値をまとめてロードしてから chunk 順に累積します。標準 kernel は全 chunk を走査し、空 chunk を `m == -FLT_MAX` で飛ばします。ソースコメントは、v2 が標準 kernel と同じ演算順・同じ有効値を使い出力 bit を変えない設計だと説明しています。この文書では、その性質を独立に測定・検証したものとしては扱いません。

この設定自体についてログ出力はありません。`docs/DETAILS.md` には `STRATA_ATTN_DAILY=1` を有効にした CUDA 全体の測定があり、RTX 3060 / RTX A4000 でそれぞれ +3.2% / +0.7% と記録されていますが、これは chunk kernel と merge を含む `STRATA_ATTN_DAILY` の組み合わせの結果であり、`STRATA_ATTN_MERGE_V2` 単独の性能値ではありません。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:831-845` — `STRATA_ATTN_DAILY` の読み取り条件。HIP では常に false。
- `src/kernels/cuda/qsa_decode_attn.cu:910-920` — この変数の既定値、`atoi` による上書き、初回評価後の static cache。
- `src/kernels/cuda/qsa_decode_attn.cu:698-721,723-800` — 標準 merge と v2 merge の実装、およびソースコメントにある同一演算の説明。
- `src/kernels/cuda/qsa_decode_attn.cu:1028-1057,1059-1114,1117-1167,1174-1220` — batch、slot、batch rows、single-query 経路からの merge 選択。
- `include/strata/kernels/qsa_decode_attn.hpp:67-77` — parity 用インターフェースの説明。これは比較用で、エンジン経路が環境から選択する処理とは別です。
- `docs/DETAILS.md:2220-2228` — `STRATA_ATTN_DAILY` 全体の測定条件と数値。
