# `STRATA_DENSE_I8_TC_MIN_T`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の native MMVQ で dense INT8 Tensor Core 経路を選ぶ列数 `ncols` の下限を設定する。`n_out >= 1024`、対応する量子化型、対応 GPU、さらに `STRATA_DENSE_I8_TC` が有効である条件を満たす場合に、`ncols` がこの下限以上なら通常 MMVQ カーネルより先に `dense_i8_tc_mmvq` を試す。既定の下限は 9 で、値を小さくすると 1～8 列でもその経路を試せる。対象は生成 token 数などの設定ではなく、MMVQ 呼び出しの列数に対するカーネル選択条件である（`engine/src/kernels/cuda/native_mmvq.cu:3767-3782`）。

同じ下限は CUDA の interleaved MMVQ 対応判定でも参照される。対象形状では interleaved 経路が `false` を返し、呼び出し側が `native_mmvq` に進むようにする（`engine/src/kernels/cuda/native_mmvq.cu:4218-4234`）。

## 値と判定

`dense_i8_tc_min_t()` が `std::getenv` で読み、空でない値には `std::atoi` を適用し、結果を `std::max(1, ...)` で 1 以上にする。未設定または空文字は 9。文字列全体の妥当性検査はなく、`atoi` が読む先頭の十進整数部分だけが使われる。したがって空白と符号は整数の前に許容され、整数の後ろの文字は無視され、数字として読めない文字列は `atoi` の 0 から 1 に丸められる。上限 clamp はない（`engine/src/kernels/cuda/native_mmvq.cu:3767-3772`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・境界 |
|---|---|---|---|
| `native_mmvq` の判定 | 既定 9 | 正の整数部分が下限になる。例: `2`, ` 10tail` → 2, 10 | 空文字 → 既定 9。`0`, `-4`, `junk`, `0anything` → 下限 1。`1tail` → 1。大文字小文字は関係しない。 |

下限は `ncols >= min_t` として比較されます。値が 1 でも `ncols` は別途 1～16 の範囲でなければ dense MMVQ 呼び出しの条件を通りません。コメントには既定値 3 とありますが、実装の fallback は 9 です（`engine/src/kernels/cuda/native_mmvq.cu:3767-3781`）。

## 有効になる条件

- `native_mmvq` が呼ばれ、`n_out >= 1024`、`min_t <= ncols <= 16` であること（`engine/src/kernels/cuda/native_mmvq.cu:3775-3782`）。
- `ggml_type` が Q8_0、Q2_K、Q3_K、Q4_K、Q5_K、Q6_K、IQ3_XXS、IQ4_NL、IQ3_S、IQ4_XS のいずれかであること（`engine/src/kernels/cuda/dense_i8_tc.cu:1705-1710`）。
- `STRATA_DENSE_I8_TC` が無効値でなく、GPU compute capability が 7.5 以上であること。`STRATA_DENSE_I8_TC` は別の関数内 static として読まれ、未設定・空文字は GPU 条件に委ね、非空値は `atoi(value) != 0` で判定する。`0` や数字で始まらない値は無効、`1` や `1tail` は有効になる（`engine/src/kernels/cuda/dense_i8_tc.cu:1701-1719`）。
- dense カーネルの追加条件として、ポインターが null でなく、`n_in > 0`、`n_out > 0`、`1 <= ncols <= 16` であり、`n_in` が型に応じた K alignment（Q8_0 / IQ4_NL は 32、それ以外は 256）の倍数であること（`engine/src/kernels/cuda/dense_i8_tc.cu:1732-1738`）。
- HIP では `current_cc()` が 0 を返すため `dense_i8_tc_supported()` は false となり、この decode 経路は有効にならない。CUDA/HIP 共用ファイル内で同じ下限関数を呼ぶコードがあっても、HIP で dense カーネルが選ばれる条件にはならない（`engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`）。
- CUDA interleaved MMVQ の対応判定では、さらに `1 <= ncols <= 8`、`g_multi_exact` が true、対応 GPU、`g_tune_rows == 0` が必要。dense 経路の条件が成立すると interleaved 対応判定が false となり、通常の `native_mmvq` 呼び出しへ進む。`STRATA_DENSE_I8_TC_MIN_T` は `native_mmvq` 側で再び同じ下限判定に使われる（`engine/src/kernels/cuda/native_mmvq.cu:4218-4234`）。

## 実行時の詳細

下限は最初に `dense_i8_tc_min_t()` が呼ばれた時に一度だけ static に保存され、後からプロセス環境を変更しても更新されない。下限判定を通った後で `dense_i8_tc_decode_enabled()` が別環境変数と GPU 対応を確認し、その後 `dense_i8_tc_mmvq` が shape・ポインター・alignment を検査して kernel を launch する。成功時は dispatch 統計に dense variant `30` を記録して戻る。カーネル関数が false を返すと通常の MMVQ 分岐に続く（`engine/src/kernels/cuda/native_mmvq.cu:3767-3805`; `engine/src/kernels/cuda/dense_i8_tc.cu:1712-1719,1732-1767`）。

この関数から CLI 引数や設定ファイルによる上書きは確認できない。直接の優先条件は `STRATA_DENSE_I8_TC` の無効化、出力行数、列数、量子化型、GPU 対応、入力形状であり、いずれかを満たさなければ既定の native MMVQ 実装に進む（`engine/src/kernels/cuda/native_mmvq.cu:3775-3805`）。

## ログと測定値

この変数の値による専用の stdout / stderr ログやエラー文字列は確認できない。dense 経路が成功した場合、dispatch 統計が有効なら `kDense` の variant `30` と shape が記録される。これは kernel 選択の統計で、専用ログ文言ではない（`engine/src/kernels/cuda/native_mmvq.cu:3782-3784`; `engine/include/strata/core/dispatch_stats.hpp:138-144`）。この調査では性能測定を行っておらず、参照した Strata 資料にもこの下限値に結び付く測定条件は見つからなかった。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:3767-3785` — 値の読取・cache・既定値と dense 経路の選択。
- `engine/src/kernels/cuda/dense_i8_tc.cu:1683-1719,1732-1767` — GPU 対応、量子化型、別の有効化変数、decode kernel の追加条件。
- `engine/src/kernels/cuda/native_mmvq.cu:4218-4234` — interleaved 経路との関係。
- `engine/include/strata/core/dispatch_stats.hpp:138-144` — 成功時に記録される dispatch 統計。
