# `STRATA_PA_FAST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AMD HIP の行列コア prompt attention（WMMA）で、query `q` と softmax weight `p` を FP16 の high/low 2 部分で計算する既定経路から、それぞれ単一の FP16 値で計算する経路へ切り替える。単一 FP16 経路は行列演算を半分にする一方、コメントでは「rounding-level」とされている。通常の2分割経路と同じ結果になる保証はない。CUDA の NVIDIA tensor-core attention を選ぶスイッチではない。実装は `engine/src/kernels/cuda/qsa_prompt_attn.cu` とその SYCL 側コピー `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp` にある（前者 `:1956-1961`、後者 `:1713-1715`）。

## 値と判定

両実装とも `launch_wmma` 内の関数ローカル `static const bool` で `std::getenv` の結果を読み、環境変数が存在し、かつ最初の文字が `'1'` のときだけ true とする（CUDA/HIP: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2348`、SYCL 側: `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1951`）。文字列全体や数値としての妥当性は検査しない。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP WMMA の両実装 | `fast=false`。ただし起動時のアーキテクチャ別既定値が先に `1` を設定する場合がある | 先頭が `1` の文字列（`1`, `1anything`） | 空文字、`0`, `true`, ` 1`, `2`, `01`。これらは先頭文字が `1` でないため無効 |

設定値があっても `fast` は WMMA 経路でだけ参照される。別途、同じ関数内で `STRATA_PF_SWITCH_MIN_T` を `std::atoll` で一度読み、未設定なら `0` とし、`n_q >= min_t` のときに限り `SPLIT=false` にする（CUDA/HIP: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2348-2364`、SYCL 側: `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1951-1960`）。空文字や数値で始まらない文字列は `atoll` により `0` となり、数値以降は判定されない。

## 有効になる条件

- `STRATA_PA_FAST` の実読み取りは HIP コンパイル条件内の WMMA prompt-attention 実装にある。カーネル内の `STRATA_PA_WMMA` は gfx1200/1201、gfx1100/1101/1102/1103、gfx1150/1151 のビルドで有効になり、それ以外では無効である（`engine/src/kernels/cuda/qsa_prompt_attn.cu:1886-1907`、SYCL 側 `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1648-1669`）。
- 呼び出し側が WMMA attention を選ぶ必要がある。HIP では `STRATA_HIP_WMMA`、GPU 世代、WMMA が失敗済みかどうかで選択が決まり、gfx11 は明示的な WMMA 要求が必要。gfx12 は既定選択もある（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2242-2296`）。
- WMMA 呼び出しには正の `n_q`、int8 K/V と scale の各 pool、Q4 pool がないこと、コンパイル済み head geometry との一致、正の `cap`、ID・step・page table が必要。条件を満たさない場合はこの WMMA 関数が false を返し、呼び出し元の別経路に委ねる（HIP: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2456-2468,2471-2518`、SYCL 側 `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1973-2028`）。
- engine 起動時にアーキテクチャ別既定値が `STRATA_PA_FAST=1` を追加する場合がある。統合 GPU では Linux gfx1103、Windows gfx1151 が `STRATA_IGPU_PROMPT_SET` の既定ルールにより対象となり、`STRATA_IGPU_PROMPT_SET=1` は対応する統合 gfx1103/1150/1151 に適用できる。`STRATA_IGPU_DEFAULTS=0` はこの統合 GPU 既定値を無効にする。統合 GPU 条件、対応アーキテクチャ、switch-set の組み立ては `engine/src/core/arch_defaults.cpp:119-138,172-199`、既定値を適用する HIP engine 起動箇所は `engine/src/program/generate.cpp:4287-4320` にある。既定値適用は変数が未設定の場合だけで、空文字を含む明示設定は保持される（`engine/src/core/arch_defaults.cpp:218-223,406-410`）。
- 離散 RDNA3 gfx1100/1101/1102 でも WMMA 既定セットに含まれる。`STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0`、または `STRATA_DEFAULTS=026` によってそのセットを外せる（`engine/include/strata/core/gfx11_extra.hpp:8-12,33-37,87-109`; 適用: `engine/src/core/arch_defaults.cpp:312-344`）。
- `STRATA_PF_SWITCH_MIN_T` が設定されていれば `n_q` の閾値を変える。未設定時の閾値は 0 なので、fast が true なら正の `n_q` で単一 FP16 経路になる。閾値未満では `STRATA_PA_FAST=1` でも2分割経路を使う（CUDA/HIP: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2348-2364`、SYCL 側: `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1951-1960`）。

## 実行時の詳細

読み取り値 `fast` と閾値 `min_t` はそれぞれ初回の `launch_wmma` 呼び出し時に初期化され、以後プロセス内で cache される。起動後に環境変数を変更しても、この関数の判定には反映されない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2346-2364`、SYCL 側 `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1946-1960`）。

各 query chunk について `fast && n_q >= min_t` なら `prompt_attn_wmma_kernel<false>`（CUDA/HIP では gate 付き経路も `pa_launch<false, ...>`）を起動し、それ以外は `<true>` を起動する。`SPLIT=true` は `q` と `p` の FP16 high/low をそれぞれ使う二回の WMMA、false は単一 FP16 image を使う。出力は同じ qsa prompt attention の `attn`、または gate 付きの FP16 出力先に書かれる（`engine/src/kernels/cuda/qsa_prompt_attn.cu:1956-1961,2100-2104,2155-2169,2211-2218,2354-2364`、SYCL 側 `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1713-1721,1951-1960`）。

## ログと測定値

この変数を読み取ったり fast 分岐に入ったりしたこと自体を示す専用ログはない。アーキテクチャ別既定値が実際に追加された場合は、stderr に `strata: integrated GPU (%s): the matrix-core prompt set is on ...` と環境変数名の一覧が出る。明示設定済みの場合は `STRATA_PA_FAST` は追加・一覧表示されない（`engine/src/core/arch_defaults.cpp:406-420`）。

カーネルのソースコメントには「32K context, 2,048 queries, gfx1151, STRATA_PA_FAST=1: 12.49 -> 11.27 ms」とある（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2182-2184`）。このコメントには backend、モデル、KV 量子化、反復数などの条件が記載されていないため、ここでは条件を補ったり一般的な速度差として扱ったりしない。

HIP WMMA 起動エラー時は `qsa_prompt_attn_batch (wmma): %s; the FP32 prompt attention runs from here on` を stderr に出して WMMA を失敗状態にし、false を返す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2366-2372`）。SYCL 側コピーのエラー処理は `qsa_prompt_attn_batch (wmma): %s` を出して `exit(1)` する（`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1962-1967`）。いずれも `STRATA_PA_FAST` の値を理由とする警告ではない。

## 根拠

- 読み取り、閾値、起動選択: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2345-2364`、`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1946-1960`
- 2分割／単一 FP16 の計算差: `engine/src/kernels/cuda/qsa_prompt_attn.cu:1956-1961,2100-2104,2155-2169`
- WMMA の build macro と対応 architecture: `engine/src/kernels/cuda/qsa_prompt_attn.cu:1886-1907`、`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1648-1669`
- GPU 条件、default injection と既存値優先: `engine/src/core/arch_defaults.cpp:124-138,172-223,302-344,406-420`、`engine/src/program/generate.cpp:4287-4320`、`engine/include/strata/core/gfx11_extra.hpp:87-109`
