# `STRATA_MMVQ_PF`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 実装の Q6_K wide MMVQ kernel で、量子化重みのロードを計算より先にまとめて発行するカーネル variant を選びます。正の整数のうち `2`、`3`、`4`、`6` は、それぞれ先行発行する load step 数 `U` としてテンプレート化された variant に対応します。これは主にカーネル選択を切り替える開発・調整用の環境変数です。

## 値と判定

値は `std::getenv()` の結果を `std::atoi()` に渡して整数化します。文字列全体の厳密な検証はありません。

| 環境変数の状態・値 | 判定と動作 |
|---|---|
| 未設定 | `0`。先行ロード variant を選ばない |
| 空文字、数値に変換できない文字列 | `atoi` の結果は `0`。先行ロード variant を選ばない |
| 整数として `2`、`3`、`4`、`6` | 対応する `U` の先行ロード variant を選ぶ |
| その他の値 | 先行ロード variant を選ばず、通常の wide kernel 選択へ進む。`5` など正数でも variant はない |

`atoi` のため、先頭の空白や符号を含む数値接頭辞は変換され、後続の非数値文字は無視されます。例えば `3junk` は `3` として扱われます。値は `q6k_pf()` 内の `static const int` に初回呼び出し時に保存されるため、その後の環境変更は反映されません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1689-1691`。

## 有効になる条件

値が `2`、`3`、`4`、`6` でも、Q6_K MMVQ が wide kernel の経路に入った場合に限り使われます。`native_q6_k_mmvq()` は最初に packed Q6_K 経路を試し、そこで処理された場合は戻ります。続いて wide kernel の有効フラグ、`ncols`、`n_in`、`n_out` の条件が評価されます。

- `STRATA_MMVQ_WIDE` が `0` 相当の場合、wide kernel 自体が無効になります。
- `1 <= ncols <= STRATA_MMVQ_WIDE_MAXC`、`n_in % 256 == 0`、`n_out >= STRATA_MMVQ_WIDE_MIN` が必要です。
- `STRATA_MMVQ_WIDE_MAXC` と `STRATA_MMVQ_WIDE_MIN` の未設定時の値は、`STRATA_MMVQ_A2` の判定によりそれぞれ `8` / `0` または `4` / `4096` です。
- Q6_K の wide 経路が選ばれた後、`STRATA_MMVQ_PF` の対応値があれば `U=2/3/4/6` の kernel を起動します。対応値がない場合は、`STRATA_MMVQ_WIDE_RPW` や sub-group 条件に基づく通常の wide kernel 選択へ進みます。

これらの条件を満たさない MMVQ では、この変数は動作に影響しません。コード上、この変数の読み取りは `sycl/src/kernels/cuda/native_mmvq.dp.cpp` のみで確認でき、CUDA 側の `src/kernels/cuda/native_mmvq.cu` には読み取りがありません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1697-1741,1989,3426-3447`。

## 実行時の詳細

先行ロード variant は `U` 個分の Q6_K 重みロードを先に発行した後、各 step の dot product を計算します。通常の wide variant に対し、処理内容は重みと Q8_1 活性値の積和です。環境変数の値を直接出力するログや、値の範囲エラーはこの読み取り経路にありません。対応外の正数もエラーにはならず、通常の wide kernel にフォールバックします。

関連資料 `docs/INTEL.md:448-454` は、Q6_K wide kernel のロード整列改善と測定値を記載していますが、`STRATA_MMVQ_PF` の値ごとの比較や性能値は記載していません。したがって、この変数自体による速度向上や正確性差は資料からは確認できません。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1621-1687` — 先行ロード variant の説明、重みロードと dot product の順序。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1689-1711` — 値の読み取りと `U=2/3/4/6` の選択。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3426-3447` — packed 経路、wide 経路の条件、および起動箇所。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1534-1536,1693-1741,1989` — 関連する wide kernel の既定値と選択条件。
- `docs/INTEL.md:448-454` — wide Q6_K kernel の整列変更についての資料。`STRATA_MMVQ_PF` の評価値は掲載されていない。
