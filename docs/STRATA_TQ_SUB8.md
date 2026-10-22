# `STRATA_TQ_SUB8`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の trellis 量子化 expert（TQ2_T/TQK6/TQK7）の grouped expert 計算で、条件を満たす行を8 lane単位で処理する sub8 カーネルを選べるようにします。対象になるのは主に gate/up の160 dot行と、特定の形状の down 行です。通常経路との計算結果の同一性は実装コメントに記されていますが、この調査では実行比較をしていません。

## 値と判定

値は数値として parse せず、最初の呼び出し時に一度だけ先頭文字を調べて `static const bool` に保存します。

| `STRATA_TQ_STAGE` | `STRATA_TQ_SUB8` | sub8 の要求状態 |
|---|---|---|
| 先頭文字が `0` | 任意 | 無効 |
| 先頭文字が `0` 以外 | 任意 | 無効（`tq_stage_on()` が true になる） |
| unset または空文字 | 先頭文字が `0` | 無効 |
| unset または空文字 | unset、空文字、または先頭文字が `0` 以外 | 有効候補 |

したがって `STRATA_TQ_SUB8=0anything` は無効、`STRATA_TQ_SUB8=false` や空文字は有効候補です。`STRATA_TQ_STAGE=0anything` は staging を明示的に無効化するため sub8 を許し得ますが、`STRATA_TQ_STAGE=1` や `false` は staging を有効化し、sub8 を止めます。大文字小文字、空白、残りの文字列は検証しません。

## 有効になる条件

- HIP コンパイルでは関数が常に `false` を返すため有効になりません。CUDA のみです。
- `STRATA_IQ_STAGE_GRID=0` などにより共通の `g_stage_grid` が false の場合は使われません。`g_stage_grid` 自体は unset/空文字/先頭文字が `0` 以外なら true です。
- gate/up は TQK6/TQK7（内部型144/145）、入力形状 `(n_embd / qk) * ipb == 160` のときに sub8 の grouped kernel を選びます。
- down は内部型144または146、`n_ff == 640`、旧 kernel と `STRATA_NO_SUB16_GU` が無効であることに加え、`tq_stage_on()` または `tq_sub8_on()` が true のとき、8-lane trellis down 行として扱います。
- `STRATA_TQ_STAGE` が未指定の場合、CUDA は GPU compute capability を調べ、major*10+minor が61未満（cc 6.0以下）のデバイスだけ既定で codebook staging を有効にします。cc 6.1以上では staging は既定無効ですが、sub8 は `STRATA_TQ_SUB8` の既定要求によって候補になります。明示した `STRATA_TQ_STAGE` はこの自動判定より優先します。

## 実行時の詳細

`launch_gu()` は上記 gate/up 条件を満たすと grid を32行単位に調整し、`native_gu_multi_kernel<TG, true, true>` を起動します。それ以外は通常の trellis grouped kernel 選択へ進みます。down 側では `tq_sub8` の有無が1 blockあたりの行数と `STRATA_TQ_ROWCH` による chunk 数を変え、その後 `launch_down()` が対応する trellis kernel を選びます。`STRATA_TQ_ROWCH` は既定4、1〜32に clamp されます。

この変数に対する専用ログ出力は確認できません。起動後の動作は expert の grouped CUDA 経路内で適用されます。値はカーネル実装の静的初期化時にキャッシュされるため、初期化後の環境変更は反映されません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3273-3284`: `env_on()` と共通 staged-grid flag の値判定。
- `src/kernels/cuda/iq_kernels.cu:3310-3328`: `STRATA_TQ_STAGE` の上書き判定、CUDA/HIP 分岐、GPU capability による既定 staging。
- `src/kernels/cuda/iq_kernels.cu:3330-3345`: `STRATA_TQ_SUB8` の読み取りと追加条件。
- `src/kernels/cuda/iq_kernels.cu:4073-4103`: gate/up の適用条件と kernel 選択。
- `src/kernels/cuda/iq_kernels.cu:4154-4168,5233-5236`: down kernel の選択、行数と chunk 数。
- `docs/release-notes-0.2.2.md:36`: RTX 3060 (12 GB) Gyro-S/M の測定条件・値を含むリリースノート上の記載。これはソースコードの実行による再測定ではない。
