# `STRATA_INK_OOM_RETRY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 Ink backend の runner 初期化中に GPU バッファ割り当てが失敗したとき、割り当て失敗を例外として捕捉し、prefill chunk を縮小して初期化をやり直すかを切り替える。未設定時は retry が有効で、`STRATA_INK_OOM_RETRY=0` 相当の値では失敗を従来どおりデバイスエラーとして終了させる。失敗した割り当て自体を小分けにする設定ではない。実装は `InkCudaBackend::init` にあり、モデルと expert のロード後、`InkCudaRunner::init` の直前に設定される（`engine/src/inkling2/cuda/ink_cuda_backend.cu:227-232,284-303`）。

## 値と判定

`std::getenv` の結果を `std::atoi` に渡し、設定されていて変換結果が `0` の場合だけ retry 用例外を無効化する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:286-289`）。

| 条件 | 未設定 | retry 有効 | retry 無効 |
| --- | --- | --- | --- |
| CUDA Ink backend | 既定で有効 | `atoi` の結果が非 0（例: `1`, `-1`, `1abc`） | `atoi` の結果が `0`（例: `0`, `00tail`, `true`, `false`, 空文字） |

`atoi` は真偽値や文字列全体の妥当性を検査しない。数値変換前の空白と符号を受け付け、先頭の数値部分を変換するため、`" 1"` は有効、`"0anything"` は無効になる。数値として始まらない文字列は変換結果が `0` となり無効。値の範囲チェックや clamp はない。別の環境変数や CLI 引数によるこの判定の上書きはない（同 `:287-290`）。

## 有効になる条件

- CUDA Ink backend が選択され、その `init` が実行されること。CUDA 実装は `engine/src/inkling2/cuda/ink_cuda_backend.cu` にあり、HIP は別実装 `engine/src/inkling2/hip/ink_hip_backend.hip.cpp` である（`engine/src/inkling2/cuda/CMakeLists.txt:56-65`; `engine/src/inkling2/ink_backend.h:197-208`）。
- `InkCudaRunner::init` 中に、`dalloc` が使う `cudaMalloc` が失敗すること。起動時でも `INK_CK(cudaMalloc(...))` など `dalloc` を通らない処理の失敗まで、この retry 経路が捕捉するわけではない（`engine/src/inkling2/cuda/ink_cuda.cuh:82-89`; `engine/src/inkling2/cuda/ink_runner.cuh:2090-2113`）。
- モデル・expert のロードはこの変数を読み取る前に行われるため、その段階の割り当て失敗には適用されない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:227-232,284-289`）。
- `--chunk` や自動 chunk 選択は retry の開始 chunk に影響するが、retry 判定を上書きしない。自動選択は `opts.chunk_auto && !model_.ls_active` の場合に行われる（同 `:290-300`）。
- CUDA backend 以外の backend への適用は確認できない。Strata の `docs/SETTINGS.md:401` は NVIDIA と AMD の双方を記載しているが、完全な名前のソース参照は CUDA backend の `getenv` 1 箇所だけで、HIP 実装には見つからない。

## 実行時の詳細

`InkCudaBackend::init` はモデルファイルのロードが成功した後に環境変数を読み、結果から `ink_alloc_throws()` を設定する。この状態は `thread_local` のフラグで、`ink_alloc_failed` は `dalloc` 内の `cudaMalloc` が失敗すると、フラグ有効時に `InkAllocFailure` を投げ、無効時には `exit_device_error` を呼ぶ（`engine/src/inkling2/cuda/ink_cuda_backend.cu:227-232,284-289`; `engine/src/inkling2/cuda/ink_cuda.cuh:60-89`）。

runner 初期化で例外を捕捉すると、backend は runner の確保済み領域を解放して作り直し、chunk を `max(64, chunk_try / 2)` に下げる。chunk がすでに 64 以下なら初期化を `false` で返し、例外メッセージと「smallest size でも working buffers に足りない」旨、および `--max-context`、`--vram-experts-gb`、他プログラム終了の案内を `err` に設定する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:321-337`）。環境変数が `atoi` で 0 になる場合は例外捕捉経路に入らず、割り当て失敗時にエンジンが終了する。

runner 初期化後、DSpark が要求され、モデルに drafter があり、layer split でない場合にも同じ例外フラグが有効なまま初期化を試みる。DSpark の割り当て失敗は別途捕捉され、drafter の領域を解放して DSpark を無効化する。これは chunk を下げる runner retry ではない。続いて例外フラグを無効化し、後続処理での割り当て失敗をこの起動 retry が扱わない状態に戻す（同 `:343-355`）。

環境変数は `InkCudaBackend::init` ごとに一度読み、初期化中は保存済みの thread-local フラグを参照する。初期化後にプロセス環境を変更してもその初期化には反映されず、別の初期化で再読込される。追加の cache はない（同 `:287-289`; `engine/src/inkling2/cuda/ink_cuda.cuh:66-79`）。

## ログと測定値

retry 時は stderr に `[InkCUDA] not enough free GPU memory for the working buffers at chunk %d (%s); retrying with chunk %d` を出す。最小 chunk でも失敗した場合は `err` を返すが、この分岐自体に専用の `fprintf` はない。DSpark の失敗では `[InkCUDA] DSpark drafter turned off: not enough free GPU memory for it (%s)` を stderr に出す（`engine/src/inkling2/cuda/ink_cuda_backend.cu:328-352`）。割り当て例外の `%s` には、要求 MiB と空き/総 MiB を含む `strata-inkling CUDA error ...` の文字列が入る（`engine/src/inkling2/cuda/ink_cuda.cuh:70-79`）。この変数に関する条件付き測定値は、参照した Strata 資料にない。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:227-232,284-355` — 読み取り時点、判定、chunk retry、停止条件、DSpark fallback。
- `engine/src/inkling2/cuda/ink_cuda.cuh:60-89` — 割り当て失敗の例外化・終了処理と `dalloc`。
- `engine/src/inkling2/cuda/ink_runner.cuh:2090-2113` — runner の起動時初期化と `dalloc` を使わない `INK_CK(cudaMalloc(...))` の例。
- `engine/src/inkling2/cuda/CMakeLists.txt:56-65`, `engine/src/inkling2/ink_backend.h:197-208`, `engine/src/inkling2/hip/ink_hip_backend.hip.cpp` — backend の分離。候補名の全参照検索では HIP 側に読み取りがない。
- `docs/SETTINGS.md:401`, `docs/DETAILS.md:1533` — 資料との照合。SETTINGS の対応 backend 表記はソースで確認できる読み取り範囲と一致しない。DETAILS の該当箇所は別の expert-cache allocation error を扱い、この retry 変数の仕様根拠にはしていない。
