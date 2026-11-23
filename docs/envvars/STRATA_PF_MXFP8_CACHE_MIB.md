# `STRATA_PF_MXFP8_CACHE_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、Blackwell 向け cuBLASLt MXFP8 dense prefill が、変換済み重み（FP8 本体と scale-factor）のキャッシュに使う GPU メモリ slab の上限を MiB 単位で指定する。`State::init` は既定で 3072 MiB を予算とし、GPU の空き容量から 4 GiB を残した範囲でその予算まで一括確保する。確保した slab に重みを保持できれば、同じ重みの次回利用時に再変換を避ける。これは MXFP8 経路そのものを有効化するスイッチではなく、生成結果や演算選択の設定でもない（`engine/src/prefill/gemm_mxfp8.cuh:234-243, 286-305, 350-369, 464-482`）。

## 値と判定

`State::init` の最初の実行時に `std::getenv` で読み、未設定または空文字なら 3072 MiB を使う。空でない文字列は `std::atoll` で整数変換し、その値に `1ll << 20` を掛けてバイト数にする。文字列全体の妥当性検査、範囲検査、clamp はない。したがって、先頭の数値部分を変換し、数値の後ろの文字は `atoll` によって無視される（例: `1abc` は 1 MiB、`0anything` は 0 MiB）。数値として始まらない文字列は変換値 0 となる。先頭空白や符号は `atoll` の変換規則に従い、正の予算になった場合だけ slab 確保を試みる。負数および 0 は slab 確保を無効にする。MiB への乗算について個別のオーバーフロー処理はない（同 `:286-305`）。

| 条件 | unset | 有効になる値 | slab を無効にする値 |
|---|---|---|---|
| CUDA cuBLASLt MXFP8 を含む build | 3072 MiB | `1`、`4096` など正数に変換される値 | 空文字は既定値。`0`、`-1`、`abc`、`true`、`false`、`0anything` など 0 以下に変換される値 |
| HIP build、または MXFP8 compile definition がない build | このコードは変数を読まない | 該当なし | 該当なし |

正の予算でも、その値がそのまま確保量になるとは限らない。確保量は `min(予算, 空き VRAM - 4 GiB)` で、空き VRAM が 4 GiB + 256 MiB 以下、空き容量取得失敗、または `cudaMalloc` 失敗の場合は slab を確保しない（同 `:292-303`）。

## 有効になる条件

- build が HIP ではなく、CUDA build で `CUDA::cublasLt` が見つかり、CUDA compiler が 12.8 以上であること。このとき `STRATA_CUBLASLT_MXFP8` が定義される（`engine/cmake/backends/cuda.cmake:84-88`）。
- MXFP8 経路の別スイッチ `STRATA_PF_MXFP8` が空でなく、`atoi` の結果が 0 以外であり、実行 GPU の compute capability major が 12 以上であること（`engine/src/prefill/gemm_mxfp8.cuh:498-517`）。
- dense GEMM 呼び出し側の形状・stride 条件を満たすこと。BF16 経路では `ldx` が 0 または `K`、`T/N/K >= 128`、`N` は 16 の倍数、`K` は 32 の倍数が必要（`engine/src/prefill/gemm.cu:1274-1277`）。量子化重み経路も同様の条件に加え `N*K <= scratch_elems_` が必要（同 `:1545-1548`）。
- `State::run_16` の条件として、未キャッシュ重みは既定 `STRATA_PF_MXFP8_MIN_T` 閾値 4096 token 以上、キャッシュ hit は 512 以上であること。さらに `N >= 1024`、`K >= 256`、出力 stride の 4 要素整列なども必要。これらを満たさず MXFP8 実行が false を返す場合、呼び出し元は通常の GEMM 経路へ進む（`engine/src/prefill/gemm_mxfp8.cuh:436-451`; `engine/src/prefill/gemm.cu:1282-1299, 1570-1585`）。
- slab がない、予算を使い切った、または重みキーが null の場合は、slab cache への追加をせず `w_fp8` / `w_sf` の再利用バッファを確保して変換を続ける。このため、容量設定による slab 不在だけで MXFP8 GEMM が無効になるわけではない（`engine/src/prefill/gemm_mxfp8.cuh:361-369, 464-482`）。

## 実行時の詳細

変数を読むのは、MXFP8 経路に入った `Gemm` の `State::init` 内で `slab_tried` が false のときの一度だけである。読み取りと slab 確保を試みた後は `slab_tried` が true となり、その `State` の存続中に環境変数を変更しても読み直さない。状態は MXFP8 経路の初回到達時に作られ、`Gemm` の破棄時に削除される（`engine/src/prefill/gemm_mxfp8.cuh:234-243, 286-306`; `engine/src/prefill/gemm.cu:1277-1284, 1548-1572, 763-765`）。

正数から得た予算がある場合でも、空き容量の確認と slab 確保は初期化時に一度試す。いずれかに失敗すればこの箇所ではエラーを返さず、以後の重み変換は個別の再利用バッファへフォールバックする。slab の空きが不足した重みも同じフォールバックとなり、その重みは slab の `wcache` に登録されない。slab 内に登録できた重みは source pointer・型・N・K の一致で検索される（同 `:292-305, 350-369, 464-482`）。

## ログと測定値

最初の MXFP8 GEMM が成功したときだけ stderr に `strata prefill: Blackwell cuBLASLt MXFP8 (VEC32_UE8M0) dense GEMM active (slab %zu MiB, STRATA_PF_MXFP8=0 disables)` が一度出る。`slab` は実際に確保された容量 MiB なので、確保なしの場合は `0 MiB` と表示される。初期化中の空き容量取得失敗や slab 確保失敗について、このコードは `cudaGetLastError()` を消費するだけで専用警告を出さない。測定値を記載した Strata 資料は確認できなかった（`engine/src/prefill/gemm_mxfp8.cuh:292-303, 485-493`）。

## 根拠

- 候補名の唯一の実行時読み取り、既定値、MiB 変換、空き VRAM 条件と確保: `engine/src/prefill/gemm_mxfp8.cuh:286-305`
- slab の使用・容量不足時の再利用バッファ経路と重み cache: `engine/src/prefill/gemm_mxfp8.cuh:350-369, 464-482`
- MXFP8 の opt-in・GPU 世代判定と run gate: `engine/src/prefill/gemm_mxfp8.cuh:436-451, 498-517`
- CUDA build macro の条件: `engine/cmake/backends/cuda.cmake:84-88`
- 呼び出し条件、通常 GEMM への fallback、状態の生成・破棄: `engine/src/prefill/gemm.cu:763-765, 1274-1299, 1545-1585`
