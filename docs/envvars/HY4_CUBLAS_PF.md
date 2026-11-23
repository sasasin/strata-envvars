# `HY4_CUBLAS_PF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4 CUDA 経路の cuBLAS prefill 用 side-stream 経路を有効にする整数スイッチ。正の値で共有 `CublasPfState` の初期化を許可し、S_K 重みを FP16 に dequantize して cuBLAS GEMM を使う候補経路を利用可能にする。未設定時は整数既定値が `1` だが、統合型 UMA GPU では別の presence 判定により自動停止する。値が `0` 以下なら state 初期化を断る。実装は `engine/src/hy4flash/run/sk_cublas_ctx.hip.h` の `cublas_pf_mode()` / `CublasPfState::ensure()`（15-18、37-54 行）。

これは処理経路の候補を許可するスイッチであり、すべての演算を cuBLAS に切り替えるものではない。Hy4 の CUDA ビルドで、線形層は `M >= HY4_CUBLAS_MIN_M`、`HY4_INT8_MMA` が無効（0）である経路、対応 format / K 幅、state 初期化成功などを満たすときだけ cuBLAS を試し、使えない場合は既存 GEMM 経路へ進む（`engine/src/hy4flash/run/skhy4.hip.h:70-80`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-56`）。

## 値と判定

`getenv("HY4_CUBLAS_PF")` で設定有無を見て、設定時は `atoi` の戻り値を使う。文字列全体の妥当性検査、範囲検査、大文字小文字変換はない。`atoi` が先頭の空白と符号付き数字を読めるため、たとえば `"  +2tail"` は `2`、`"0anything"`・空文字・`"true"` は `0` として無効になる。負値はすべて無効、正の整数は有効。数値として読めない先頭の場合も `0`。整数範囲外の文字列の結果はこのコードで検証・規定していない。unset と空文字は異なり、UMA 判定でも設定の有無が別途使われる（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-17, 38, 51-54`）。

| ビルド / GPU 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `HY4_CUDA` の Hy4 CUDA 経路、非 UMA GPU | `cublas_pf_mode()` は `1`。メモリ等の初期化条件を満たせば有効 | `atoi` 結果が `> 0`（例: `1`, `2`, `1tail`） | `atoi` 結果が `<= 0`（例: `0`, `-1`, `0anything`, `true`, 空文字） |
| `HY4_CUDA` の Hy4 CUDA 経路、統合型 UMA GPU | mode の既定値は `1` だが presence 判定で自動停止 | `atoi` 結果が `> 0`。明示設定があれば UMA 自動停止を通過 | `atoi` 結果が `<= 0`。空文字もこれに該当 |

## 有効になる条件

- `sk_cublas_ctx.hip.h` の実装は `#if HY4_CUDA` 内にある。Hy4 CUDA 経路が対象で、HIP 専用経路ではこの実装はコンパイルされない（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:4-7, 107`、`engine/src/hy4flash/run/hy4_gpu.h:17-24`）。
- `ensure()` が `cublas_pf_mode() <= 0` と判定すると即座に `false` を返す。正値でも、現在 device の取得失敗、stream capture 中、cuBLAS handle・scratch・stream/event の作成失敗などで初期化に失敗すれば利用できない（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:37-79`）。
- 統合型 GPU（`cudaDeviceProp.integrated != 0`）では、変数が未設定の場合に自動停止する。空文字を含め何か設定されていれば、この自動停止条件は通過するが、値が `atoi` で `0` 以下なら先行する mode 判定で停止する（同 `:38-39, 49-54`）。
- 非 UMA GPU では空き VRAM に応じて scratch を 64 MiB から 32 MiB に縮小し、それでも不足なら停止する。scratch 要求量は別変数 `HY4_CUBLAS_SCRATCH_MB` にも左右される（同 `:55-59`）。
- 線形層の経路では `HY4_CUBLAS_MIN_M` の閾値以上かつ `HY4_INT8_MMA`（`lin_int8_mma()`）が無効であることが cuBLAS 呼び出しの条件。`HY4_INT8_MMA` は未設定時 `0` で、非ゼロなら cuBLAS 候補より int8 MMA 経路を優先する（`engine/src/hy4flash/run/skhy4.hip.h:33-38, 70-73`）。形式が `FMT_Q8ROW` または K が 256 の倍数でない場合も候補関数は `false` を返す。失敗時は呼び出し側の GEMM 経路へフォールバックする（同 `:70-80`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-56`）。
- MLA の Q 準備 / V 出力も同じ state を共有するが、それぞれ `HY4_CUBLAS_MLA`、`HY4_CUBLAS_MIN_M`、`g_mla_force_simple` の条件が別にある。したがって `HY4_CUBLAS_PF` が正でも MLA 経路の採用は保証しない（`engine/src/hy4flash/run/mla_attn.hip.cpp:2164-2172, 2256-2266`）。
- 起動時設定、サーバーモード、CLI 引数による上書きは、この変数の読み取り実装にはない。プロセスへ値を渡す別の Strata コード経路も候補名の全参照検索では見つからなかった。

## 実行時の詳細

`cublas_pf_mode()` の関数内 `static` 値は初回呼び出し時に一度だけ初期化される。`CublasPfState` も関数内 static の共有 singleton。CUDA graph の初期化処理から `ensure(st)` が呼ばれるほか、線形層と MLA の候補経路からも `ensure()` に到達する（`engine/src/hy4flash/run/hy4_graph.hip.h:1707-1711`、`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-17, 100-103`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-53`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2105, 2130-2138`）。最初の `cublas_pf_mode()` 評価後にプロセス環境を変えても mode static には反映されない。一方 UMA の追加判定は `ensure()` のたびに `getenv` し直す。

UMA 未設定時および mode が `<= 0` の場合は `tried` を立てずに戻るため、後続の候補呼び出しでも同じ判定を行う。初期化を試す場合、device ごとの初回失敗後は `tried` / `dev` / `ok` が使われ、同じ device では成功状態を返し、別 device は primary GPU only として拒否する（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:37-45`）。

有効時は共有 scratch、cuBLAS handle、side stream、ready/free event を用意し、線形層の処理では side stream 上の dequant と cuBLAS GEMM を交互に進める。state の初期化または個別 GEMM が失敗すると候補関数は `false` を返し、呼び出し側は通常経路を続ける（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:61-91`、`engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90`、`engine/src/hy4flash/run/skhy4.hip.h:70-80`）。

## ログと測定値

- UMA GPU で未設定なら stderr に `[cublas-pf] auto-disabled on integrated UMA GPU (fused skwmma avoids LPDDR5X round-trip; set HY4_CUBLAS_PF=1 to override)` を出す（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:51-53`）。`tried` を立てる前の return のため、後続の `ensure()` 呼び出しごとに再度出る可能性がある。
- 非 UMA GPU で VRAM が不足すると stderr に `[cublas-pf] disabled: low free VRAM (%.0f MiB)` を出す（同 `:56-59`）。
- 初期化成功時は stderr に `[cublas-pf] side-stream double-buffered dequant + cuBLAS enabled (2 x %.0f MiB scratch, M >= %d)` を出す（同 `:83-90`）。
- cuBLAS handle / scratch / stream / event の作成失敗など、ほかの初期化失敗にはこのコードから専用のエラー文言や終了処理はなく、呼び出し元の fallback に進む。Strata の `docs/DETAILS.md` にこの変数の条件付き性能測定値は見つからないため、速度・精度の測定値は記載しない。

## 根拠

- `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-17, 37-59, 61-91, 100-107` — 値の読み取り、UMA / VRAM 条件、初期化、ログ、共有 state。
- `engine/src/hy4flash/run/sk_cublas_cuda.hip.h:49-90` — 線形層の候補処理と失敗時の戻り値。
- `engine/src/hy4flash/run/skhy4.hip.h:70-80` — `M`・int8 条件と線形 GEMM の fallback。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1707-1711` — graph 初期化時の `ensure()` 呼び出し。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:2164-2172, 2256-2266` — MLA 側の追加条件。
