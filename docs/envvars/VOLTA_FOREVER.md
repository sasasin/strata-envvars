# `VOLTA_FOREVER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`VOLTA_FOREVER` は volta-forever shim が有効だと Strata に知らせる補助入力です。`strata::core::volta_forever_active()` はこの値を、Strata 固有の `STRATA_VOLTA_FOREVER`、shim の version symbol、`LD_PRELOAD` の検査と合わせて判定します。判定結果は CUDA module loading の既定値や一部の CUDA Graph 経路に使われます。候補名の読み取りは `engine/include/strata/core/volta_forever.hpp:42-65` にあります。

## 値と判定

数値・真偽値への変換はせず、文字列の有無と完全一致を判定します。優先順位は次のとおりです。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `STRATA_VOLTA_FOREVER` が非空 | 対象変数を判定 | 対象変数の値にかかわらず、こちらの先頭文字が `0` 以外なら有効（例: `1`, `true`, ` 0`, `00`） | 先頭文字が `0` なら無効（例: `0`, `0anything`）。対象変数や shim 検出へ進まない |
| `STRATA_VOLTA_FOREVER` が未設定または空 | 下の `VOLTA_FOREVER` 判定へ進む | 対象変数が空でない文字列かつ完全な `0` 以外（例: `1`, `true`, `0anything`, `00`, ` 0`） | 未設定、空文字、または完全な `0`。この場合も shim 検出は続く |

大文字小文字や空白の正規化、数値としての妥当性検査はありません。したがって `false` も有効、`0anything` は対象変数では有効ですが、`STRATA_VOLTA_FOREVER=0anything` は先頭文字判定で無効です。対象変数の値 `0` は shim を強制的に無効化しません。後続の version symbol が空でなく、または `LD_PRELOAD` に `libvolta_forever` が含まれる場合は有効になります。`STRATA_VOLTA_FOREVER` の先頭文字が `0` の場合だけ、後続判定を打ち切ります（`engine/include/strata/core/volta_forever.hpp:42-58`）。

## 有効になる条件

- この値だけで判定結果が有効でも、CUDA module loading の変更は `apply_default_cuda_module_loading()` を呼ぶ CUDA 対応実行経路に限られます。呼び出しは `strata-hy4` の `HY4_CUDA` build、Inkling の `INKLING_ENABLE_CUDA` / `INKLING_ENABLE_EP_CUDA` build、`strata-inkling-cuda`、`strata-q36`、および `engine/src/program/generate.cpp` にあります（`engine/src/hy4flash/run/hy4_main.hip.cpp:342-345`、`engine/src/inkling2/ink_main.cpp:366-370`、`engine/src/inkling2/cuda/ink_cuda_main.cu:38-41`、`engine/src/qwen35/q36_engine.cu:5420-5423`、`engine/src/program/generate.cpp:3765-3771`）。
- module loading の既定値を変えるのは `CUDA_MODULE_LOADING` が未設定のときだけです。空文字を含め、設定済みなら Strata は値を上書きしません（`engine/include/strata/core/volta_forever.hpp:74-94`）。
- `strata-hy4` では `HY4_HAS_GRAPHS` が有効な CUDA build で、取得した device property が厳密に major 7 / minor 0 かつ本判定が有効なとき、1024-thread CUDA Graph の既定利用を止めます。`HY4_GPU_GRAPH`、`HY4_CUDA_GRAPH`、`HY4_HIP_GRAPH` のいずれかが設定されていれば、その値の `atoi(...) != 0` が graph の明示設定になります。分散 build では別の条件で graph を止める経路もあります（`engine/src/hy4flash/run/hy4_graph.hip.h:1712-1736`）。
- Inkling CUDA backend は device property が同じく厳密に 7.0 で本判定が有効なら、CUDA Graph の利用を許可しません。さらに EP2 または layer-split が有効なら、判定が graph を許可していても `runner_->use_cuda_graph` は false です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:233-240`）。
- `strata-q36` は既定で graph を使いますが、`--no-graph` で無効化できます。graph instantiate が失敗したとき本判定が有効なら、graph を無効にして当該処理を stream launch で再実行します（`engine/src/qwen35/q36_engine.cu:3612-3634`、`5346-5372`、`5474`）。
- compute capability の `7.5` から `7.0` への再マップは別の `strata::volta_forever_active()` を使い、`engine/include/strata/core/emulate.hpp:18-56,67-80` では version symbol の結果をキャッシュして判定します。この経路は `VOLTA_FOREVER` を読まないため、この変数だけでは再マップを有効にしません。`engine/src/program/generate.cpp:8494-8500` の表示・再マップ判定もこの別 helper に依存します。

## 実行時の詳細

`volta_forever_active()` は呼び出しごとに `std::getenv("VOLTA_FOREVER")` と他の検出入力を読み、結果を static cache しません。従って、プロセス実行中に環境値が変更されれば、その後の同 helper 呼び出しには反映され得ます。一方、`CUDA_MODULE_LOADING` の既定値設定は各実行ファイルの記載位置で一度呼ばれ、その時点ですでに同変数が存在すれば変更しません。Strata が `VOLTA_FOREVER` を子プロセスへ転送・上書きする処理は見つかりません（`engine/include/strata/core/volta_forever.hpp:61-94` と上記呼び出し位置）。

`CUDA_MODULE_LOADING` が未設定で本判定が有効なら `LAZY`、無効なら `EAGER` を設定し、前者の場合だけ関数は true を返します。`setenv(..., 0)` / `_putenv_s` による設定後、呼び出し元が true のときだけ検出ログを出します（`engine/include/strata/core/volta_forever.hpp:74-94`）。

## ログと測定値

検出され、かつ `CUDA_MODULE_LOADING` が未設定で `LAZY` を設定した場合、呼び出し元により `[gpu] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`、`[inkling] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`、`[inkling-cuda] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`、`strata-q36: volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`、または `strata: volta-forever detected (%s): setting CUDA_MODULE_LOADING=LAZY` が stderr に出ます。既定値設定が行われない場合、このログは出ません（各呼び出し元は「有効」だけでなく関数の true 戻り値も確認します。`engine/src/hy4flash/run/hy4_main.hip.cpp:343-345`、`engine/src/inkling2/ink_main.cpp:367-369`、`engine/src/inkling2/cuda/ink_cuda_main.cu:39-41`、`engine/src/qwen35/q36_engine.cu:5421-5423`、`engine/src/program/generate.cpp:3768-3771`）。

グラフ経路では、hy4 が既定 graph capture を止めると `[runner] sm_70 under volta-forever: disabling 1024-thread CUDA Graph capture by default (HY4_CUDA_GRAPH=1 overrides)`、Inkling が止めると `[inkling-cuda] sm_70 under volta-forever: disabling 1024-thread CUDA Graph capture by default` を stderr に出します。q36 の graph instantiate 失敗時は CUDA error 名を含む `strata-q36: CUDA Graph instantiate returned %s under volta-forever (sm_70 512-thread graph limit); running stream launches` を出し、以後 graph を無効にします（`engine/src/hy4flash/run/hy4_graph.hip.h:1729-1733`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:234-239`、`engine/src/qwen35/q36_engine.cu:3619-3634`）。Strata の資料にこの環境変数による測定値はありません。`docs/NVIDIA_V100.md:53-59` は shim の version symbol 検査や module loading を説明していますが、`VOLTA_FOREVER` alias の値判定は記載していません。

## 根拠

- `engine/include/strata/core/volta_forever.hpp:42-65` — 値の優先順位と全読み取り箇所。
- `engine/include/strata/core/volta_forever.hpp:74-103` — module loading の既定値と 1024-thread graph の条件。
- `engine/include/strata/core/emulate.hpp:18-80` — 別の symbol-only detection と compute capability 再マップ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1712-1736`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:233-240`、`engine/src/qwen35/q36_engine.cu:3612-3634` — graph の有効条件・fallback。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:342-345`、`engine/src/inkling2/ink_main.cpp:366-370`、`engine/src/inkling2/cuda/ink_cuda_main.cu:38-41`、`engine/src/qwen35/q36_engine.cu:5420-5423`、`engine/src/program/generate.cpp:3765-3771` — module loading 設定の呼び出しとログ。
