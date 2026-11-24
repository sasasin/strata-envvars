# `STRATA_INK_Q80_TC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 Inkling-2 MoE が GGUF_RAW の Q8_0 expert を実行するとき、INT8 Tensor Core kernel を使い始める最小 token 数 `M` を指定する。条件を満たすと Gate/Up と Down の Q8_0 行列を `k_ink_moe_q80_tc` で処理し、それ以外の GGUF expert は既存の DP4A kernel で処理する。DP4A 側は Q8_0 expert をスキップし、二重計算しない。kernel コメントは DP4A と同じ演算順・結果（bit for bit）と説明している。ルーティングや選択 expert はこの変数では変更しない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:969-975, 3832-3858`）。

読み取り箇所は `launch_ink_moe_dispatch_only` 内の CUDA 実装だけである。同ファイルは CUDA backend のソースであり、HIP・SYCL・Metal 側にこの変数の読み取りはない。`docs/SETTINGS.md:405` は NVIDIA and AMD と分類しているが、調査対象 HEAD の実装上の適用範囲は CUDA 経路である。`docs/DETAILS.md` にこの変数の個別説明は見当たらない。

## 値と判定

環境値を `std::getenv` で取得し、設定されていれば `std::atoi` で `int` に変換する。文字列全体の検証、エラー報告、clamp はない。空文字や数値で始まらない文字列は `atoi` の結果が 0 になり、正の threshold ではないため無効になる。先頭の空白と符号は `atoi` の規則で扱われ、数字の後ろは変換されない（例: `256junk` は 256）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---:|---|---|
| CUDA Inkling-2 GGUF_RAW dispatch | 256 | `1` 以上の整数。実行時に `M >= 値` なら候補になる | 空文字、`0`、`-1`、`true`、`0anything`。`atoi` 結果が 0 以下なら使わない |

したがって既定では `M >= 256` のとき候補になり、`0` はコメントにあるとおり無効化する。負数も `q80_tc_min > 0` の条件を満たさず無効。`atoi` は変換範囲の検査をしないため、`int` で表現できない入力の扱いはこのコードで保証されない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3828-3832`）。

## 有効になる条件

- 呼び出しが CUDA Inkling-2 MoE dispatch であり、その層に `info.has_gguf` があること。expert directory の Gate/Up code が `FMT_GGUF_RAW` の場合にこのフラグが立つ（`engine/src/inkling2/cuda/ink_runner.cuh:1522-1529`）。
- 該当する Gate/Up または Down の GGUF type が `8u`（Q8_0）であること。Q8_0 以外の GGUF type はこの kernel が処理しない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:886-887, 940-941, 990-994`）。
- `q80_tc_min > 0` かつ dispatcher の token 数 `M >= q80_tc_min` であること（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3831-3832`）。
- 現在の CUDA device が INT8 Tensor Core 対応であること。能力判定は device properties の compute capability major が8以上かで行われ、device ごとに cache される。非対応または能力取得失敗なら Q8_0 Tensor Core kernel を起動せず、DP4A 経路を使う（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:2298-2311`; `engine/include/strata/core/ink_caps.hpp:16`）。

環境値を選ぶ CLI 引数や別環境変数による上書きはこの読み取り箇所にない。`STRATA_INK_GGUF_MT` は GGUF DP4A kernel の token group サイズを選ぶ別設定で、この threshold の判定式には入らない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3826-3843`）。

## 実行時の詳細

環境変数は `launch_ink_moe_dispatch_only` の関数内 `static const int` 初期化で最初に一度だけ読み取られる。したがって最初に `info.has_gguf` の dispatch がこのコードまで到達したときの値がプロセス内で保持され、実行中に環境を変えても反映されない。threshold はプロセス共通で、INT8 対応の有無は別途 device ごとに判定される（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:2305-2311, 3814-3833`）。

条件成立時は Gate/Up 用 kernel を先に起動し、続いて通常の GGUF Gate/Up DP4A kernel に `skip_q80` を渡す。中間値を Q8_1_G32 に量子化した後、Down 用 Tensor Core kernel を起動し、Down DP4A にも同じ skip flag を渡す。DP4A kernels は該当する type 8 の行列を飛ばし、Tensor Core kernel は GGUF_RAW かつ type 8 の expert のみ処理する。閾値未満・無効値・能力不足時は `skip_q80` が false となり、GGUF kernel が通常の DP4A 経路で処理する（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:886, 940, 983-994, 3832-3858`）。

## ログと測定値

この設定の読み取り・有効化・fallback に伴う専用ログや警告はコードにない。kernel の切り替えは dispatch 内の分岐で行われる（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3831-3858`）。

同ファイルのコメントは、UD-Q4_K_XL の2048-token prefill chunkを RTX 4090 で測ったとき 2,805 から 3,370 ppts、低 token 数の例では8 slots が2.3対4.6 ms、64 slots が12.7対17.1 ms（DP4A対Tensor Core）と記す。ただし同箇所には測定方法・回数の説明はなく、別環境での性能を保証する値ではない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3828-3830`）。

## 根拠

- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:969-995` — Q8_0 Tensor Core kernel と対象型の判定。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:2298-2311` — CUDA device ごとの INT8 Tensor Core capability 判定。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3812-3858` — 値の読み取り、threshold 判定、GGUF dispatch と fallback。
- `engine/src/inkling2/cuda/ink_runner.cuh:1522-1529` — 層の `has_gguf` フラグ設定。
- `engine/include/strata/core/ink_caps.hpp:16` — compute capability major による INT8 TC 対応判定。
- `docs/SETTINGS.md:405` — 設定一覧の分類（NVIDIA and AMD）。
