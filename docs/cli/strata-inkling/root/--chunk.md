# `--chunk`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root、CUDA/HIP） |
| オプション | `--chunk` |
| 別名 | なし |
| 値 | prompt の token 数を表す整数。parser は正数へ補正するが、parser 自体に上限検査はない |

## 役割

prompt を prefill するとき、1 回の forward step で処理する token 数を指定する。serve では複数 slot の prefill と decode をまとめる token budget に、bench では prompt の分割幅に使われる。既定では 512 token だが、CUDA backend は明示指定がない場合、初期化後の GPU 空き容量と slot 数から chunk を自動選択する。CUDA/HIP 以外の backend ではこの自動選択フラグは使われず、設定された `chunk` が使われる。

## 使い方

```sh
# CUDA/HIP で serve の prefill step を 1024 token に指定
strata-inkling --serve --native model.strata --chunk 1024

# bench の prompt 処理幅を指定
strata-inkling --bench --native model.strata --chunk 512 --prompt-len 2048
```

## 値と既定値

- 値は必須。値が続かない場合は `missing value after --chunk` を stderr に出し、終了コード 2 で終了する。
- parser は `atoi` で整数化した後 `max(1, 値)` を設定する。したがって 0、負数、数値に変換できない文字列は 1 に補正される。parser に最大値の検査はない。
- 未指定時は `BackendOpts::chunk = 512`、`chunk_auto = true`。`--chunk` を指定すると `chunk_auto = false` になる。
- CUDA backend は runner 初期化の chunk を最低 64 にする。さらに runner の `max_batch` による実効上限や、確保失敗時の縮小再試行があるため、明示値が実際の実行幅より大きくなる場合がある。

## 実行時の動作

- serve は backend が報告する実効 chunk（なければ設定値）を `chunk_sz` とし、各 batch の初期 token budget を `max(chunk_sz, active slot 数)` にする。先に decode token を batch に追加し、残りの budget を複数の prefill slot に分配する。`STRATA_INK_PREFILL_CAP` が設定され、同時に decode がある場合は prefill 分の budget がさらに制限される（`engine/src/inkling2/ink_serve.h:494-507,1003-1047`）。
- bench では実効 chunk ごとに prompt を分割して batch を作る（`engine/src/inkling2/ink_main.cpp:168-184`）。通常の直接生成経路は prompt token 列全体を一つの `StepBatch` に追加して一度 `forward_batch` するため、この経路で `--chunk` による prompt 分割は行わない（`engine/src/inkling2/ink_main.cpp:1097-1115`）。
- CUDA の明示 chunk は `chunk_auto` を無効にする。未指定時は `STRATA_INK_CHUNK_AUTO=0` で自動選択を止められる。自動選択は layer split 中には行わず、未指定 chunk の 512 を基準とする。自動選択時は expert 配置後の空き VRAM、context 終端までに必要な K/V 容量、slot 数を使い、最大 2048 までの候補から選ぶ（`engine/src/inkling2/cuda/ink_cuda_backend.cu:282-301`、`engine/include/strata/core/ink_chunk.hpp:18-49`）。
- CUDA の runner 初期化が `InkAllocFailure` になった場合、chunk を半分にして再試行し、64 でも失敗すれば backend 初期化失敗を返す。`STRATA_INK_OOM_RETRY=0` はこの再試行を無効化する。成功後の serve/bench 実効 chunk は `min(chunk_try, runner.max_batch)` で決まる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:284-340`）。
- HIP は `chunk_auto` を参照せず、`opts.chunk` を prefill span 用の SWA ring 計算にも使う。serve scheduler は backend の既定 `effective_chunk()` が 0 のときに `opts.chunk` をそのまま使う（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:718-734`、`engine/src/inkling2/ink_backend.h:17-21,68-76`、`engine/src/inkling2/ink_serve.h:494-499`）。

## 適用条件と副作用

- `--chunk` は parser に登録されているが、`--info`、`--export-tokenizer`、`--selfcheck` などの先行モードが選ばれた場合、後続の通常モデル初期化や serve / bench 処理には進まない。通常の serve、bench、直接生成ではモデル backend の初期化に渡される（`engine/src/inkling2/ink_main.cpp:845-881,1039-1094`）。
- CUDA では chunk が runner の作業領域や K/V ring の大きさに関係し、GPU メモリ確保・自動縮小・起動失敗に影響する。HIP でも SWA KV ring の計算に反映される（`engine/src/inkling2/cuda/ink_runner.cuh:2090-2095`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:724-734`）。
- CUDA の自動 chunk ログは stderr に `[InkCUDA] prefill chunk ...` と出る。確保失敗時も縮小再試行を stderr に記録する。64 token でも確保できないと `init` エラーを表示して終了コード 1 になる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:299-300,328-340`、`engine/src/inkling2/ink_main.cpp:1086-1091`）。

## 出力とエラー

- オプション値の欠落: stderr に `missing value after --chunk`、終了コード 2（`engine/src/inkling2/ink_main.cpp:845-849`）。
- 未知の option: stderr に `unknown option: ...`、終了コード 2（`engine/src/inkling2/ink_main.cpp:985-988`）。
- backend の初期化失敗: 通常モードでは stderr に `init: <詳細>`、終了コード 1。serve では protocol 出力 `ERR init: <詳細>`、終了コード 1（`engine/src/inkling2/ink_main.cpp:1086-1091`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:845-849,875-881` — root parser、値欠落時の終了、整数変換と自動選択解除。
- `engine/src/inkling2/ink_backend.h:17-21,68-76` — 512 の既定値、`chunk_auto` の意味、backend の既定実効 chunk。
- `engine/src/inkling2/ink_serve.h:494-507,1003-1047` — serve の実効 chunk、prefill budget と cap。
- `engine/src/inkling2/ink_main.cpp:168-184,1097-1115` — bench の prompt 分割と直接生成の単一 batch。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:282-340`、`engine/include/strata/core/ink_chunk.hpp:18-49` — CUDA 自動選択、メモリ見積もり、確保 retry と実効値。
- `engine/src/inkling2/cuda/ink_runner.cuh:2090-2129` — CUDA runner の batch 容量とメモリ状況に応じた上限。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:718-734` — HIP 側の `opts.chunk` 使用箇所。
