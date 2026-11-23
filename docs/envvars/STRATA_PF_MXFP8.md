# `STRATA_PF_MXFP8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の dense prefill GEMM で、Blackwell cuBLASLt MXFP8（E4M3 + VEC32 UE8M0 scale）経路を opt-in で有効にする。成功すると BF16/FP16 入力と重みを MXFP8 に量子化して GEMM し、prompt 出力のうち 16-token 単位に切り下げた部分を処理する。残りの token は通常の BF16 経路へ渡す。無効、条件不一致、初期化・量子化・GEMM の失敗時は呼び出し元の通常経路へ進む。実装は `strata::prefill::mxfp8::enabled()` と `State::run_16()` にある（`engine/src/prefill/gemm_mxfp8.cuh:436-494,498-518`、呼び出し元 `engine/src/prefill/gemm.cu:1274-1299,1545-1585`）。

## 値と判定

`enabled()` は `std::getenv` で値を取得し、関数内 `static` に一度だけ `std::atoi(v) != 0` の結果を保存する。未設定または空文字は無効。`atoi` は文字列全体の厳密な数値検証をしないため、先頭の空白・符号の後の数値部分を変換し、数値以降の文字は判定に含めない。したがって `1`、`-1`、`+1x`、` 1` は有効、`0`、`0anything`、`true`、`false`、`x1`、空文字は無効になる。値の範囲検証や clamp はない（`engine/src/prefill/gemm_mxfp8.cuh:498-504`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA、`STRATA_CUBLASLT_MXFP8` 定義、GPU compute capability major >= 12 | 無効 | `1`、`-1`、`1suffix` | 空文字、`0`、`0suffix`、`true` |
| HIP、または `STRATA_CUBLASLT_MXFP8` 未定義 | この実装はコンパイル対象外 | 該当なし | 該当なし |

## 有効になる条件

- `engine/cmake/backends/cuda.cmake:86` で定義される `STRATA_CUBLASLT_MXFP8` を含む CUDA ビルドであること。ソースは `!__HIPCC__` とこの macro の両方で guard されている（`engine/src/prefill/gemm.cu:1274,1545`、`engine/src/prefill/gemm_mxfp8.cuh:12`）。
- `enabled()` が対象 device を取得でき、compute capability major が 12 以上であること。minor はこの判定では限定されない。device 判定は device index ごとに cache される（`engine/src/prefill/gemm_mxfp8.cuh:505-517`）。
- 呼び出し元で `ldx == 0 || ldx == K`、`T >= 128`、`N >= 128`、`K >= 128`、`N % 16 == 0`、`K % 32 == 0` を満たすこと（`engine/src/prefill/gemm.cu:1274-1276,1545-1547`）。
- `State::run_16()` ではさらに `N >= 1024`、`K >= 256`、`T_al = T` の 16-token 切り下げ値が 256 以上、`ldy` から決まる leading dimension が 4 の倍数であることが必要。重み cache miss なら `T >= STRATA_PF_MXFP8_MIN_T`（未設定・空文字時 4096）、cache hit なら `T >= 512` が必要（`engine/src/prefill/gemm_mxfp8.cuh:439-451`）。
- BF16 native GEMM では `N * K <= scratch_elems_` も必要。超える場合は MXFP8 分岐を通らない（`engine/src/prefill/gemm.cu:1545-1548`）。
- 先行する BF16 の FP16/FP32 変換経路が処理を完了すると、その経路が先に return し MXFP8 判定に到達しない（`engine/src/prefill/gemm.cu:1195-1257`）。
- `STRATA_PF_MXFP8_CACHE_MIB` は `State::init()` 時の重み slab 予算に関係するが、主変数の有効判定を上書きしない。slab なしでも個別 buffer による処理を試みる（`engine/src/prefill/gemm_mxfp8.cuh:286-305,464-482`）。
- CLI 引数による上書きはこの実装箇所では確認できない。検索した Strata 所有ソースに、この変数を渡す動的 env helper や別の直接読み取り箇所はなかった。

## 実行時の詳細

主変数の判定は `enabled()` の初回呼び出し時に評価して process 内で cache される。実行中に環境を変更しても判定は変わらない。device capability も index ごとに初回判定結果を cache する（`engine/src/prefill/gemm_mxfp8.cuh:498-517`）。`STRATA_PF_MXFP8_MIN_T` は `run_16()` の初回評価時に `static` へ保存され、未設定・空文字なら 4096。値は `atoll` で変換され、値域の clamp や文字列全体の検証はない。cache hit 時はこの値に代えて 512-token gate を使う（`engine/src/prefill/gemm_mxfp8.cuh:439-447`）。

BF16 native GEMM と GGUF block weight の経路がそれぞれ MXFP8 を試す。block weight の変換では Q8_0/Q6_K を直接変換し、それ以外は通常 dequantize を試す。重み cache miss で変換・allocation に失敗した場合、または MXFP8 matmul が使えない場合は `run_16()` が false を返し、呼び出し元の既存 GEMM 経路へ fall through する。成功時は `T_al = T & ~15` の範囲を MXFP8 で計算し、残りがあれば通常経路で処理する（`engine/src/prefill/gemm_mxfp8.cuh:464-487`、`engine/src/prefill/gemm.cu:1282-1299,1570-1585`）。

## ログと測定値

初回成功時に stderr へ次のログを一度出す。`logged` は `State` ごとのフラグ。

```text
strata prefill: Blackwell cuBLASLt MXFP8 (VEC32_UE8M0) dense GEMM active (slab %zu MiB, STRATA_PF_MXFP8=0 disables)
```

この変数が無効、条件不一致、または MXFP8 経路が失敗したときに、主変数固有の理由ログは出さない。`docs/DETAILS.md` にこの経路の測定値を確認できなかったため、速度・精度の測定値は記載しない（ログ位置 `engine/src/prefill/gemm_mxfp8.cuh:488-493`）。

## 根拠

- `engine/src/prefill/gemm_mxfp8.cuh:436-494,498-518` — 閾値、処理成功条件、ログ、環境変数判定と device 判定。
- `engine/src/prefill/gemm.cu:1195-1257,1274-1299,1545-1585` — CUDA dense GEMM の呼び出し条件、優先される経路、失敗後の fallthrough。
- `engine/cmake/backends/cuda.cmake:86` — CUDA backend の build macro 定義。
- `engine/src/prefill/gemm_mxfp8.cuh:267-305,464-482` — state 初期化、補助 cache 予算、重み変換と cache。
- `docs/SETTINGS.md:218-221` — 設定一覧の分類。ここでは `STRATA_PF_MXFP8` を NVIDIA and AMD と記載するが、上記実装は `!__HIPCC__` と CUDA build macro に限定されるため、資料の分類とソース実装に差がある。
