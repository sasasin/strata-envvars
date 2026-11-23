# `HY4_INT8_MMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 版 Hy4-Flash の線形層 dispatcher で、対象 GEMM に CUDA INT8 Tensor Core 経路を選ぶか、その経路の活性値量子化を 1 項または 2 項にするかを制御する。未設定時は `0` で、通常は FP16 WMMA を使う。非ゼロなら対応する形状・重み形式で INT8 GEMM を選び、値が `2` 以上なら HI（2 項）、それ以外の非ゼロ値なら 1 項を選ぶ。読み取り箇所は `skd::lin_int8_mma()`、選択は `linear_h()` にある（`engine/src/hy4flash/run/skhy4.hip.h:33-43,47-80`）。

対象コードは Hy4-Flash の CUDA ビルド経路である。統合 CMake ビルドでは `STRATA_BUILD_HY4` が既定 OFF で、Hy4 ターゲットを有効にするには CUDA または HIP が必要（`engine/CMakeLists.txt:846-852`）。`HY4_INT8_MMA` の読み取りはプリプロセッサ条件 `HY4_CUDA && HY4_MMA` の中だけにあり、CUDA では `HY4_MMA` は別指定がなければ 1（`engine/src/hy4flash/run/hy4_gpu.h:16-23`）。HIP、Metal、SYCL の経路にはこの読み取りがない。

## 値と判定

関数内 `static int` の初期化時に `getenv` で設定有無を調べ、設定されていれば `atoi` で整数化する。文字列全体の妥当性検査はなく、空文字は設定済みでも `atoi("") == 0` となる。`atoi` は先頭の空白と符号を許し、先頭の整数部分を変換し、数値の後ろは無視する。数値に変換できない文字列は 0 になる。したがって大文字小文字という概念はなく、`true` は有効化値ではない。範囲 clamp や無効値の警告もない（`engine/src/hy4flash/run/skhy4.hip.h:33-38`）。

| 条件（ビルド） | unset | 設定時に INT8 を選ぶ値 | 0 扱いになる例 | 1 項 / 2 項の選択 |
|---|---:|---|---|---|
| `HY4_CUDA && HY4_MMA` | 0 | `atoi` の結果が非ゼロ。例: `1`, `2`, `-1`, `2suffix` | 空文字、`0`, `0anything`, `true`, `abc` | 非ゼロかつ 2 未満は 1 項。2 以上は 2 項 HI |
| それ以外 | 読み取りなし | 該当なし | 該当なし | この変数による選択なし |

この分類は `atoi` の変換結果と後段の `if (lin_int8_mma())` / `lin_int8_mma() >= 2` による（`engine/src/hy4flash/run/skhy4.hip.h:35-37,62,73`）。`atoi` が `int` で表せない入力を受けた場合の結果はこのコードで検査されず、値域として保証できない。

## 有効になる条件

- Hy4-Flash の CUDA ビルドで `HY4_CUDA && HY4_MMA` が成立すること。CUDA 側では `HY4_MMA` は既定 1 だが、ビルド時に上書き可能（`engine/src/hy4flash/run/hy4_gpu.h:16-23`）。
- 対象の重み形式が `FMT_Q8ROW` ではないこと。`FMT_Q8ROW` は dispatcher の先頭で常に参照カーネルへ送られ、環境変数を参照しない（`engine/src/hy4flash/run/skhy4.hip.h:47-48`）。
- 入力行数 `M` が GEMV 経路を通らないこと。CUDA + MMA の `lin_gemv_max_m()` は 4 を返すため、`M <= 4` は GEMV 分岐となり、この変数による INT8 GEMM 選択に進まない（`engine/src/hy4flash/run/skhy4.hip.h:28-31,47-60`）。
- INT8 GEMM を実際に起動するには、`K >= 256` かつ `K` が 256 の倍数で、形式が `S2`〜`S6` または `S8` であること。そうでない場合、INT8 GEMM 関数内で参照実装、FP16 small GEMM、または FP16 GEMM に fallback する（`engine/src/hy4flash/run/sk_int8_cuda.hip.h:574-590`）。
- `M` が 5〜16 の場合、非ゼロ設定は `linear_h_gemm_i8()` を選ぶ。`M > 16` では非ゼロ設定が cuBLAS の試行を飛ばして INT8 関数へ進む。0 の場合は `HY4_CUBLAS_MIN_M`（既定 32）以上なら cuBLAS を先に試し、成功しなければ FP16 GEMM に進む。cuBLAS 自体は `HY4_CUBLAS_PF`（既定 1）や GPU・VRAM 等の条件にも依存する（`engine/src/hy4flash/run/skhy4.hip.h:59-80`; `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-21,37-59`; `engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90`）。
- `HY4_DP4A` は `M <= 4` の GEMV 経路に関係する別変数で、この経路が選ばれた場合は `HY4_INT8_MMA` による GEMM 選択は行われない（`engine/src/hy4flash/run/skhy4.hip.h:39-43,49-54`）。

CLI 引数や設定ファイルによる `HY4_INT8_MMA` の上書きは、この読み取り・dispatch 経路にはない。サーバー専用条件もなく、同じ `linear_h()` を使う呼び出しで適用される。呼び出し例として、runner の線形層、Engram の投影、lm head、DFly2 の logits 計算がこの dispatcher を利用する（`engine/src/hy4flash/run/hy4_graph.hip.h:1332-1347,1944-1956,3455-3465`; `engine/src/hy4flash/run/hy4_dfly2.hip.h:688-712`）。

## 実行時の詳細

最初に `lin_int8_mma()` が呼ばれた時点で、関数内 static 値を初期化する。以後はその整数値がプロセス内でキャッシュされるため、初回評価後に環境を変更しても再読込されない。CLI やリクエストごとの再評価はない（`engine/src/hy4flash/run/skhy4.hip.h:35-37`）。

`linear_h()` はまず Q8ROW を参照経路へ分岐し、その後 `M <= 4` を GEMV 経路として処理する。残る `M <= 16` では非ゼロなら INT8 small GEMM、0 なら FP16 small GEMM を選ぶ。`M > 16` では非ゼロなら INT8 GEMM を選び、0 なら条件を満たす cuBLAS が成功した場合にそれを使い、そうでなければ FP16 GEMM に進む。INT8 関数内では `K < 256` または `K % 256 != 0` の場合に参照実装へ戻り、対応外の形式も FP16 関数へ戻る。従って、非ゼロは INT8 実行を無条件には保証しない（`engine/src/hy4flash/run/skhy4.hip.h:47-80`; `engine/src/hy4flash/run/sk_int8_cuda.hip.h:574-590`）。

## ログと測定値

この変数の値や INT8 / FP16 dispatch 選択を直接表示するログは、読み取り箇所と dispatcher にない。cuBLAS 経路を試す場合には cuBLAS 状態初期化が成功すると別機能の有効ログを出し、UMA GPU や VRAM 不足時には cuBLAS 側の理由ログを出すが、これは `HY4_INT8_MMA` のログではない（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:48-59,84-90`）。この変数について条件付き測定値を示す Strata 資料は確認できなかった。

## 根拠

- 読み取り・整数化・既定値・cache と CUDA/MMA 条件: `engine/src/hy4flash/run/skhy4.hip.h:33-44`; `engine/src/hy4flash/run/hy4_gpu.h:16-23,324-352`。
- dispatcher と行数条件、cuBLAS との分岐: `engine/src/hy4flash/run/skhy4.hip.h:28-83`; cuBLAS の条件・fallback: `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-21,37-59`; `engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90`。
- INT8 kernel の K 境界、対象形式、fallback: `engine/src/hy4flash/run/sk_int8_cuda.hip.h:574-590`。
- build target 条件: `engine/CMakeLists.txt:846-852,884-893`。
- production 呼び出し経路: `engine/src/hy4flash/run/hy4_graph.hip.h:1332-1347,1944-1956,3455-3465`; `engine/src/hy4flash/run/hy4_dfly2.hip.h:688-712`。
