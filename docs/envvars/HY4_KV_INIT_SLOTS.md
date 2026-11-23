# `HY4_KV_INIT_SLOTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

GPU Hy4-Flash runner が sparse KV cache と IndexPool を VRAM に最初に確保する位置数を指定する。GPU model の計画時には `init_slots` としてメモリ見積り・chunk 選択にも使われ、Graph 初期化時には実際の確保位置数の上限になる。実行時により多くの位置が必要なら、その後の VRAM 拡張または pinned host memory への退避は別の処理として行われる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:459-501`, `engine/src/hy4flash/run/hy4_graph.hip.h:1602-1625`, `2795-2856`）。

名前の直接参照はこの 2 箇所だけ。計画時は、単一 GPU・`HY4_KV_NO_GROW` 未設定・VRAM 総量が `44ull << 30` 未満で、かつ context が VRAM 別の初期目標より大きい場合に限って読む。既定の初期目標は総 VRAM を十進 GB 換算して `<=9.0` なら 4096、`<=13.5` なら 8192、それ以外なら 16384。Graph 側の読み取りは KV が host 配置でない限り無条件で、計画分岐に入らない場合も適用される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-470`, `engine/src/hy4flash/run/hy4_graph.hip.h:1602-1609`）。Metal / SYCL runner にはこの名前の読み取りがない。

## 値と判定

両箇所とも `getenv(...)` が null かどうかで設定有無を判定し、設定されていれば `atoi` で変換する。文字列全体の数値検証はない。`atoi` は先頭空白と符号を許し、数値として読める先頭部分の後ろは無視し、数値が始まらない文字列や空文字は 0 として扱う。従って `8192junk` は 8192、`true`・`false`・空文字は 0 相当。大文字小文字の比較はしない。計画時と Graph 初期化時で下限が異なる。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・境界 |
|---|---|---|---|
| GPU model 計画の自動伸長分岐に入る場合 | context が目標以下なら `max_ctx`。目標を超える場合は VRAM 別目標（4096 / 8192 / 16384）を `init_slots` にし、同じ値を環境へ設定 | `atoi` 結果を `[2048, max_ctx]` に clamp | 0、負値、空文字、`true` などは 2048。値が `max_ctx` より大きければ `max_ctx`。例: `0` → 2048、`999999` → context 上限 |
| Graph 初期化で `kv_is_host == false` | `max_ctx` | `atoi` 結果に 4096 の下限を適用し、さらに `max_ctx` 以下にする | 0、負値、空文字、非数値文字列は 4096。`max_ctx < 4096` なら最終値は `max_ctx`。例: `0` → `min(max_ctx, 4096)`、`8192tail` → 8192 |
| Graph 初期化で `kv_is_host == true` | 変数を読まず `max_ctx` | 変数を読まず `max_ctx` | 値にかかわらず無視 |

計画時と Graph 初期化時で値が一致しない場合がある。たとえば自動伸長分岐で明示値が空文字なら、計画の `init_slots` は 2048 だが、Graph は同じ設定値を 4096 に clamp する。計画分岐が初期値を自動設定した場合も、Graph はその環境値を改めて読み直す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:463-475`, `engine/src/hy4flash/run/hy4_graph.hip.h:1605-1608`）。

## 有効になる条件

- 実行経路が `plan_memory` / Hy4-Flash Graph GPU runner を使うこと。値の変換は `HY4_CUDA` 分岐の内外では分けられていないが、Metal / SYCL runner には参照がない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-470`, `engine/src/hy4flash/run/hy4_graph.hip.h:1605-1608`）。
- 実際の初期確保への適用には sparse KV cache が device 配置であること。`HY4_KV_HOST` の bit 0 が立つと `kv_is_host` となり、KV は `max_ctx` 分を確保するためこの変数は無視される（`engine/src/hy4flash/run/hy4_graph.hip.h:1598-1609`）。
- `HY4_KV_DEVPOS` が正で `max_ctx` 未満なら、Graph 初期化時に `init_p` はさらにその値以下へ縮小される（`engine/src/hy4flash/run/hy4_graph.hip.h:1599-1608`）。
- `HY4_KV_NO_GROW` は計画時に既定の初期値を選び、この環境変数を自動設定する分岐を止める。ただし Graph の読み取りには条件として使われず、ユーザーが `HY4_KV_INIT_SLOTS` を設定していれば初期確保に適用される。また、実行時の `kv_grow_to` を無効にはしない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:459-475`, `engine/src/hy4flash/run/hy4_graph.hip.h:2795-2801`）。
- CLI / server から渡された context が `max_ctx` 上限になる。GPU CLI では入力された最大 context（未指定時は計画に 32768）を `plan_memory` に渡し、その後 GPU model をロードする（`engine/src/hy4flash/run/hy4_main.hip.cpp:632-659`）。GPU server も `o.max_ctx` を `plan_memory` に渡してから同じ GPU model をロードする（`engine/src/hy4flash/run/hy4_serve.hip.h:291-307`）。

## 実行時の詳細

計画時の読み取りは `plan_memory` 呼び出し中に行われる。対象条件で `max_ctx > target_init` かつ環境変数が未設定なら、計画器は初期目標値を `HY4_KV_INIT_SLOTS` に設定する。Windows では `_putenv_s`、それ以外では `setenv(..., 1)` を使う。明示値がある場合は上書きせず、計画値を clamp する。Graph の初期化時には環境を再読し、`kv_alloc_pos` と sparse cache の slot 数を決めて KV cache と IndexPool の配列を確保する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410, 463-475`, `engine/src/hy4flash/run/hy4_graph.hip.h:1602-1640`）。

初期化後はこの変数を再読しない。実行中に環境を変えても現在の cache サイズには反映されない。context 位置が足りなくなると `kv_grow_to` は `HY4_KV_STEP_SLOTS`（未設定時 16384、設定時も最低 4096）単位で拡張する。`HY4_KV_DEVPOS` 上限を越える場合、必要 VRAM が確保できない場合、または拡張時の `hipMalloc` が失敗した場合は sparse KV と IndexPool を pinned host memory に移す。context 上限 `max_ctx + 8` 超過は `kv_ensure` が false を返す（`engine/src/hy4flash/run/hy4_graph.hip.h:2795-2862, 3385`）。

この変数自体に専用エラー処理はない。GPU 確保・コピーなど `HCK` 対象の HIP 呼び出しが失敗すると stderr に `HIP error %d (%s) at %s:%d` を出し、終了コード 3 で終了する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

## ログと測定値

計画器は stderr に `[plan] ctx %d (init %d, kv=%s) chunk %d: ...` を出し、`init` に計画上の初期 slot 数を表示する。Graph 初期化は `[runner] kv cache %.2f GB (%s, init %d / ctx %d, chunk %d), device free %.1f GiB` を出し、`init` に実際の `kv_alloc_pos` を表示する。差があればこの 2 行で確認できる。拡張時は `[runner] sparse KV + IndexPool grew in VRAM: %d -> %d positions ...`、host 移行時は `[runner] sparse KV + IndexPool moved to pinned host memory (%d positions, %.2f GB, %.2f s)` を出す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`, `engine/src/hy4flash/run/hy4_graph.hip.h:1753-1756, 2793-2793, 2855-2856`）。

`docs/DETAILS.md` の KV cache 説明にはこの設定名やこの初期 slot 規則は記載されていない。ここでは測定値を記載しない。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410, 434-483` — 環境設定 helper、計画時の条件、初期値・clamp・自動設定。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:515-566` — host / device KV の計画分岐と計画ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-659` — context の決定、計画、GPU model 初期化の順序。
- `engine/src/hy4flash/run/hy4_serve.hip.h:291-307` — server の context、計画、GPU model 初期化の順序。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1596-1640, 1753-1756` — Graph 側の環境読み取り、実確保、初期化ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2771-2862, 3385` — 拡張・host 移行と context 境界。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — HIP API 失敗時の出力と終了。
