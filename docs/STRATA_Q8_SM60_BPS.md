# `STRATA_Q8_SM60_BPS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Pascal 向け Q8_0 decode GEMV の CUDA grid サイズを調整します。GPU の SM 数にこの値を掛けた数を grid の上限にし、各 SM あたりに何個の workgroup を投入するかを指定します。既定値は4です。

engine では、この変数単独でカーネルを有効にはしません。主スイッチ `STRATA_Q8_SM60` が有効で、Q8_0 の重みが packed registry に登録され、対象の shape がカーネルの制限を満たす場合に値が使われます。一方、同梱の `tools/q8_sm60_check.cu` はヘッダーのカーネルを直接呼ぶため、チェック実行時にもこの値が grid サイズへ反映されます。

## 値と判定

`q8sm60::blocks_per_sm()` の初回呼び出し時に `std::getenv()` で読み、`std::atoi()` で整数へ変換します。変換結果が正数ならその値を使い、それ以外は4にします。

| 環境変数の状態・値 | 変換と採用値 |
|---|---|
| 未設定 | `atoi` 相当の値を0として扱い、4 |
| 空文字、数字で始まらない文字列 | 変換結果0となり、4 |
| 正の整数として読める値 | その整数 |
| `0`、負数 | 4 |
| 数字の後ろに文字が続く値 | `atoi` が読んだ先頭の整数を採用。正数ならその値（例: `3junk` は3） |

`atoi` は先頭の空白と符号を許容するため、たとえば `  +3tail` は3になります。文字列全体の妥当性検査、上限 clamp、エラーや警告の出力はありません。kernel の grid は `min(groups, SM 数 × 採用値)` で決まり、shape に必要な `groups` が上限になります。

## 有効になる条件

- CUDA 実装であること。HIP コンパイルでは `q8_sm60_on()` が常に false を返し、このカーネル経路を使いません。
- `STRATA_Q8_SM60` が文字列全体で `1` であること。この主スイッチは別の static 値として初回評価時にキャッシュされます。未設定、空文字、`01`、`1anything` などは無効です。
- Q8_0 の dense matrix または output head が packed され、decode GEMV がその packed weight を見つけること。dense weight の shape が Q8_0 用の処理に入る必要があります。
- `q8sm60::launch()` が受け付ける shape であること。入力幅 `n_in` は32の倍数かつ128以上、列数 `ncols` は1〜8、shared-memory 使用量は48 KiB以下です。対象外ならこのカーネルは `false` を返します。その後は同ファイルの packed kernel、または呼び出し側の通常経路へ進みます。

## 実行時の詳細

`blocks_per_sm()` は `static const int` に結果を保存するため、プロセス内で最初に呼ばれた後の環境変更は反映されません。`launch_one()` は `grid = min(groups, sm_count() * blocks_per_sm())` として CUDA kernel を起動します。`groups` は出力行数と1 workgroup が担当する行数から計算され、`sm_count()` は CUDA API で取得します。device の取得または SM 数取得に失敗した場合、あるいは取得数が正でない場合は48を使います。

この値をログへ出す処理はありません。カーネル起動の失敗時にこの変数固有の fallback や診断はありません。`tools/q8_sm60_check.cu` も同じ header の `launch()` を直接呼び、独立した engine opt-in 判定はしません。packed weight の確保・変換に失敗した場合は、別途 `strata q8 sm60: ...` の stderr メッセージを出して通常の GGUF layout を維持します。

カーネルは Q8_0 の重みを再配置して使い、通常の exact kernel と積の加算順序が異なります。ソースコメントは出力が bitwise 一致しない（float 丸め差のみ）と説明しています。これはカーネル全体の性質であり、`STRATA_Q8_SM60_BPS` 個別の正確性や速度を示す測定値ではありません。

## 根拠

- `src/kernels/cuda/q8_sm60.cuh:85-109`: `atoi` による値の読み取り、既定値4、SM 数あたりの grid 上限。
- `src/kernels/cuda/q8_sm60.cuh:118-132`: kernel が受け付ける `n_in`、`ncols`、shared-memory 条件。
- `src/kernels/cuda/native_mmvq.cu:1932-1946`: `STRATA_Q8_SM60` の厳密な文字列判定、HIP で無効にする分岐、header の取り込み。
- `src/kernels/cuda/native_mmvq.cu:2053-2070,2232-2242`: packed registry からの呼び出しと、対象外 shape の fallback。
- `src/kernels/cuda/native_mmvq.cu:2252-2281`: Q8_0 weight の packed 処理、VRAM 確保・変換失敗時のログ。
- `src/core/native_dense.cpp:363-382`、`src/core/native_head.cpp:77-79`: dense matrix と output head の packed weight 登録箇所。
- `tools/q8_sm60_check.cu:1-25,53-54,98-100`: 同梱の parity/speed check が同じ header を直接利用する箇所。
- `docs/OLDER_GPUS.md:110-156`: GP100 向け opt-in kernel の説明と、PH402 で記録された測定条件。記載値は `STRATA_Q8_SM60` 全体の測定であり、BPS の個別比較ではありません。
