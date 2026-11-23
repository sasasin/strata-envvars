# `HY4_CUBLAS_MLA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA build の Hy4-Flash MLA 経路で、Q の準備 (`mla_prep_q`) と V up projection (`mla_vup`) に cuBLAS 実装を使うかを整数モードで制御する。既定値 `2` は両方を許可し、`1` は V up だけを許可し、`0` 以下はどちらも許可しない。MLA attention 自体 (`mla_attend`) の実装選択はこの変数では制御しない。cuBLAS 経路を使えない場合は各関数の既存 HIP/CUDA kernel 経路へ進む。`mla_attention` は prefill 経路で attention の後に `mla_vup` を呼び、graph runner は decode (`T <= 8`) では専用の `mla_prep_q_dec` / `mla_vup_dec` を使うため、この変数による選択はその decode helper には適用されない（`engine/src/hy4flash/run/mla_attn.hip.cpp:2164-2175,2256-2274,2328-2332`; `engine/src/hy4flash/run/hy4_graph.hip.h:2108-2120,2166-2179`）。

## 値と判定

`cublas_mla_mode()` は `getenv("HY4_CUBLAS_MLA")` の null 判定後に `atoi` で整数化し、関数内 `static` に保存する。未設定なら `2`。空文字は設定済みなので `atoi("") == 0` となる。`atoi` は文字列全体の妥当性検査をせず、先頭の空白と符号を受け付け、数値に続く文字を無視する。数値に変換できない先頭文字なら `0` となる。範囲外整数の変換結果は C ライブラリ仕様上保証されない。

| 条件 | unset | cuBLAS MLA を許可する値 | 許可しない値の例 |
|---|---:|---|---|
| CUDA build の Q 準備 (`mla_prep_q`) | 既定 `2` | 2 以上。例: `2`, `3`, `2anything` | 1 以下。例: `1`, `0`, `-1`, 空文字, `true`, `0anything` |
| CUDA build の V up (`mla_vup`) | 既定 `2` | 1 以上。例: `1`, `2`, `1anything` | 0 以下。例: `0`, `-1`, 空文字, `true`, `0anything` |
| 非 CUDA build | 既定値に関係なく未参照 | 該当なし | すべて機能に影響しない |

判定は大文字小文字を含む真偽文字列比較ではなく `atoi` である。たとえば `true` は 0、`2tail` は 2、先頭空白付きの ` 2` は 2 として扱われる。`HY4_CUBLAS_MIN_M` は別 helper で既定 32 として `atoi` され、各 cuBLAS 経路に必要な `M` の下限を決める（`engine/src/hy4flash/run/mla_attn.hip.cpp:2164-2166,2170-2175,2256-2260`; `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:19-21`）。

## 有効になる条件

- `HY4_CUDA` が有効な CUDA build であること。`mla_prep_q` の cuBLAS 分岐は `#if HY4_CUDA` 内にあり、`mla_vup` も同じ build guard を持つ。HIP build では該当する分岐がコンパイルされない（`engine/src/hy4flash/run/mla_attn.hip.cpp:2169-2175,2256-2266`; `engine/src/hy4flash/run/hy4_gpu.h:17-23,324-327`）。
- Hy4-Flash の prefill MLA 経路を通ること。graph runner は `T > 8` の場合に `mla_prep_q` を呼び、prefill の MLA projection は `mla_attention` から `mla_vup` を呼ぶ。`T <= 8` の decode では専用 decode helper が使われる（`engine/src/hy4flash/run/hy4_graph.hip.h:2108-2120,2166-2179`; `engine/src/hy4flash/run/mla_attn.hip.cpp:2328-2332`）。
- `mla_prep_q` では mode が `2` 以上、`mla_vup` では `1` 以上で、かつ `M >= skd::cublas_pf_min_m()` が必要。`HY4_CUBLAS_MIN_M` の未設定時は 32（`engine/src/hy4flash/run/mla_attn.hip.cpp:2170-2172,2256-2260`; `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:19-21`）。
- `g_mla_force_simple` が false であること。ソースの初期値は 0 で、同梱 `mla_test` が診断計測中に切り替える（`engine/src/hy4flash/run/mla_attn.hip.cpp:17,2171,2257`; `engine/src/hy4flash/run/mla_test.hip.cpp:327,410-417`）。
- 共用 `CublasPfState::ensure` が成功すること。同 helper は `HY4_CUBLAS_PF` の `atoi` 値が 0 以下なら無効化し、CUDA stream capture 中は利用を見送り、GPU/handle/scratch の初期化を試みる。統合 UMA GPU では `HY4_CUBLAS_PF` が未設定なら無効化し、非 UMA GPU の VRAM が不足する場合も無効化する。scratch 割当や stream/event 作成などが失敗した場合も false を返す（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-21,37-83`）。
- 各 cuBLAS helper 内で `M` と scratch 容量から処理可能な token block `MT` を計算する。`MT < 32`、stream 設定失敗、または cuBLAS GEMM status が成功以外なら helper は false を返し、呼び出し元が fallback kernel に進む（`engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2127,2130-2160,2170-2175,2256-2274`）。

## 実行時の詳細

値は `cublas_mla_mode()` の最初の呼び出しで読み込まれ、以後プロセス内の static 値を再利用する。したがって最初の判定後に環境を変更しても、このプロセスでは反映されない。`mla_prep_q` は許可条件を満たして cuBLAS helper が成功すれば Q の NoPE 部分を cuBLAS GEMM で計算し、RoPE 部分などを pack/unpack kernel で処理して return する。条件不成立または helper 失敗なら `k_prep_q` kernel を起動する。`mla_vup` は許可条件を満たして helper が成功すれば cuBLAS GEMM と unpack kernel で出力を作り return し、それ以外は build の `HY4_MMA` / GPU 分岐に応じた head GEMM kernel、または `k_vup` に進む（`engine/src/hy4flash/run/mla_attn.hip.cpp:2097-2127,2130-2160,2164-2175,2256-2274`）。

この変数について CLI 引数による上書きは見つからない。関連する別設定として `HY4_CUBLAS_PF` が共用 cuBLAS scratch/handle の利用を止める場合があり、`HY4_CUBLAS_MIN_M` が両 projection の最小 `M` を変える。前者は各設定 helper 内で初回利用時に判定される（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-21,37-58`）。

## ログと測定値

`HY4_CUBLAS_MLA` 自体を理由に出すログやエラーはない。共用 `CublasPfState` が初期化されると stderr に `[cublas-pf] side-stream double-buffered dequant + cuBLAS enabled (2 x %.0f MiB scratch, M >= %d)` を出す。統合 UMA GPU で `HY4_CUBLAS_PF` が未設定のときは `[cublas-pf] auto-disabled on integrated UMA GPU (fused skwmma avoids LPDDR5X round-trip; set HY4_CUBLAS_PF=1 to override)`、非 UMA GPU の VRAM 不足では `[cublas-pf] disabled: low free VRAM (%.0f MiB)` を出す。これらは共有 cuBLAS 状態のログであり、`HY4_CUBLAS_MLA` の値や個別の Q/V helper 成功を直接表示するものではない（`engine/src/hy4flash/run/sk_cublas_ctx.hip.h:51-59,84-90`）。

`docs/DETAILS.md` にこの環境変数固有の説明や測定値は見つからなかった。

## 根拠

- `engine/src/hy4flash/run/mla_attn.hip.cpp:2062-2167` — CUDA 専用 cuBLAS MLA helpers と mode の読み取り。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:2169-2175,2256-2274,2328-2332` — Q/V の mode 判定、fallback、attention wrapper。
- `engine/src/hy4flash/run/sk_cublas_ctx.hip.h:15-21,37-90` — 共用 cuBLAS の環境条件、失敗経路、ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2108-2120,2166-2179` — graph runner の prefill と decode の呼び分け。
- `engine/src/hy4flash/run/hy4_gpu.h:17-23,324-327` — CUDA/HIP build macro の定義。
