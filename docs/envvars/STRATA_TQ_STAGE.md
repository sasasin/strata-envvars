# `STRATA_TQ_STAGE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA/HIP の grouped expert trellis（Gyro の TQ2_T / TQK6 / TQK7）カーネルで、4 KB の int8 codebook を shared memory に stage するかを制御する。未設定時は CUDA で GPU の compute capability に応じて自動選択し、明示値ではその選択を上書きする。これはカーネル経路の選択であり、数値計算の定義は変わらない。実装コメントは有効・無効どちらでも bitwise 同じ結果としている。

## 値と判定

`tq_stage_on()` は値を文字列全体として parse せず、先頭文字だけを調べる。空文字は unset と同じ自動選択。判定結果は関数内の `static const int` に一度保存される。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | 自動選択 |
| 先頭文字が `0`（例: `0`, `0abc`） | 明示的に無効 |
| それ以外の非空文字列（例: `1`, `2`, `true`） | 明示的に有効 |

明示的な有効値でも、`STRATA_IQ_STAGE_GRID=0` により codebook staging 全体が無効なら staging されない。後述のとおり HIP の自動選択は常に無効だが、明示的な非ゼロ値の判定は HIP 分岐より先に返るため、`STRATA_IQ_STAGE_GRID` が有効なら明示的に有効化できる。

## 有効になる条件

- 対象は trellis expert の grouped CUDA/HIP カーネル経路。`launch_gu()`、`launch_gu_swiglu()`、`launch_down()` で TQ 型について判定する。旧 kernel 経路や split 無効時など、別 kernel を選ぶ場合はこの設定による staging 経路に入らない。
- `STRATA_IQ_STAGE_GRID` が未設定・空文字・先頭文字が `0` 以外なら staging の土台が有効。先頭文字が `0` なら `STRATA_TQ_STAGE` が有効でも無効。
- 未設定時は CUDA で device の compute capability を取得し、`major * 10 + minor < 61` の GPU だけ自動的に有効。取得失敗、device 番号が `0..63` の範囲外、または 6.1 以上なら無効。HIP では自動選択は無効。
- `STRATA_TQ_STAGE=0` は trellis の staging を無効にし、CUDA の `tq_sub8_on()` も無効にする。`STRATA_TQ_SUB8=0` も sub8 経路だけを無効にする。`tq_sub8_on()` は HIP では常に false。

## 実行時の詳細

自動選択時、CUDA では初回の `tq_stage_on()` 呼び出し時点の device を問い合わせ、その結果を `per_dev[64]` に device ごとに保存する。属性取得に失敗した場合は CUDA の last error をクリアし、その device では無効として記録する。環境変数の判定自体は process 内で一度だけ行われるため、初回判定後に環境を書き換えても再評価されない。`STRATA_IQ_STAGE_GRID` はグローバル初期化時に読まれる。

有効時は gate/up と down の grouped TQ kernel が staged variant を選ぶ。未設定の CUDA 6.0 では自動でこの経路を使い、それ以外の CUDA GPU では既定で使わない。資料 `docs/GYRO.md` は Tesla P100（compute capability 6.0）の Gyro-S でこの最適化を 5 組の interleaved 測定で比較した結果に触れているが、その測定値は資料の条件に限られる。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3306-3328` — codebook、値の判定、自動選択、device ごとの capability cache。
- `src/kernels/cuda/iq_kernels.cu:3280-3284` — `STRATA_IQ_STAGE_GRID` の既定と無効化規則。
- `src/kernels/cuda/iq_kernels.cu:3334-3345` — `STRATA_TQ_STAGE` / `STRATA_TQ_SUB8` と sub8 経路の条件。
- `src/kernels/cuda/iq_kernels.cu:4073-4100,4130-4149,4154-4168` — grouped gate/up、SwiGLU、down kernel の dispatch。
- `src/kernels/cuda/iq_kernels.cu:5232-5236` — trellis down rows の sub8 dispatch 条件。
- `docs/GYRO.md:128-130` — P100 の測定に関する資料上の説明。
