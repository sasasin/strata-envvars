# `STRATA_ATTN_V3`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA decode attention の INT8 K/V 用 chunk kernel を、通常の `attn_chunk_kernel<1>` から `attn_chunk_q8_v3_kernel` に切り替えます。後者は Turing (SM 7.5) 向けに shared-memory の読み方、12 query head の reduction、確率値の配置を変えた CUDA kernel です。ソースコメントは演算順序とオペランドを保ち、結果が bitwise 一致すると説明しています。

切替は単一 query の `qsa_decode_attn_step()` とバッチの `qsa_decode_attn_batch()` の chunk pass にあります。環境変数の結果は `attn_v3_on()` 内の関数ローカル `static const int` に保存され、プロセスで最初に呼ばれた時点で一度だけ読み取られます。

## 値と判定

環境変数の文字列全体や数値としての妥当性は検査せず、設定されている場合は先頭文字が `'0'` かどうかだけを見ます（`src/kernels/cuda/qsa_decode_attn.cu:437-440`）。

| 設定 | 判定 |
|---|---|
| 未設定 | GPU の compute capability と `STRATA_SM75_PERF` による自動判定へ進む |
| 空文字 | 有効。値は設定済みで先頭文字が `'0'` ではないため |
| 先頭文字が `0` | 無効。例: `0`, `0abc` |
| それ以外の先頭文字 | 有効。例: `1`, `2`, `true`, `false`, 空白 |

この明示設定は GPU 世代を問わず判定上有効にします。環境変数が明示設定されていれば、GPU の capability 判定には進みません。

未設定の場合は現在の CUDA device ordinal が 0〜15 であること、CUDA の device 属性取得が成功すること、および `strata::sm75_default(major, minor)` が真であることが必要です。これは compute capability 7.5 かつ `STRATA_SM75_PERF` が `atoi` で 0 以外となる設定の場合に真です。`STRATA_SM75_PERF` の読み取りも初回に static cache され、未設定または `atoi` 結果が 0 なら通常 kernel を使います（`src/kernels/cuda/qsa_decode_attn.cu:441-450`; `include/strata/core/sm75_series.hpp:24-37`）。

## 有効になる条件

- CUDA コンパイルのときだけ有効です。呼び出し側の kernel 選択は `#if !defined(__HIPCC__)` 内にあり、HIP ビルドではこの分岐自体がありません（`src/kernels/cuda/qsa_decode_attn.cu:1004-1008,1196-1201`）。
- KV pool mode が `1`、すなわち `pools.k_q` があり、`k_q4` と `v_q4` による Q4 系形式ではない経路に限られます。mode `2`、`3`、`0` はこの変数では切り替わりません（同 `:905-908,1004-1025,1181-1213`）。
- バッチ API と単一 step API には切替があります。`qsa_decode_attn_slots()` には `attn_v3_on()` の呼び出しがなく、この変数による選択はありません（同 `:1059-1117`）。
- バッチ path で lane-cell scoring (`STRATA_ATTN_LANECELL`) が選ばれた場合、先に lane-cell kernel を起動するため `STRATA_ATTN_V3` の分岐には到達しません（同 `:950-973,1004-1008`）。
- `qsa_decode_attn_batch()` 自体は形状・buffer 条件を検証した後 chunk pass を起動します。失敗時は `qsa_decode_attn_batch: ...` を stderr に出して終了します。成功時、環境変数専用の選択ログはありません（同 `:1041-1056`）。

## 実行時の詳細

バッチ path では `launch_chunks_batch()` が KV mode を調べ、mode 1 かつ `attn_v3_on()` が真なら `attn_chunk_q8_v3_kernel` を launch します。それ以外の mode 1 は通常の `STRATA_ATTN_CHUNK_SEL(1, pre)` kernel に進みます。single-step path も mode 1 かつ判定が真のとき同じ V3 kernel を使い、それ以外は通常の INT8 chunk kernel を使います。両経路とも chunk 結果の後に merge pass を実行します（`src/kernels/cuda/qsa_decode_attn.cu:932-1025,1174-1214`）。

環境変数をプロセス起動後に書き換えても、`attn_v3_on()` の cached 値は再評価されません。未設定時の device 判定も ordinal ごとに `on[16]` に記録されます。CUDA 属性取得に失敗した場合は CUDA error を消費してその device では無効とします（同 `:437-450`）。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:329-340` — V3 kernel の用途、演算順序についての説明、RTX 2080 Ti のコメント内測定値、および `STRATA_ATTN_V3=0/1` の説明。
- `src/kernels/cuda/qsa_decode_attn.cu:437-450` — 環境変数の読み取り、未設定時の device ごとの判定と cache。
- `src/kernels/cuda/qsa_decode_attn.cu:932-1025,1041-1056` — バッチ chunk pass の切替と実行経路。
- `src/kernels/cuda/qsa_decode_attn.cu:1174-1214` — 単一 step path の切替。
- `include/strata/core/sm75_series.hpp:24-43` — `STRATA_SM75_PERF` の parse と Turing 判定。
- `docs/DETAILS.md:2248-2257` — Turing kernel 群の説明と `STRATA_ATTN_V3` の位置づけ。ここでは性能値を一般化していません。kernel コメントの RTX 2080 Ti 測定値は `src/kernels/cuda/qsa_decode_attn.cu:338-340` に記載されていますが、同コメントには測定手順・試行数の記載がないため、他環境の性能根拠にはしていません。
