# `STRATA_SM60_TABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の Pascal GP100（compute capability `sm_60`）で、2 種類のカーネル選択を切り替える。

- `engine/src/kernels/cuda/iq_kernels.cu` の専門家カーネルでは、`STRATA_EXP_LAYOUTS` が有効な CUDA build における既定の expert mode を選ぶ。既定の mode 8 は gate/up・SwiGLU・q8_1 の融合経路を候補にする。`0` にすると P100 は通常の CUDA layout を使う（同ファイル:6782-6803, 7196-7214）。
- `engine/src/kernels/cuda/native_mmvq.cu` の interleaved MMVQ では、P100 向け `kIlRows_60` テーブルを使用可能にするかを決める。`0` なら interleaved MMVQ を不許可にし、呼び出し側は `native_mmvq` に戻る（同ファイル:3891-3896, 4194-4214, 4218-4237）。

この設定は計算結果や model の選択を直接指定せず、条件を満たす形状で使う CUDA カーネル経路を切り替える。HIP ではこの名前を読む実装がなく、CUDA 専用の二つの分岐に限られる（`native_mmvq.cu`:1745-1746, 4263-4271、`iq_kernels.cu`:6807-6808）。

## 値と判定

両方の読み取り箇所は `std::getenv` の結果を `std::atoi` に渡し、変換結果が非ゼロかどうかで判定する。`nullptr`（未設定）は明示的に有効扱い。空文字、数値に変換できない文字列、`0` または `0` から始まる数値部分は `atoi` が 0 を返すため無効。文字列全体の検証やエラー報告はない（`native_mmvq.cu`:4198、`iq_kernels.cu`:6785-6786）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA `sm_60` の両経路 | 有効（既定 ON） | `1`, `2`, `-1`, `1abc` | 空文字, `0`, `0abc`, `true`, `false`, `abc` |
| `sm_60` 以外、または該当機能を含まない build | この変数による変更なし | なし | なし |

`atoi` は先頭の空白と符号を許容し、整数として読める先頭部分を変換するため、たとえば `  +1tail` は有効、`  -0tail` は無効になる。真偽文字列としての解釈、大文字小文字の区別、空白除去後の文字列全体チェックは行わない。

## 有効になる条件

- **expert mode の経路:** `STRATA_EXP_LAYOUTS` が有効な CUDA build であること。`exp_mode()` は GPU の compute capability を調べ、`sm_60` かつ本変数が有効なら mode 8 を選ぶ（`iq_kernels.cu`:6807-6808, 6778-6803）。mode 8 でも、`native_expert_grouped` の `fused_gu` 条件（例: block/quantization type、埋め込み幅、`n_ff % 32 == 0`）を満たさない場合は、その fused gate/up 経路には入らない（同ファイル:7205-7215）。
- `grid_groups > 0 && grid_groups < cap_groups` の専門家呼び出しは `exp_mode()` を呼ばず `em0=0` とするため、この設定による mode 8 を使わない（`iq_kernels.cu`:7196-7203）。
- `STRATA_EXP_MODE` が `exp_mode()` の static 初期化時に `0` 以上へ変換されると、P100 の既定選択より優先される。ベンチ用 `native_expert_set_mode()` が非負の mode を設定した場合はそれが最優先（同ファイル:6763-6803, 6822-6828）。
- **interleaved MMVQ 経路:** CUDA 実装で、GPU ordinal が 0–15 の範囲にあり、compute capability が `6.0`、`native_mmvq_il_supported()` が `ncols`（1–8）、`g_multi_exact`、重み型とテーブルの行数に基づいて対応と判定すること（`native_mmvq.cu`:4202-4214, 4218-4227）。P100 のテーブルに行があるのは GGML type 23 / 12 / 13 / 14 / 11 のうち該当する型、2–4 列の形状で、出力幅クラスごとの行数が 0 でない場合。1 列は `kIl1Arch` に sm_60 がなく、5–8 列も別の wide-table の `Il58Arch` に sm_60 がないため、本変数だけでは有効にならない（同ファイル:3891-3896, 4009-4050, 4112-4143）。
- `g_multi_exact` は初期値 `true` だが API で変更できる。false のとき interleaved MMVQ は使われない（`native_mmvq.cu`:1246, 3272-3273, 4218-4219）。
- `STRATA_MMVQ_IL_Q3K=0` は type 11（Q3_K）をテーブル経路から除外する。`STRATA_MMVQ_IL_ROWS` が指定されていれば該当 type・列数の既定テーブル行を差し替え、ベンチ用 `native_mmvq_il_tune()` も行数を直接指定できる（`native_mmvq.cu`:4078-4108, 4135-4143, 4184-4187）。
- interleaved MMVQ が未対応なら `native_mmvq_il()` は通常の `native_mmvq()` を呼ぶ。対応しても、テーブルの該当 type・列数・出力幅クラスの行数が 0 なら `native_mmvq_il_supported()` は false となり、通常経路へ戻る（同ファイル:4112-4143, 4226-4237）。
- `native_mmvq_il_supported()` は一定条件で `dense_i8_tc_mmvq` に処理を譲るため interleaved 経路を辞退する（同ファイル:4220-4224）。この判定は形状・型・別設定に依存する。

## 実行時の詳細

expert mode 側では `exp_mode()` 内の `per_dev[64]` がデバイス ordinal ごとに判定結果を保存する。最初にそのデバイスの mode を必要とした時点で環境変数を読み、以後同じプロセス内での環境変更はそのデバイスの既定 mode に反映されない（`iq_kernels.cu`:6764-6803）。`STRATA_EXP_MODE` 自体も関数内 static で初回評価時に保存される。

interleaved MMVQ 側では `sm60_table_on()` 自体は値を static 保存しないが、その呼び出し元 `il_arch_ok()` が可否を `ok[16]` にデバイスごとにキャッシュする。したがって最初の対応判定後に環境を変更しても、そのデバイスの可否は再評価されない（`native_mmvq.cu`:4198, 4202-4215）。いずれの経路もリクエストごとに環境を読み直す構造ではない。

この変数の読み取りに伴う起動ログや診断ログはない。expert mode の分岐で融合条件が成立しない場合は他の実装経路が続き、interleaved MMVQ が不許可の場合は `native_mmvq` へフォールバックする。後者のフォールバック自体はこの分岐では警告を出さない（`native_mmvq.cu`:4230-4237）。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:6763-6803` — expert mode の override、値の読み取り、GPU 世代別の選択と device cache。
- `engine/src/kernels/cuda/iq_kernels.cu:7196-7215` — 呼び出し時の mode 抑制条件と融合 gate/up の適用条件。
- `engine/src/kernels/cuda/native_mmvq.cu:3891-3896` — P100 向け行テーブル。
- `engine/src/kernels/cuda/native_mmvq.cu:4009-4050, 4078-4108, 4112-4143` — 1 列および wide-table の GPU 対応範囲、形状・型・テーブル行の選択と上書き。
- `engine/src/kernels/cuda/native_mmvq.cu:4190-4237` — 環境変数判定、compute capability の cache、interleaved MMVQ 対応判定と通常 MMVQ への fallback。
- `engine/src/kernels/cuda/native_mmvq.cu:1745-1746, 4263-4271` — interleaved 実装は CUDA 専用で、HIP 側 stub は通常 MMVQ に委譲する。
