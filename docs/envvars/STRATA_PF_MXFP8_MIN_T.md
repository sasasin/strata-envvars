# `STRATA_PF_MXFP8_MIN_T`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、CUDA cuBLASLt MXFP8 dense prefill が重みを初めて MXFP8 化する場合に必要な最小 token 行数 `T` を指定します。未設定時は 4096 です。重みが MXFP8 キャッシュに見つかった場合は、この値に関係なく 512 以上で経路を試します。経路自体は `STRATA_PF_MXFP8` の opt-in が必要です。読み取りと判定は `engine/src/prefill/gemm_mxfp8.cuh` の `State::run_16` にあります（439-447 行）。

## 値と判定

`run_16` の初回呼び出し時に `std::getenv` で読み、未設定または空文字なら 4096、その他は `std::atoll` の結果を閾値にします（440-443 行）。完全な文字列検証や範囲チェックはありません。`atoll` は先頭の空白と符号を受け付け、先頭の整数部分を読み、後続の非数値文字を判定材料にしません。数値部分がない文字列は 0 になります。したがって `0anything` や `true` は 0、`12tail` は 12、`-1` は -1 として扱われます。オーバーフロー入力の結果はこのコードで検査・規定していません。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 重みキャッシュ未ヒット | 4096 | `T >= atoll(value)`。例: `4096`, `+4096`, `12tail` | `T < atoll(value)`。例: 既定閾値に対する `4095`; `0anything` は閾値 0 となり正の `T` で閾値判定を通る |
| 重みキャッシュヒット | 固定 512（変数値を参照しない） | `T >= 512` | `T < 512` |

空文字は未設定と同じ 4096 です。負数や 0 による下限クランプはありません。閾値判定を通っても、後述の他の形状条件や実行時処理が失敗すれば MXFP8 GEMM は成立しません（`gemm_mxfp8.cuh:447-451`）。

## 有効になる条件

- `STRATA_PF_MXFP8` が空でなく、`atoi` の結果が 0 以外である必要があります。未設定・空文字・`0`・`0tail` は無効です（`engine/src/prefill/gemm_mxfp8.cuh:498-504`）。
- CUDA 非 HIP build で `STRATA_CUBLASLT_MXFP8` が定義されている必要があります。CUDA backend の CMake は cuBLASLt target があり、CUDA compiler が 12.8 以上の場合にこの macro を定義します（`engine/cmake/backends/cuda.cmake:83-88`）。HIP build では関連箇所が `!defined(__HIPCC__)` により除外されます（`engine/src/prefill/gemm.cu:1274-1276,1545-1547`）。
- 実行 GPU の compute capability major が 12 以上で、`cudaGetDevice` と属性取得が成功する必要があります。デバイス判定結果は device ごとに `dev_ok[64]` に保存されます（`engine/src/prefill/gemm_mxfp8.cuh:504-517`）。
- 呼び出し側では `ldx == 0` または `ldx == K`、`T >= 128`、`N >= 128`、`K >= 128`、`N` が 16 の倍数、`K` が 32 の倍数である必要があります。量子化 weight の経路ではさらに `N * K <= scratch_elems_` が必要です（`engine/src/prefill/gemm.cu:1274-1276,1545-1547`）。
- `run_16` 内では上記に加えて状態が失敗状態でないこと、`N >= 1024`、`K >= 256`、`N` が 16 の倍数、`K` が 32 の倍数、`T` がキャッシュ未ヒット時の変数閾値またはキャッシュヒット時の 512 以上であることが必要です。また、16 行単位に切り下げた `T_al` が 256 未満でも不採用になります（`engine/src/prefill/gemm_mxfp8.cuh:446-451`）。
- BF16 dense 重みでは `Gemm::bf16` から、量子化重みでは `Gemm::native` から呼ばれます。CLI 引数や他の環境変数による `MIN_T` の上書きはこの読み取り箇所にはありません（`engine/src/prefill/gemm.cu:1274-1284,1545-1572`）。

索引 `docs/SETTINGS.md:220` は対応対象を「NVIDIA and AMD」としていますが、現行実装は HIP build ではコンパイル対象外で、CUDA のみです。このプラットフォーム表記はソース上の適用条件と一致しません。

## 実行時の詳細

`run_16` の関数ローカル `static const min_t` 初期化で値を読みます。したがってプロセス内で最初に同関数へ到達した時点の値が以後の呼び出しにも使われ、プロセス起動後の環境変更は反映されません（`engine/src/prefill/gemm_mxfp8.cuh:439-443`）。一方、重みのキャッシュ有無は `find_cached` で呼び出しごとに確認され、未ヒットなら変換してキャッシュできた場合に登録されます（同:446,464-483）。

しきい値や形状条件で `run_16` が false を返した場合、呼び出し元は MXFP8 成功として return せず、通常の BF16/GEMM 経路へ続きます。MXFP8 が成功した場合は `T` の 16 行境界まで処理し、端数行があれば BF16 または native 経路で残りを処理します（`engine/src/prefill/gemm.cu:1282-1298,1570-1585`）。この環境変数は経路の適用閾値を変えますが、成功時に使う MXFP8 の形式自体を選択するものではありません。

## ログと測定値

成功すると各 `State` で初回に限り stderr へ `strata prefill: Blackwell cuBLASLt MXFP8 (VEC32_UE8M0) dense GEMM active (slab %zu MiB, STRATA_PF_MXFP8=0 disables)` を出します（`engine/src/prefill/gemm_mxfp8.cuh:488-493`）。この環境変数の未設定、閾値未達、または通常経路への fallback を理由とする専用ログは、この実装にはありません。対象 commit の `docs/DETAILS.md` にこの変数の挙動や測定値の記載はありません。

## 根拠

- `engine/src/prefill/gemm_mxfp8.cuh:439-451` — 値の読み取り、既定値、cache hit/未 hit の閾値、形状 gate。
- `engine/src/prefill/gemm_mxfp8.cuh:464-493` — 重み変換・cache 登録、計算、成功ログ。
- `engine/src/prefill/gemm_mxfp8.cuh:498-517` — opt-in と CUDA device capability 判定。
- `engine/src/prefill/gemm.cu:1274-1299,1545-1585` — BF16/量子化重み側の呼び出し条件と通常経路への fallback。
- `engine/cmake/backends/cuda.cmake:83-88` — CUDA 12.8 以上かつ cuBLASLt target がある場合の compile macro。
- `docs/SETTINGS.md:220` — 索引のプラットフォーム分類（実装条件と不一致）。
