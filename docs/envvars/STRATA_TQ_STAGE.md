# `STRATA_TQ_STAGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA IQ grouped-expert の TQ trellis 量子化（`TQ2_T` / `TQK6` / `TQK7`）について、int8 codebook を shared memory に stage するカーネルを選ぶ。通常は CUDA compute capability 6.0 だけ stage し、それ以外は global table を使う。設定値でこの選択を上書きできる。さらに同じ変数は CUDA の TQ gate/up にある 8-lane (`sub8`) カーネルの選択にも関わる。読み取りと選択は `engine/src/kernels/cuda/iq_kernels.cu` の `tq_stage_on()` / `tq_sub8_on()` にある（同ファイル:3722-3761）。

コードコメントと Gyro のリリース資料は、staging の有無で演算結果は bitwise 同一と説明している。これは資料上の説明であり、本調査で実行比較はしていない（`engine/src/kernels/cuda/iq_kernels.cu:3722-3725`, `docs/release-notes-0.2.2.md:36-37`）。

## 値と判定

`tq_stage_on()` は最初の呼び出し時に環境値を static cache する。未設定または空文字なら自動判定（内部値 `-1`）、非空なら先頭 1 文字だけ見て `0` は off、それ以外は on とする。文字列全体や数値としての妥当性は検査しない。したがって `0anything` は off、`1`・`true`・`false`・` 0` はいずれも on であり、大文字小文字や後続文字は判定に影響しない。明示的な on は `STRATA_IQ_STAGE_GRID` が無効なら staging されない（`engine/src/kernels/cuda/iq_kernels.cu:3696-3700,3726-3744`）。

| 条件 | unset / 空文字 | 設定時に staging が有効 | 設定時に staging が無効 |
|---|---|---|---|
| CUDA (`__HIPCC__` ではない) | `STRATA_IQ_STAGE_GRID` が on で、現在 device の compute capability が 6.1 未満なら on。それ以外は off | 非空値の先頭文字が `0` 以外、かつ `STRATA_IQ_STAGE_GRID` が on | 空文字は自動判定。非空値の先頭文字が `0` なら off。さらに `STRATA_IQ_STAGE_GRID=0...` なら、明示 on でも off |
| HIP (`__HIPCC__`) | off | 同じ先頭文字規則で on。ただし `STRATA_IQ_STAGE_GRID` が on の場合 | 空文字は自動判定で off。非空値の先頭文字が `0` なら off。`STRATA_IQ_STAGE_GRID=0...` でも off |

CUDA の自動判定では `cudaGetDevice` と compute capability major/minor を調べ、major×10+minor が 61 未満の device を on とする。device 番号が 0–63 の範囲外、または属性取得に失敗した場合は off。HIP ではこの自動 device 判定をせず off にする。明示値の分岐は HIP 用の compile-time 分岐より先に評価されるので、HIP でも明示 on は `STRATA_IQ_STAGE_GRID` が許す限り有効になりうる（`engine/src/kernels/cuda/iq_kernels.cu:3726-3744`）。

別の読み取り `tq_sub8_on()` でも、`STRATA_TQ_STAGE` の先頭文字が `0` なら sub8 を無効にする。その他（未設定・空文字を含む）では `STRATA_TQ_SUB8` を見て、こちらの先頭文字が `0` なら無効、それ以外は候補として on。最終的には `STRATA_IQ_STAGE_GRID` が on、`STRATA_NO_SUB16_GU` が off、かつ `tq_stage_on()` が off である必要がある。HIP では関数自体が常に false（`engine/src/kernels/cuda/iq_kernels.cu:3746-3761`）。

このため `STRATA_TQ_STAGE` が明示 on の場合、codebook staging を選び、sub8 は `!tq_stage_on()` 条件で無効になる。先頭文字 `0` の場合は両方が無効になる。unset / 空文字なら CUDA は compute capability と他条件に応じて staging または sub8 を選ぶ。CLI 引数や設定ファイルによる上書きはこのコードにはなく、確認できた優先関係は上記の環境変数間のみ。

## 有効になる条件

- 対象は `engine/src/kernels/cuda/iq_kernels.cu` に実装された native grouped-expert 経路で、TQ 型は整数型 ID 144–146 として扱われる（`kTqType`, 同ファイル:993-995）。モデルの expert がこの TQ 型でなければ、この変数によるカーネル選択は発生しない。
- Gate/up の通常の staged 分岐では、TQ 型に `tq_stage_on()` が true であることが必要。false のときは unstaged `native_gu_multi_kernel` に進む。TQ 型の gate/up で sub8 を使うには、さらに型が 144 または 145、dot 数が 160 であることが必要（同ファイル:4541-4570）。
- Down 側は TQ 型で、`STRATA_OLD_IQ_MMVQ` による旧 kernel 経路を選ばず、`STRATA_IQ_STAGE_GRID` が有効であることが前提。`tq_stage_on()` または `tq_sub8_on()` が true の場合は staged TQ kernel、それ以外は unstaged TQ kernel を選ぶ（同ファイル:4622-4636）。
- Down の sub8 行形状は追加で down 型が 144 または 146、`n_ff == 640`、`STRATA_NO_SUB16_GU` が無効であることを要する。満たさなければ通常の down 行構成を使う（同ファイル:7340-7343）。
- `STRATA_IQ_STAGE_GRID` は unset / 空文字なら on、先頭文字が `0` なら off。これが off だと `STRATA_TQ_STAGE=1` 相当でも shared-memory staging と sub8 は無効（同ファイル:3696-3700,3728,3760）。`STRATA_NO_SUB16_GU` は unset / 空文字 / 先頭 `0` なら off、それ以外の非空値は on（同ファイル:3689-3695）。
- HIP は unset 時に `tq_stage_on()` が false、sub8 も常に false。明示 on の staging 分岐は存在するが、実行環境・ビルドで実際に利用されるかは本調査では実行確認していない（同ファイル:3726-3744,3750-3761）。

## 実行時の詳細

`STRATA_IQ_STAGE_GRID`、`STRATA_NO_SUB16_GU`、`STRATA_OLD_IQ_MMVQ` はファイル内 namespace の初期化時に読み取られる。`STRATA_TQ_STAGE` は `tq_stage_on()` の初回呼び出し時に static 保存され、CUDA の自動判定結果も device ごとの 64 要素配列に保存される。`tq_sub8_on()` の判定も初回呼び出し時に static 保存される。したがって実行中に環境を変更しても、それらの判定は更新されない（`engine/src/kernels/cuda/iq_kernels.cu:3689-3707,3726-3761`）。

選択された gate/up kernel は shared memory に `tq_lut_i8` の 2048 個の 16-bit 要素（4 KB）をコピーし、staged kernel はそのコピーを参照する。unstaged kernel は global table を参照する。down 側でも同じ staged codebook を使い、sub8 選択時は行形状と chunk 数を変えて launch する（同ファイル:771-785,2036-2041,4550-4567,4628-4634,7340-7343）。

## ログと測定値

環境変数の値や自動判定結果を報告する専用ログは見つからなかった。device 選択・属性取得に失敗した場合は `cudaGetLastError()` を呼び出してエラー状態を消費し、ここでは警告を出さず off にする（`engine/src/kernels/cuda/iq_kernels.cu:3735-3742`）。後続 kernel launch のエラーは `check()` が `what: error string` を stderr に出して `exit(1)` する経路がある（同ファイル:47-50,7316,7337,7409）。

Strata の v0.2.2 release notes は、Gyro-S の Tesla P100（compute capability 6.0）decode が `STRATA_TQ_STAGE` による variant で約 30%向上した測定を記載する。測定は 5 組の interleaved pairs、CUDA 12 packages に当該カード向けコードがあり、CUDA 13 packages にはない条件。別途 RTX 3060 12 GB の Gyro-S / Gyro-M 比較は 5 組の interleaved pairs とされるが、その記述は主に sub8 path で、`STRATA_TQ_SUB8=0` の off switch を明記している。これらは文書に記載された測定であり、今回再測定していない（`docs/release-notes-0.2.2.md:34-37`）。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:3696-3707` — staging 共通 gate と他の関連環境値の初期化。
- `engine/src/kernels/cuda/iq_kernels.cu:3722-3761` — `STRATA_TQ_STAGE` の2箇所の読み取り、自動判定、sub8 との関係。
- `engine/src/kernels/cuda/iq_kernels.cu:771-785,993-995,2036-2041` — TQ 型・codebook と shared-memory staging。
- `engine/src/kernels/cuda/iq_kernels.cu:4541-4570,4622-4636,7340-7343` — gate/up・down の実際の dispatch 条件。
- `engine/src/kernels/cuda/iq_kernels.cu:47-50,3735-3742,7316-7409` — 失敗時の観測経路。
- `docs/release-notes-0.2.2.md:34-37` — 資料に記載された測定条件と結果。
