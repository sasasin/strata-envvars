# `STRATA_MMVQ_RPW`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版の native Q6_K MMVQ で、row-blocked kernel を使うときの「1 warp が処理する出力行数」を選ぶ調整値です。`1`、`2`、`4` はそれぞれ行数を指定し、未設定または 0 は row-blocked kernel を選びません。複数列では既存の shared kernel、1列では既存の単一列 kernel に進みます。ソースコメントでは bench knob とされ、既定の shared kernel は warm clocks で同等と測定されたため既定値は 0 です。

実装は `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあります。トップレベル CUDA 実装 `src/kernels/cuda/native_mmvq.cu` にはこの変数の読み取りがありません。この設定の対象は SYCL build の経路です（`sycl/CMakeLists.txt:1-7,87-104`）。

## 値と判定

`rowwarp_rpw()` は `std::getenv()` で取得した文字列を `std::atoi()` で整数化します。未設定なら 0 です。明示的な空文字や整数に変換できない文字列も `atoi` の結果は 0 になります。`atoi` は整数として読める先頭部分を使うため、例えば `2junk` は 2、`-1` は -1 です。文字列全体の一致や範囲 clamp はありません。

| `atoi` の結果 | row-blocked kernel の選択 |
|---|---|
| 1、2、4 | 対応する rows-per-warp kernel を選択可能 |
| 0、負数 | 選択しない（通常経路へ進む） |
| 正数だが 1、2、4 以外 | 条件の入口は通るが対応する launch 分岐がなく、通常経路へ進む |

判定結果は `rowwarp_rpw()` 内の関数ローカル `static const int` に保存されます。最初の呼び出し後にプロセス環境を変更しても、この値は再読込されません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2000-2003,3448-3456`。

## 有効になる条件

値が 1/2/4 でも、次の条件を満たす Q6_K 呼び出しでなければ row-blocked kernel は選ばれません。

- `ncols` が 1〜4。
- `n_in` が 256 の倍数。
- 先行する packed Q6_K 経路が当該 weight 行列を処理していない。
- 先行する Q6_K wide 経路が当該呼び出しを処理していない。

特に `STRATA_MMVQ_WIDE` は既定で有効です。既定の `STRATA_MMVQ_A2` も有効なら、wide 経路の既定 gate は `ncols` 1〜8、`n_in % 256 == 0`、`n_out >= 0` なので、通常の有効な Q6_K shape は rowwarp 判定より先に wide kernel が処理します。したがって、既定状態ではこの変数を 1/2/4 にしても rowwarp 経路には到達しません。wide 経路を無効にするか、wide の範囲条件から外れる場合に、この設定が rowwarp 選択へ影響し得ます。packed 経路については、登録済みの packed weight が対象 shape と一致し、複数列の場合は exact multi mode であるとき、先に packed kernel を起動して戻ります。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2699-2722,3426-3456`。wide の既定値・条件は `1989,1693-1695,3433-3446`。

## 実行時の詳細

rowwarp kernel は warp ごとに連続する `RPW` 行を処理します。各入力ブロックについて列ごとの activation fragment を一度読み、`RPW` 行の weight fragment と dot product を計算し、各行・列の部分和を warp 内で reduce して出力に書きます。対応する `RPW` はコンパイル時 template 値で、呼び出し側は 12 通り（列数1〜4 × rows-per-warp 1/2/4）の分岐から一致した kernel を起動します。一致しなければ通常の検証後、複数列では既存の multi/shared kernel、1列では既存の単一列経路へ進みます。

rowwarp の dispatch は fallback 経路にある `validate_shape`、`n_out`、pointer、stream の検証より前にあります。一致する 1/2/4 の分岐では kernel を起動して戻るため、これらの後続検証は通りません。通常経路では検証される不正な直接呼び出しを rowwarp 選択時にどう扱うかは、この dispatch 部分では確認できません。

変数自体によるログ出力、警告、エラー処理はありません。範囲外の正数もエラーにせず、対応する分岐がないため通常経路に戻ります。ソースコメントは、rowwarp が activation の再読込や barrier/SLM reduction を避ける構造であると説明していますが、この調査では新たな性能測定や出力一致の検証はしていません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1464-1503,1991-2003,3448-3456`。

## 文書との照合

`docs/DETAILS.md` にこの変数の記述はありません。`docs/INTEL.md:448-455` は Q6_K wide kernel と `STRATA_MMVQ_A2=0` の経路を説明していますが、rowwarp knob には触れていません。コードでは A2 が有効な既定状態で wide 経路が先に選ばれ、A2 を無効にした場合も shape 条件によって rowwarp 判定が後続します。rowwarp が既定値 0 の場合はそのまま従来経路へ進むため、INTEL 文書にある「old path」の説明は既定値での動作と整合します。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2000-2003`: 環境値の読み取り、`atoi`、既定値、static cache。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1464-1503`: rowwarp kernel の処理。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1991-1998`: kernel launch と grid の行数計算。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2699-2722,3426-3456`: packed / wide 経路の後にある適用 gate と列数別 dispatch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1693-1695,1989,3433-3446`: wide 経路の設定値と条件。
- `sycl/CMakeLists.txt:1-7,87-104`: SYCL build の migrated source 解決規則。
