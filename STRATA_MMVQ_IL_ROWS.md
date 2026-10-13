# `STRATA_MMVQ_IL_ROWS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec（`native_mmvq_il`）で、型・列数・出力行数区分ごとに warp が処理する行数を指定する上書き表です。標準表の値を再ビルドせず試せます。`0` は interleaved kernel を使わず、通常の `native_mmvq` に戻す指定です。Verifier の dense projection / loaded output head の呼び出しで、上位の `STRATA_MMVQ_IL` 判定と kernel 対応条件を通過した場合に間接的に使われます。

## 値と判定

環境変数を最初に参照した時点で一度だけ parse し、結果を関数内 `static` の vector に保存します。未設定または空文字なら上書き項目はありません。空文字は警告も出しません。

形式はセミコロン区切りの `type:ncols:r0,r1,r2,r3,r4` です。`type` は GGML type の整数、`ncols` は 1〜4、5つの行数値はそれぞれ `0`、`1`、`2`、`4` のいずれかでなければ、その項目は無視されます。5区分は `n_out < 2048`、`< 4096`、`< 8192`、`< 12288`、`>= 12288` です。

実装は各セミコロン区間を `sscanf("%d:%d:%d,%d,%d,%d,%d%n", ...)` で読みます。5値まで読み取れて `ncols` が範囲内なら構文成立とし、`%n` が記録する読み取り終端は検査していません。そのため、5値の後ろの余分な文字は拒否されず無視されます。型は整数として読み取られますが、最終的に対応対象となるのは 23 (IQ4_XS)、12 (Q4_K)、13 (Q5_K)、14 (Q6_K)、11 (Q3_K) のみです。未知の型の有効形式項目は保存されますが、カーネル選択には使われません。

| 入力状態 | 動作 |
|---|---|
| 未設定 / 空文字 | 上書き項目なし。標準表を使う |
| 有効な項目 | 該当する型・列数・出力行数区分の値で標準表を上書き |
| 行数値が 0/1/2/4 以外 | その項目を無視し、stderr に `strata: STRATA_MMVQ_IL_ROWS: rows must be 0/1/2/4 - entry ignored` |
| 書式不正、または `ncols` が 1〜4 の範囲外 | その項目を無視し、stderr に `strata: STRATA_MMVQ_IL_ROWS: cannot read '<項目>' (type:ncols:r0,r1,r2,r3,r4) - ignored` |
| 同じ型と列数の項目が複数 | 先に現れた項目が使われる |

この parser はコメント上の「2〜4列」より広く `ncols=1` も受け付けます。また `ncols=1` の上書き検索は標準の1列用設定 (`STRATA_MMVQ_IL_T1`) より先です。したがって該当項目があれば、同じ shape に対する `STRATA_MMVQ_IL_T1=0` の標準1列抑止を越えて行数を返します。型 11 の上書きも `STRATA_MMVQ_IL_Q3K=0` 判定より先に返るため、その標準複数列抑止を越えます。上位の `STRATA_MMVQ_IL=0` は verifier から interleaved 経路へ入るのを止めるので、この上書きだけでは有効化できません。

## 有効になる条件

- この環境変数の実装は `#if !__HIPCC__` 側、つまり CUDA 実装にあります。HIP 側の `native_mmvq_il_supported()` は常に false、行数照会は常に 0 で、通常 kernel を使います。
- CUDA では `ncols` が 1〜4、`g_multi_exact` が true、GPU compute capability が対応対象であることが必要です。通常は sm_80 以上、または `STRATA_SM70_TABLE` によって opt-in された sm_70、`STRATA_SM60_TABLE` が有効な sm_60 です。
- さらに interleaved kernel が対応する型（23、12、13、14、11）である必要があります。上書き値が `0` のときは `native_mmvq_il_supported()` が false となり、呼び出し側は `native_mmvq()` に fallback します。
- Verifier 側では `STRATA_MMVQ_IL` が未設定または先頭文字が `0` 以外のときだけ interleaved 対応判定に進みます。この判定自体は初回呼び出しでキャッシュされます。

## 実行時の詳細

`native_mmvq_il_rows_for()` は、まず環境変数由来の項目を先頭から検索し、型と `ncols` が一致すれば出力行数区分の値を返します。一致しない場合は標準表を選びます。標準表は compute capability に応じて architecture 固有表または共有表を参照します。CUDA デバイスの capability は device ordinal ごとにキャッシュされ、環境由来の行数表はプロセス内で一度だけ parse されます。最初の parse 後にプロセス環境を変えても読み直しません。

Verifier の dense projection helper と loaded output head は `native_mmvq_il_supported()` が true の場合に `native_mmvq_il()` を呼びます。2〜4列では必要に応じて q8_1 activation の interleaved copy を作成します。1列では元の q8_1 block をそのまま使います。対応判定が false なら同じ処理箇所から通常の `native_mmvq()` を呼びます。実装コメントと `docs/MMVQ_IL_TABLE.md` は、表が速度選択のみを変え、対象カーネルの出力は通常 kernel と bitwise 同一と説明しています。この調査では測定や出力同一性を再検証していません。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:2608-2638`: 環境変数の形式、parse、警告、static cache。
- `src/kernels/cuda/native_mmvq.cu:2642-2662`: 環境上書きの優先順位、出力行数区分、標準表への fallback。
- `src/kernels/cuda/native_mmvq.cu:2690-2709`: CUDA architecture 条件と supported 判定。
- `src/kernels/cuda/native_mmvq.cu:2711-2747`: CUDA の kernel 呼び出しと未対応時の fallback、HIP stub。
- `src/kernels/cuda/native_mmvq.cu:1526-1532`: 返された行数 1/2/4 に対応する kernel dispatch。
- `src/core/verify.cpp:139,1085-1095,1769-1777`: verifier における環境ゲート、activation interleave、dense projection / loaded head の呼び出しと fallback。
- `docs/MMVQ_IL_TABLE.md:1-11,26-30`: 用途、標準表の説明、文書記載の例と測定手順。測定結果はソースコメントおよび資料上の記述として扱い、独自確認はしていません。
