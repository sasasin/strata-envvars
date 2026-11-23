# `HY4_KV_HOST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の GPU 実行で、疎層の KV cache と IndexPool 用データを VRAM ではなく pinned host memory に置く計画・割り当てを制御する整数ビットマスクです。通常は `plan_memory` が GPU 容量・コンテキスト長などからマスクを決めますが、環境変数が設定されている場合は `atoi` の結果でその自動値を置き換えます。設定値は CLI 引数からは上書きされません。通常のトークン計算そのものを切り替える設定ではなく、主にこれらのバッファの配置先を変えます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-438, 511-535`）。

コード上のビット定義コメントは `1` = sparse KV rows + Vt、`2` = absorbed `wk_b/wv_b`、`4` = IndexPool state です。ただしこの commit の `dalloc_big` 呼び出しを全件確認すると、実際の呼び出しはビット `1` の sparse KV cache とビット `4` の IndexPool のみで、ビット `2` の呼び出しはありません。さらに IndexPool の host 分岐自体が `kv_is_host`（ビット `1`）で選ばれるため、現行コードでは `4` 単独では IndexPool を host に移しません（`engine/src/hy4flash/run/hy4_graph.hip.h:1242-1247, 1613-1640`）。

## 値と判定

読み取りは `getenv("HY4_KV_HOST")` の設定有無確認と `atoi` です。文字列全体の検証はなく、`atoi` が数値として読める先頭部分だけを使います。表の「実際の割り当て」はこの commit の分岐を示します。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `plan_memory` のマスク選択 | GPU メモリ計画から自動算出し、結果をプロセス環境へ設定 | `1`、`5` など数値文字列。設定値は自動マスクを置換 | 空文字、`true`、`abc` は `atoi` で `0`。`0anything` も `0`。設定済み扱いなので自動算出値は使われない |
| ビット判定 | 自動算出値を利用 | `1`（または `1` ビットを含む値）で sparse KV を host 側へ。`5` は IndexPool も強制 host にする | `0` は強制なし。`4` は IndexPool の host 分岐に入らないため単独では効果なし |

`atoi` は大文字小文字の概念を持たず、`true` 等を真偽値として解釈しません。先頭空白や符号は C の `atoi` の数値変換に従い、たとえば ` 1tail` は `1`、`-1` は負の整数です。負値や未知のビットを拒否する範囲検査はありません。ビット判定は `(mask & bit) != 0` です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:530-535`, `engine/src/hy4flash/run/hy4_graph.hip.h:1247-1252`）。

空文字は `getenv` では「設定あり」ですが、`atoi("")` は `0` です。このため自動マスクを抑止して強制ビットなしになります。通常 unset 時に計画が host 配置を必要と判断する場合とは結果が異なり、VRAM 側の割り当てが失敗する可能性があります。

## 有効になる条件

- 対象は `engine/src/hy4flash/run/` の HY4 GPU runner/server です。単体実行は `hy4_main.hip.cpp` から、serve 起動は `hy4_serve.hip.h` から同じ `plan_memory` を呼びます（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-659`, `engine/src/hy4flash/run/hy4_serve.hip.h:270-295`）。この名前の読み取りは調査対象ソース内ではこれらの共有 HIP/CUDA 実装に限られ、CPU-only 経路で読む箇所はありません。
- `plan_memory` は GPU 容量、空き容量、最大コンテキスト、multi-GPU、chunk などから初期マスクを計算します。初期マスクが `1` ビットを含み、環境変数が未設定なら、VRAM 内に部分 KV を収められる条件（`dev_pos >= 4096 && dev_pos < max_ctx && trunk_in_vram > 0`）ではマスクを解除して `HY4_KV_DEVPOS` を設定します。設定済み `HY4_KV_HOST` はこの自動 fallback 判定後に読み直され、マスクを置換します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:511-535`）。
- bit `1` が実効になると sparse KV cache の runner 初期化が host allocation 分岐に入ります。IndexPool も同じ host 分岐に入りますが、`dalloc_big` 内でビット `4` が立っている場合だけ IndexPool を強制 host にし、そうでなければ空き VRAMが対象サイズに 300 MiB を足した量を超える場合に限って VRAM を試し、足りなければ host に fallback します（`engine/src/hy4flash/run/hy4_graph.hip.h:1247-1270, 1596-1640`）。
- 値の取得・マスク設定は計画時、再確認は runner の初期化・各 `dalloc_big` 呼び出し時です。static cache はありませんが、確保後の配置を実行中に変更する読み取り箇所はありません。未設定時に自動設定した値は `setenv` / `_putenv_s` で同一プロセス環境に書き込まれます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410, 520-535`）。

## 実行時の詳細

`plan_memory` は未設定時、容量見積もりで sparse KV rows と IndexPool が収まらないと見込むと bit `1` を立てます（自動マスクは `0` または `1` です）。状況により `HY4_KV_DEVPOS` による部分 VRAM 常駐案も選びます。その後 `HY4_KV_HOST` が存在すれば `atoi` の値を使い、存在しなければ自動マスクを文字列化して環境へ設定します。stderr の `[plan]` 行には `host mask %d` と reserve 値が出ます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:511-566`）。

Runner 初期化では再度マスクを読み、bit `1` を `kv_is_host` に反映します。bit `1` がなければ sparse KV は `hipMalloc` され、KV の割り当て上限は `max_ctx` を基準に `HY4_KV_INIT_SLOTS` と `HY4_KV_DEVPOS` で小さくなる場合があります。bit `1` があれば sparse KV は最大コンテキスト分を `dalloc_big` で確保します。IndexPool も同じ `kv_is_host` 分岐で device または `dalloc_big` に進みます（`engine/src/hy4flash/run/hy4_graph.hip.h:1596-1640`）。

`dalloc_big` は強制 host でない場合、空き VRAMが `bytes + 300 MiB` を超えると device allocation を試みます。それ以外、または `hipMalloc` が失敗した場合は pinned mapped host memory を確保し、GPU が参照する device pointer を返して `[runner] <対象>: %.2f GB in pinned host memory (read by the GPU)` を出します。強制 host の場合はこの VRAM 試行を飛ばします（`engine/src/hy4flash/run/hy4_graph.hip.h:1247-1270`）。

## ログと測定値

- 計画時に `[plan] ... -> host mask %d; reserve %s GiB` が stderr に出ます。明示値が無効文字列や空文字でも、ログ上の mask は `atoi` の結果 `0` です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`）。
- host memory を実際に確保した `dalloc_big` ごとに `[runner] %s: %.2f GB in pinned host memory (read by the GPU)` が stderr に出ます。device allocation が成功したとき、この行は出ません（`engine/src/hy4flash/run/hy4_graph.hip.h:1253-1269`）。
- HIP allocation / mapped pointer 取得が `HCK` で失敗すると、`HIP error %d (%s) at %s:%d` を stderr に出して終了コード `3` で終了します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`, `engine/src/hy4flash/run/hy4_graph.hip.h:1264-1267`）。
- 調査対象の `docs/DETAILS.md` と `docs/` を確認しましたが、この変数の説明や条件付き測定値は見つかりませんでした。コード上の動作以外の速度・品質効果は記載していません。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:402-410` — 自動設定の意図、環境変数設定 helper。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:511-566` — 自動 mask、`HY4_KV_DEVPOS` fallback、明示値優先、ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1242-1270` — bit コメント、整数判定、VRAM / pinned host 配置。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1596-1640` — runner 初期化での読み取り、KV と IndexPool の確保分岐。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:617-659`, `engine/src/hy4flash/run/hy4_serve.hip.h:270-295` — 単体 CLI と serve の計画呼び出し。
