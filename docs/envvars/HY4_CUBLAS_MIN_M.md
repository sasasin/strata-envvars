# `HY4_CUBLAS_MIN_M`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 版 Hy4-Flash の行列処理で cuBLAS 経路を選ぶ最小の `M` を指定する。対象は量子化線形層の `linear_h_cublas`、MLA の query 前処理 `mla_prep_q_cublas`、MLA の value up-projection `mla_vup_cublas` で、いずれも呼び出し側で `M >= cublas_pf_min_m()` を判定する。閾値未満、または cuBLAS 経路が使えない場合はそれぞれの既存 GPU カーネルへ進む。この変数自体は cuBLAS 機能全体の有効化スイッチではない。(`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:19-22`, `engine/src/hy4flash/run/skhy4.hip.h:47-80`, `engine/src/hy4flash/run/mla_attn.hip.cpp:2169-2175,2256-2273`)

## 値と判定

`cublas_pf_min_m()` の関数内 `static int` 初期化で `getenv` を調べ、未設定なら `32`、設定されていれば `atoi` の結果を使う。空文字も設定済みとして `atoi("")` の結果 `0` になる。`atoi` は整数全体の厳密な検証をせず、先頭の空白と符号の後の数字列を変換し、数字以降の文字は無視する。数字で始まらない文字列も `0` になる。値を clamp する処理はない。(`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:19-22`)

| 条件 | unset | 有効になる値の例 | しきい値・選択上無効になる値の例 |
|---|---|---|---|
| CUDA 版 Hy4-Flash | 既定値 `32` | `32` は `M >= 32`、`64tail` は `64` と解釈され `M >= 64` | 設定値 `32` なら `M=31` は不選択（`M=32` から選択）。`0`、空文字、`0anything`、`true` は `0` となり非負の `M` なら閾値判定を通る。`-1` は負の閾値となり通常の正の `M` は通る |
| HIP、Metal、SYCL など CUDA 以外 | この変数を読むコードなし | 該当なし | 該当なし |

`atoi` が `int` で表せない値を受け取った場合の結果は C ライブラリ仕様上保証されないため、利用可能な値として扱えない。大文字小文字は数値変換に関係せず、先頭の空白と符号は許容される。CLI 引数や設定ファイルからこの閾値を上書きする読み取りは見つからなかった。(`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:19-22`)

## 有効になる条件

- `STRATA_BUILD_HY4` と `STRATA_ENABLE_CUDA` を使って `strata-hy4` を CUDA 言語でビルドすること。対象ヘッダーおよび呼び出し箇所は `HY4_CUDA` 条件内にあり、CMake の HIP 側では GPU ソースを HIP 言語として扱う。HIP、Metal、SYCL の同名環境変数参照はない。(`engine/CMakeLists.txt:846-852,884-907`, `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:6-7`, `engine/src/hy4flash/run/skhy4.hip.h:71-79`, `engine/src/hy4flash/run/mla_attn.hip.cpp:2169-2172`)
- 線形層の cuBLAS 経路では `M` が閾値以上で、`lin_int8_mma()` が無効であること。さらに `FMT_Q8ROW` ではなく、`K` が 256 の倍数であり、`CublasPfState::ensure` とバッファ・cuBLAS 呼び出しが成功する必要がある。条件を満たさなければ線形 GEMM 等の既存経路へ進む。(`engine/src/hy4flash/run/skhy4.hip.h:70-79`, `engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-56,74-90`)
- MLA query 前処理では `g_mla_force_simple` が偽で、`HY4_CUBLAS_MLA` が `2` 以上、`M` が閾値以上であること。value up-projection では `g_mla_force_simple` が偽で、同変数が `1` 以上、`M` が閾値以上であること。各 cuBLAS 関数の失敗や scratch から 32 行以上を処理できない場合はカーネル経路へ戻る。(`engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2105,2130-2138,2164-2175,2256-2273`)
- `CublasPfState::ensure` は `HY4_CUBLAS_PF` の数値が正であることを要求する。未設定時の既定値は `1` だが、統合 UMA GPU では同変数が未設定なら自動で無効化される。空文字や `0` も `atoi` 後に無効となる。GPU/stream 状態、空き VRAM、ハンドル・scratch・stream/event の初期化も cuBLAS 利用可否に影響する。(`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-17,37-79`)

## 実行時の詳細

値は環境から取得した文字列を `cublas_pf_min_m()` の関数内 `static` に一度だけ保存する。呼び出しスレッドの初回評価後にプロセス環境を書き換えても、この閾値には反映されない。起動時の GPU 初期化から `CublasPfState::ensure` に進み、cuBLAS 初期化に成功すれば有効ログの引数評価で閾値が初期化される。初期化に失敗した場合は、線形または MLA 経路で閾値を初めて参照した時に評価される。(`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:19-22,37-45,81-91`, `engine/src/hy4flash/run/hy4_graph.hip.h:1706-1711`)

線形層では閾値以上なら S_K 重みを FP16 scratch に変換して cuBLAS GEMM を試し、成功時に戻る。失敗時は通常 GEMM 等へ進む。MLA の query と value up-projection も閾値以上で cuBLAS の batched GEMM を試し、失敗時は専用カーネルを使う。したがってこの閾値が直接変えるのは経路選択であり、低い値を設定しただけで cuBLAS 経路の利用が保証されるわけではない。(`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90`, `engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2127,2130-2160,2169-2175,2256-2273`)

## ログと測定値

cuBLAS 初期化に成功すると stderr に `[cublas-pf] side-stream double-buffered dequant + cuBLAS enabled (2 x %.0f MiB scratch, M >= %d)` が出て、採用された閾値が `%d` に表示される。初期化失敗や閾値だけが不一致のときに、この変数専用の警告・エラーを出す処理はない。低空き VRAM の場合は `[cublas-pf] disabled: low free VRAM (%.0f MiB)` が出る場合があるが、これは閾値ではなく初期化条件による。対象変数の条件付き性能測定値は参照資料に見つからなかった。(`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:57-59,89-90`)

## 根拠

- `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:6-22,37-91`
- `engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90`
- `engine/src/hy4flash/run/skhy4.hip.h:47-84`
- `engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2167,2169-2175,2256-2273`
- `engine/src/hy4flash/run/hy4_graph.hip.h:1706-1711`
- `engine/CMakeLists.txt:846-907`
