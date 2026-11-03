# `STRATA_HEAD_HOST`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

CUDA の native output head を VRAM ではなく mapped pinned host memory に置くよう要求します。native head の読み込みが実行されるときに限り有効です。通常の head 経路や、SYCL 実装にはこの変数の読み取りはありません。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_HEAD_HOST") != nullptr` かだけを見ます。

| 設定状態 | 読み込み時の動作 |
|---|---|
| 未設定 | `cudaMalloc` で head を VRAM に確保する。確保失敗時は条件を満たせば host memory へ fallback する。 |
| 設定あり | 空文字を含め、どの値でも VRAM の `cudaMalloc` を試さず、確保失敗と同じ状態から host memory fallback を試す。 |

数値・真偽値・大文字小文字・空白の検証や、無効値からの fallback 判定はありません。CLI 引数による同じ設定の上書きもありません。

## 有効になる条件

- `strata generate` で `--native-head-gguf` が指定され、`--stream-token` も指定されている必要があります。`--native` を使う場合は native preset が head GGUF として自動設定され、同時に stream-token も有効になります（`--native` 自体には PLE 関連の前提があります）。どちらの指定もなければ `NativeHead::load()` に進まず、この変数は使われません。単一 GPU では `NativeHead` を直接ロードし、layer split では最終 stage の head をロードします。
- CUDA 実装でのみ読み取られます。SYCL 側の `sycl/src/core/native_head.cpp` は device memory を割り当てる実装で、この変数を参照しません。
- host memory fallback には discrete GPU であること（`spill_allowed()` が integrated GPU を拒否）、`STRATA_HEAD_HOST_OFF` が未設定であること、`STRATA_Q6_PACKED` が有効でないことが必要です。`STRATA_HEAD_HOST_OFF` は値の内容でなく設定有無を見ます。`STRATA_Q6_PACKED` は別 helper で文字列全体が `"1"` の場合に有効となり、結果を static cache します。これらの条件を満たさない場合、`STRATA_HEAD_HOST` が設定されていると VRAM allocation を省略したまま fallback できず、head load が失敗します。
- head の GGUF、architecture、`output.weight` の型・次元・payload が native head の要件を満たす必要があります。

## 実行時の詳細

`NativeHead::load()` は GGUF の `output.weight` を検証し、重みサイズを計算した後に環境変数を読みます。この読み取りに static cache はなく、各 `load()` 呼び出しで評価されます。設定ありなら `status` を `cudaErrorMemoryAllocation` として後続処理へ進めるため、通常の VRAM allocation は行われません。fallback 条件を通ると `cudaHostAlloc(..., cudaHostAllocMapped | cudaHostAllocPortable)` と `cudaHostGetDevicePointer()` を試し、成功時は GGUF の重みを host buffer にコピーして、その device alias を `weights` に使用します。Strata は stderr に `strata generate: short of GPU memory: the output head (... MiB) stays in pinned host memory and is read over PCIe for every logits row: decode is slower` を出します。

fallback の host allocation または device alias 取得に失敗した場合、確保した host buffer を解放します。後続の失敗処理では `native head upload: <CUDA error>` が `err` に入り、単一 GPU の呼び出し元は `strata generate: ...` と VRAM 空き容量等の補足を stderr に出して status 1 で終了します。layer split では `strata generate: layer split, CUDA%d head: ...` を出して status 1 で終了します。fallback 成功後も scratch buffer の確保は必要で、失敗すれば load 全体が失敗します。

ロード後は `run_head` が通常 head の代わりに native head の GEMV を実行します。Strata のコードは mapped host alias をその重み pointer として渡し、失敗を `native head launch: ...` として返します。なお、`STRATA_HEAD_HOST` 自体が制御するのは初回 load 時の配置選択です。別の cache sizing 経路では、十分な GPU cache slot を確保できなかった後に native head を `to_host()` へ移す処理もありますが、それはこの変数の判定ではなく、`STRATA_HEAD_HOST_OFF` / `STRATA_SPILL_OFF` 等の条件で制御されます。

## 根拠

- `src/core/native_head.cpp:32-57` — native head load の前提、GGUF head の検証とサイズ計算。
- `src/core/native_head.cpp:61-96` — 環境変数判定、VRAM allocation の省略、fallback 条件・host memory copy・ログ・upload error。
- `src/core/native_head.cpp:139-160` — loaded head の実行と CUDA launch error の返却。
- `src/program/generate.cpp:3377-3379,4215-4225,4351-4358,4420-4423` — `--native-head-gguf` / `--native` の設定、shard 解決、`--stream-token` 必須条件。
- `src/program/generate.cpp:6417-6424,6880-6892,8660-8665` — layer split 最終 stage / 単一 GPU での load、load error の終了、native head 実行経路。
- `include/strata/core/spill_gate.hpp:14` — integrated GPU と Metal build を spill 対象外にする条件。
- `src/kernels/cuda/native_mmvq.cu:2949-2955` — `STRATA_Q6_PACKED` の完全一致判定と static cache。
- `sycl/src/core/native_head.cpp:24-67` — SYCL load が device allocation を行い、`STRATA_HEAD_HOST` を読まないこと。
- `src/program/generate.cpp:7676-7703` — `STRATA_HEAD_HOST` とは別の、cache sizing 後の `to_host()` 経路。
