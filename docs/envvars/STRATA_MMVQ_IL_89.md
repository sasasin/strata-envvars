# `STRATA_MMVQ_IL_89`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の `native_mmvq_il` が使う、compute capability 8.9（sm_89 / Ada）向け行数テーブル `kIlRows_89` と1列用 `kIl1Rows_89` の選択を制御する。行数テーブルは量子化形式・列数・出力行数クラスに対して、warp が処理する行数を選ぶ。選択行数が 0 なら `native_mmvq` の通常カーネルへ戻り、0 以外なら interleaved MMVQ カーネルを使う。ソースはテーブル選択が出力 bit を変えないと説明している。実行時の選択は `native_mmvq_il_rows_for` から `native_mmvq_il_supported` / `native_mmvq_il` に伝わる（`engine/src/kernels/cuda/native_mmvq.cu:3934-3940,4112-4143,4218-4252`）。

通常の CUDA 実行では `il_89_opt_in()` 内の関数 `static` が初回に `getenv` した結果を保存する。プロセス起動後に環境値を変更しても再評価されない。`STRATA_DEFAULTS` も `qwen_defaults_026()` の関数 `static` で初回評価される（`engine/src/kernels/cuda/native_mmvq.cu:4061-4064`、`engine/include/strata/core/defaults_026.hpp:21-30`）。

同梱の CUDA 診断プログラム `mmvq_il_parity` も `check_tables()` でこの値を読み、sm_89 の表が期待値と合うかを確認する。CUDA 有効時にビルドされ、CMake には `STRATA_MMVQ_IL_89=1` で表確認だけを行うテスト登録がある（`engine/src/kernels/mmvq_il_parity.cpp:402-424,521-526`、`engine/cmake/strata_gpu_engine.cmake:807-815`）。

## 値と判定

Strata は値全体を数値や真偽値として parse しない。`mmvq_il_89_resolve` は文字列の先頭 1 文字だけを見て、`'1'` なら ON、`'0'` なら OFF、それ以外は既定規則へ進む。したがって空文字、未設定、`true`、`false`、先頭が空白の値はいずれも既定規則になる。`10` / `1anything` は ON、`0anything` は OFF。大文字小文字の解釈や数値妥当性の検査はない（`engine/include/strata/core/sm120_series.hpp:151-169`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA の sm_89 テーブル選択 | `STRATA_DEFAULTS=026` でなければ ON | `1`, `10`, `1anything` は明示 ON | `0`, `0anything` は明示 OFF |
| 上記以外の文字列 | 既定規則 | `true`, `2`, 空文字、` 1` は、`STRATA_DEFAULTS` と GPU 条件に従う | 同左。独立した「無効文字列」扱いにはならない |
| HIP 実装 | 該当なし。HIP 側は interleaved path をサポートしない | 該当なし | 該当なし |

既定規則は `!v026 && !hip && cc == 89`。ここで `v026` は `STRATA_DEFAULTS` が厳密に `026`、`0.2.6`、`v0.2.6` のいずれかと一致する場合に限り true（空白や他の表記は一致しない）。環境変数を明示して先頭が `1` なら、このマスタースイッチより優先される。先頭が `0` は常に OFF（`engine/include/strata/core/sm120_series.hpp:154-169`、`engine/include/strata/core/defaults_026.hpp:21-29`）。

## 有効になる条件

- 該当する実装は `native_mmvq.cu` の CUDA 側で、HIP 側の `native_mmvq_il_supported` は常に false、`native_mmvq_il` は `native_mmvq` に委譲する（`engine/src/kernels/cuda/native_mmvq.cu:4255-4271`）。
- 独自の `kIlRows_89` / `kIl1Rows_89` が選ばれるのは compute capability が 8.9 の場合だけ。`=1` を別の GPU で指定しても、その GPU 用の sm_89 表が適用されることはない（`engine/src/kernels/cuda/native_mmvq.cu:4065-4076,4139-4142`）。
- 実動作には `native_mmvq_il_supported` の条件も必要: 1〜8列、`g_multi_exact`、対応 GPU architecture、対応する量子化形式（IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K）、選択された行数が非 0 であること。dense int8 Tensor Core GEMM が形状を受け持つ場合は interleaved 経路を辞退する（`engine/src/kernels/cuda/native_mmvq.cu:4218-4227`）。
- 通常の検証経路では `STRATA_MMVQ_IL` が別途ゲートとなる。先頭文字が `0` なら interleaved 量子化・MMVQ を使わず、それ以外（未設定・空文字を含む）は有効。こちらも関数内 `static` で一度だけ読む（`engine/src/core/verify.cpp:192-194,1835-1854`）。
- Q3_K（type 11）は `STRATA_MMVQ_IL_Q3K` の先頭文字が `0` なら表の行数を 0 にする。未設定では有効（`engine/src/kernels/cuda/native_mmvq.cu:4055-4056,4135-4142`）。1列用テーブルはさらに `STRATA_MMVQ_IL_T1` が先頭文字 `0` でないことが必要で、sm_89 の表では Q3_K の一部出力行クラスだけが非 0（`engine/src/kernels/cuda/native_mmvq.cu:4016,4055,4127-4133`）。
- `STRATA_MMVQ_IL_ROWS` に現在の type と列数に一致する有効エントリーがあると、アーキテクチャ別表の選択より先にその値を返すため、この環境変数による表選択を覆う。5〜8列は別の wide 表を通り、sm_89 用の wide 表は登録されていない（`engine/src/kernels/cuda/native_mmvq.cu:4078-4108,4112-4143`）。
- 2〜4列では sm_89 表のうち RTX 4070 と RTX 4080 の行数が一致したセルだけが非 0。1列では Q3_K 専用表を使う。表に該当する行がないセルは 0 となり通常カーネルへ戻る（`engine/src/kernels/cuda/native_mmvq.cu:3928-3940,4016-4049,4230-4237`）。

## 実行時の詳細

通常の CUDA 経路では `native_mmvq_il_supported` が `il_rows()` を呼び、その内部の `native_mmvq_il_rows_for` が sm_89 のテーブルを調べる。環境値が ON なら対応セルから行数を返し、OFF なら共有表 `kIlRowsShared` を使う（Q3_K は共有表にエントリーがないため 0）。結果が 0 の場合、呼び出し側は interleaved 変換を省くか、`native_mmvq_il` から `native_mmvq` にフォールバックする。非 0 なら量子化形式に対応する `launch_il_rows` を起動する（`engine/src/kernels/cuda/native_mmvq.cu:4112-4143,4218-4252`、`engine/src/kernels/cuda/shared_expert.cu:230-256`）。

この値は起動時の一括処理ではなく、表引きが最初に必要になったときに読み込まれて `static` に保持される。子プロセスへの転送や CLI 引数による上書きは、この変数について Strata ソース上で確認できない。`mmvq_il_parity` では `check_tables()` の実行ごとに読み、指定値に基づく期待表と実際の lookup を比較する（`engine/src/kernels/mmvq_il_parity.cpp:402-424`）。

## ログと測定値

通常のテーブル選択について、この変数の値や選択結果を出すログは確認できない。カーネル起動後は `launch_check()` を呼び、失敗時は通常の CUDA 起動エラー経路に進む（`engine/src/kernels/cuda/native_mmvq.cu:4244-4252`）。

診断プログラムは表の不一致を `FAIL table: sm_89 is ...` と出力し、最後に `mmvq_il_parity: FAIL` を表示して非 0 で終了する。一致時は `mmvq_il_parity: OK (every case, T 1-8, rows 1/2/4 and the table, bitwise)` を表示して 0 で終了する（`engine/src/kernels/mmvq_il_parity.cpp:420-424,525-526`）。CMake の `mmvq_il_parity_89table` は環境変数を `1` にしてこの表確認を実行する（`engine/cmake/strata_gpu_engine.cmake:813-815`）。

## 根拠

- 値判定と既定規則: `engine/include/strata/core/sm120_series.hpp:151-169`、`engine/include/strata/core/defaults_026.hpp:21-30`
- CUDA 表、cache、表引き、kernel dispatch: `engine/src/kernels/cuda/native_mmvq.cu:3928-3940,4051-4064,4112-4143,4218-4271`
- 通常の呼出条件と全体ゲート: `engine/src/core/verify.cpp:192-194,1835-1854`、`engine/src/kernels/cuda/shared_expert.cu:230-256`
- parity 診断と CMake 登録: `engine/src/kernels/mmvq_il_parity.cpp:402-424,521-526`、`engine/cmake/strata_gpu_engine.cmake:807-815`
