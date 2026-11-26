# `STRATA_DF2_HEAD_IL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 共通の DFlash2 実装 `Dflash2Drafter::record_block` で、draft head の行列積に interleaved activation 用の経路を許可するスイッチです。値が有効で、さらに `native_mmvq_il_supported` が型・行数・GPU 等をサポートすると判定した場合、Q8_1 活性を interleave して `native_mmvq_il` を呼びます。それ以外は `native_mmvq` を使います。実装コメントは interleaved head の出力が通常経路と bitwise 同一で draft が同じになるとしています（`engine/src/core/dflash2.cpp:596-605`）。

これは通常のモデル head 全般ではなく、DFlash2 draft round 内の head 計算に限った選択です。対象名を読む実装は `engine/src/core/dflash2.cpp:598` の 1 箇所です。`terminal/data/settings-register.json:6266-6280` にも登録情報がありますが、これは実行時読み取りではありません。

## 値と判定

`std::getenv` で取得し、値が存在していて先頭文字が `'0'` の場合だけ OFF、それ以外は ON とします。文字列全体の parse や数値変換はありません（`engine/src/core/dflash2.cpp:598`）。

| 条件 | unset | ON になる値の例 | OFF になる値の例 |
|---|---|---|---|
| CUDA/HIP 共通の読み取り | ON | 空文字、`1`、`true`、`false`、` 0`、`00` 以外の通常文字列 | `0`、`0anything`、`00` |

空文字は設定済みですが `e[0]` が NUL なので ON です。先頭の空白は除去せず、空白で始まる ` 0` は ON。大文字小文字、残りの文字、整数としての妥当性は判定しません。したがって `false` も ON です。値そのものの優先順位を変える CLI 引数・別設定はありません。

## 有効になる条件

- DFlash2 が選ばれ、draft round の `record_block` が呼ばれる必要があります。通常の DFlash2 launch は graph がまだない場合に capture し、その時 `record_block` を呼びます。profile 経路では各 draft round でも直接呼びます（`engine/src/core/dflash2.cpp:1174-1208`, `engine/src/core/dflash2.cpp:621-655`）。
- `STRATA_DF2_SKIP` に `head` が含まれる場合は head 部分を省略するため、この変数の読み取り箇所まで到達しません（`engine/src/core/dflash2.cpp:142-146`, `engine/src/core/dflash2.cpp:596-599`）。
- interleaved 経路は `native_mmvq_il_supported(head_type_, ndraft_, n_dvocab_)` が true の場合だけです。CUDA 実装では列数が 1〜8、multi-column exact が有効、対象 GPU architecture が許可され、行数テーブルが非ゼロで、型が IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K のいずれかであることが必要です。Q3_K は `STRATA_MMVQ_IL_Q3K` の判定で無効化できます。また dense INT8 Tensor Core decode がその形状をカバーする場合も interleave を選ばず通常経路になります（`engine/src/kernels/cuda/native_mmvq.cu:4056`, `engine/src/kernels/cuda/native_mmvq.cu:4190-4228`）。
- 行数テーブルは GPU 世代・head の行数と `STRATA_MMVQ_IL_ROWS` 等で変わります。Ada の `STRATA_MMVQ_IL_89`、sm_80 の `STRATA_MMVQ_IL_SM80` / `STRATA_DEFAULTS=026`、sm_70 / sm_75 / sm_60 / sm_61 用の `STRATA_SM70_TABLE`、`STRATA_SM75_IL` / `STRATA_SM75_PERF`、`STRATA_SM60_TABLE`、`STRATA_SM61_TABLE` もサポート判定に影響します（`engine/src/kernels/cuda/native_mmvq.cu:3874-3878`, `engine/src/kernels/cuda/native_mmvq.cu:4056-4143`, `engine/src/kernels/cuda/native_mmvq.cu:4190-4227`）。
- HIP ビルドでは `native_mmvq_il_supported` が常に false を返す実装なので、変数が ON でも interleaved 経路にはなりません（`engine/src/kernels/cuda/native_mmvq.cu:4255-4268`）。

## 実行時の詳細

値は `record_block` 内の関数ローカル `static const bool` で、head 部分を初めて実行する時に一度だけ評価されます。最初の評価は通常、初回 graph capture 時か profiling の最初の直接実行時です。`STRATA_DF2_SKIP` が head を飛ばす間は未評価です。一度評価された後の環境変更は反映されず、同じ実行ファイル内の drafter インスタンス間でも同じキャッシュ値を使います（`engine/src/core/dflash2.cpp:596-605`, `engine/src/core/dflash2.cpp:1174-1208`）。

ON かつ対応形状なら、`native_q8_1_interleave` で `xq_` から interleaved buffer `xil_` を作り、`native_mmvq_il` で `logits_` を計算します。サポートされない場合または変数が OFF の場合は `native_mmvq` にフォールバックします。後続の `df2_topk` と selector はどちらの経路でも同じ logits 出力先を使います（`engine/src/core/dflash2.cpp:587-613`）。

## ログと測定値

この変数の値や選択経路を知らせる専用ログはありません。interleaved kernel 内で例外が起きた場合は `record_block` が例外文字列を `err` に入れて失敗を返します。通常の graph capture で失敗すれば `draft_launch` は false を返し、capture 自体の CUDA エラーは `dflash2: capture: ...` として `err` に入ります。通常の `strata generate` 呼び出し元は `strata generate: %s` を stderr に出して終了コード 1 を返します（`engine/src/core/dflash2.cpp:614-617`, `engine/src/core/dflash2.cpp:647-650`, `engine/src/core/dflash2.cpp:1203-1208`, `engine/src/program/generate.cpp:25008-25011`）。

関連資料 `docs/DETAILS.md:1591-1595` は DFlash2 selector の Q4_0 表現に触れていますが、このスイッチや head interleave の性能測定値は示していません。コードコメント上の bitwise 同一性は上記の実装コメントの記載であり、この調査で再測定した結果ではありません。

## 根拠

- `engine/src/core/dflash2.cpp:596-605` — 環境変数の読み取り、分岐、draft head kernel の選択。
- `engine/src/core/dflash2.cpp:142-146`, `engine/src/core/dflash2.cpp:621-655`, `engine/src/core/dflash2.cpp:1174-1208` — skip 条件、capture / profiling、実行時の呼び出し。
- `engine/src/kernels/cuda/native_mmvq.cu:4056-4143`, `engine/src/kernels/cuda/native_mmvq.cu:4190-4228`, `engine/src/kernels/cuda/native_mmvq.cu:4255-4268` — CUDA の対応条件と HIP の unsupported 実装。
- `docs/DETAILS.md:1591-1595` — 関連する DFlash2 資料との照合。
