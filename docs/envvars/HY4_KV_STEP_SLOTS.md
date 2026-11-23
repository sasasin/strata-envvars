# `HY4_KV_STEP_SLOTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 GPU runner が sparse KV cache と IndexPool の VRAM 容量を拡張するときの増分を、slot 数で指定する。`Runner::kv_grow_to` は必要位置数と現在位置数から拡張先をこの step の倍数へ切り上げ、`max_ctx` を上限として再確保する。KV の内容や token 選択を変える設定ではなく、容量を増やす単位を変える（`engine/src/hy4flash/run/hy4_graph.hip.h:2795-2806`）。

対象は `strata-hy4` の GPU 実装で、CMake 上は `STRATA_BUILD_HY4=ON` かつ CUDA または HIP が必要。CLI 実行と `--serve` のどちらも `plan_memory` を通る。Metal と SYCL の専用 runner にはこの名前の参照がない（`engine/CMakeLists.txt:846-852,884-908`、`engine/src/hy4flash/run/hy4_main.hip.cpp:647-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295`）。

## 値と判定

読み取りは `getenv` の設定有無判定と `atoi` による整数変換。全体の数値妥当性検査や末尾文字の検査はなく、変換結果に `std::max(4096, ...)` を適用する。したがって空文字・数字で始まらない文字列・`0`・負数は変換値が 0 以下となり step は 4096。`atoi` が認識する先頭の空白や符号は許容され、数値の後ろの文字列は判定されない（例: `8192junk` は 8192）。範囲外の整数文字列についてはコードに明示的な検査がない（`engine/src/hy4flash/run/hy4_graph.hip.h:2798`）。

| 条件（build / 実行経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `strata-hy4` CUDA/HIP runner の `kv_grow_to` | 16384 | `4096` → 4096、`8192` → 8192、`8192junk` → 8192 | 空文字、`abc`、`0`、`-1`、`1` → 4096 に下限 clamp |
| 単一 GPU、`HY4_KV_NO_GROW` 未設定、検出 VRAM が 44 GiB 未満で `plan_memory` 実行 | `plan_memory` が環境に既定値を設定: 4,096 / 8,192 / 16,384 | 事前設定値があればその値を保持し、`kv_grow_to` 側で判定 | 空文字も「設定済み」として保持されるため planner は補完しないが、読み取り時は 4096 に clamp |
| 複数 GPU、`HY4_KV_NO_GROW` 設定、または VRAM が上記しきい値以上 | planner は設定しない。読み取り側の既定値 16384 | 事前設定値があれば `kv_grow_to` で使用 | 同上 |

planner の既定 step は `total / 1e9` を `tot` とし、`tot <= 9.0` なら 4096、`tot <= 13.5` なら 8192、それ以外の対象範囲では 16384。planner が既定値を書き込むのは単一 GPU、`HY4_KV_NO_GROW` が未設定、かつ `total < (44ull << 30)`（44 GiB）の場合である。既存の `HY4_KV_STEP_SLOTS` は空文字でも上書きしない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:464-481`）。

## 有効になる条件

- `strata-hy4` の CUDA または HIP GPU runner がビルドされ、初期計画および KV 拡張経路を実行すること。`STRATA_BUILD_HY4` は既定 OFF（`engine/CMakeLists.txt:846-852`）。
- KV が host 配置でなく、必要位置が `kv_alloc_pos` を超えること。`forward_chunk` はこの条件で `kv_grow_to` を呼ぶ。host 配置、または既存割当内の処理では step は使われない（`engine/src/hy4flash/run/hy4_graph.hip.h:2859-2862,3384-3386`）。
- `HY4_KV_DEVPOS` が正の上限として設定されているとき、計算した次の目標がその上限を超えれば step による VRAM 拡張は行わず pinned host memory へ移す（`engine/src/hy4flash/run/hy4_graph.hip.h:2799-2801`）。
- VRAM が拡張分を確保できない場合も `vcache_release_vram` 後に再確認し、なお不足すれば pinned host memory へ移す。step 値が有効でも、この fallback が起きれば VRAM 上の拡張ログは出ない（`engine/src/hy4flash/run/hy4_graph.hip.h:2802-2818`）。
- `HY4_KV_NO_GROW` は planner による初期 step の自動設定だけを止める。既に環境にある値は `kv_grow_to` が読むため、変数設定だけで step 読み取りが無効になるわけではない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:464-481`、`engine/src/hy4flash/run/hy4_graph.hip.h:2796-2799`）。

## 実行時の詳細

通常の CLI 起動ではモデルロード前に `plan_memory` が呼ばれ、`--serve` でも runner 初期化前に同じ計画関数が呼ばれる。planner は上記条件で `HY4_KV_STEP_SLOTS` が未設定の場合、GPU メモリ量から算出した step を `hy4_setenv` でプロセス環境に設定する。Windows では `_putenv_s`、それ以外では `setenv(..., 1)` を使う。既存値は planner が維持する（`engine/src/hy4flash/run/hy4_main.hip.cpp:647-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-411,464-481`）。

実際の値は各 `kv_grow_to` 呼び出し時に `getenv` で読み直され、関数内 static cache はない。プロセス環境を変更すれば後続の拡張で再評価される。step は少なくとも 4096。目標は `max(need + 16, kv_alloc_pos + step)` を step の倍数へ切り上げた値と `max_ctx` の小さい方。成功時は全 sparse layer の KV / IndexPool 領域を拡張して旧内容をコピーし、`kv_alloc_pos` と `slots_sparse` を更新する（`engine/src/hy4flash/run/hy4_graph.hip.h:2796-2806,2820-2856`）。

## ログと測定値

この変数名や採用 step を直接表示するログはない。VRAM 拡張が成功した場合は stderr に `[runner] sparse KV + IndexPool grew in VRAM: %d -> %d positions (%.2f GB total, %.1f ms)` を出す。VRAM 不足時に host へ移せば `[runner] sparse KV + IndexPool moved to pinned host memory (%d positions, %.2f GB, %.2f s)` を出す（`engine/src/hy4flash/run/hy4_graph.hip.h:2793,2855-2856`）。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-411,434-481` — 環境設定 helper、メモリ計画、step 既定値の設定条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2793-2818,2820-2862,3384-3386` — step の読み取り・clamp、拡張先計算、VRAM fallback と呼び出し条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:647-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295` — CLI と server の計画呼び出し。
- `engine/CMakeLists.txt:846-852,884-908` — HY4 GPU target の build 条件。
