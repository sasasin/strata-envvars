# `STRATA_ATTN_DAILY`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

CUDA の QSA attention で、decode の chunk 計算に `attn_chunk_kernel_pre75`（PR #540 / Daily 系カーネル）を選び、merge に `attn_merge_v2_kernel` を選びます。CUDA の通常ビルドでは、設定しなければ従来の chunk kernel と merge kernel が使われます。HIP ではこの変数の判定は常に無効です。

環境変数を読む実装は `src/kernels/cuda/qsa_decode_attn.cu` の `daily_attn()` だけです。結果は関数内の `static const bool` に保存されます。

## 値と判定

| 値 | `daily_attn()` の結果 |
|---|---|
| unset | `false` |
| 文字列がちょうど `1` | CUDA では `true`、HIP では `false` |
| 空文字、`0`、`10`、`true`、その他すべて | `false` |

値は整数として変換せず、文字列全体を `v[0] == '1' && v[1] == '\0'` で検査します。したがって `10` や `1anything` は有効になりません。判定結果を最初に必要とした時点でキャッシュされ、以後プロセス内で環境変数を変更しても再読込されません。HIP コンパイルでは `daily_attn()` は環境を読まず `false` を返します。根拠: `src/kernels/cuda/qsa_decode_attn.cu:831-845`。

## 有効になる条件と相互作用

- `STRATA_ATTN_PRE75_BUILT` が定義されたビルドで、`pre75_attn()` は CUDA の `STRATA_ATTN_DAILY=1` を `true` として扱います。通常の CUDA ビルドではこのカーネルが組み込まれます。CUDA の `STRATA_EXPERIMENTAL_SM60` ビルドでは、Daily が無効でも compute capability が 75 未満なら同じカーネルが選ばれます。
- `STRATA_ATTN_PRE75` の値の先頭文字が `0` なら、CUDA/HIP 共通の `pre75_attn()` が先に `false` を返し、chunk カーネルを切り替えません。これは `STRATA_ATTN_DAILY=1` であっても適用されます。ただし `STRATA_ATTN_DAILY` は merge の既定値にも使われるため、`STRATA_ATTN_PRE75=0` だけでは `attn_merge_v2_kernel` への切替は取り消されません。
- `STRATA_ATTN_MERGE_V2` が空でない文字列に設定されると、その値の `atoi()` が 0 かどうかで merge の選択を上書きします。たとえば `0junk` は `atoi()` が 0 を返すので従来 merge、`1junk` は V2 merge です。空文字または unset なら `STRATA_ATTN_DAILY` の結果が既定値になります。merge の選択も `static const int` に保存されます。
- HIP では `STRATA_ATTN_DAILY` は常に無効ですが、`STRATA_ATTN_PRE75` による gfx103x 等の chunk kernel 選択は別に存在します。Daily 変数自体は HIP の chunk kernel 選択を有効にしません。

根拠: `src/kernels/cuda/qsa_decode_attn.cu:454-467, 847-885, 910-920`。

## 実行時の詳細

通常の CUDA QSA batch decode は `qsa_decode_attn_batch()` から chunk pass と merge pass を順に起動します。Daily が有効で、かつ `STRATA_ATTN_PRE75` がそれを無効化していない場合、`launch_chunks_batch()` は KV プール形式ごとの `attn_chunk_kernel_pre75` を起動します。別途 `STRATA_ATTN_V3` が有効で INT8 KV の条件に合う場合は、その分岐が優先されるため Daily の chunk kernel は使われません。merge pass は `attn_merge_v2()` の判定に従います。単一 query の `qsa_decode_attn_step()`、複数 slot の `qsa_decode_attn_slots()`、複数行の `qsa_decode_attn_batch_rows()` にも同じ `pre75_attn()` / merge 判定が関わります。`qsa_decode_attn_slots()` は Daily 系 kernel が必要なとき、slot 専用経路を使わず呼び出し側に fallback を促します。

この変数専用のログ出力はありません。kernel 起動後の CUDA エラーは既存の `qsa_decode_attn_batch: ...` 等のエラー経路で stderr に出力され、プロセスを終了します。

根拠: `src/kernels/cuda/qsa_decode_attn.cu:932-1025, 1041-1056, 1059-1114, 1136-1165, 1174-1219`。

## 文書と測定値

`docs/DETAILS.md:2220-2228` は、CUDA opt-in スイッチを 0.1.45 で測定した資料として、RTX 3060 / RTX A4000（sm_86）、IQ3_XXS、5 組の median 比較、長い prompt の後の decode という条件を示し、`STRATA_ATTN_DAILY=1` の値をそれぞれ +3.2% / +0.7% と記載しています。同資料は bit-exact とも記載しています。これらはその文書に記された過去の測定条件と結果であり、現在の HEAD で再測定した値ではありません。
