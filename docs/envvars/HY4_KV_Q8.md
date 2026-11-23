# `HY4_KV_Q8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の GPU runner が使う MLA KV cache の形式を切り替える。無効時は FP16、`atoi` が非ゼロになる設定時は圧縮 Q8 形式になり、メモリ計画と cache の確保・書き込み・attention 読み出しに同じ選択が渡る。runner は Q8 時に 1 slot 656 bytes、FP16 時に 1152 bytes として計算する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:452-458`、`engine/src/hy4flash/run/hy4_graph.hip.h:1596-1601,1611-1625`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2044-2046,2178-2184,2193-2217`）。

この環境変数を読む実装は `engine/src/hy4flash/run/` の HIP/CUDA runner だけにある。Metal runner は `--kv` を「not used」と stderr に出して読み飛ばし（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`）、SYCL runner は `--kv fp16` 以外をエラーにする（`engine/src/hy4flash/sycl/sy_main.cpp:144-150`）。この変数自体を Metal / SYCL が読む箇所はない。

## 値と判定

環境変数を読み、値全体の文字列比較ではなく `atoi(...) != 0` で判定する。未設定と空文字はどちらも 0 扱い。先頭の空白や符号を `atoi` が扱い、数値部分の後ろは検査しない。値域検査はない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:454-458`、`engine/src/hy4flash/run/hy4_graph.hip.h:1601`）。

| runner 経路 | unset | Q8 が有効になる値の例 | FP16 になる値の例 |
|---|---|---|---|
| HY4 CUDA/HIP runner | FP16 | `1`, `-1`, ` 1`, `1tail` | 空文字, `0`, `0tail`, `true`, `false`, `q8` |
| Metal / SYCL runner | この変数を読まない | 該当なし | 該当なし |

HY4 の `--kv fp16` / `--kv f16` は環境変数を `0` に、`--kv q8` / `int8` / `i8` / `k8v8` は `1` に上書きする。`--kv auto` は環境を変更せず、その時点の `HY4_KV_Q8` を使う。したがって `auto` は自動選定ではなく環境値を保持する指定である。CLI 引数は左から処理され、有効な `--kv` が複数あれば最後の書き込みが残る。未知の値は `ERR --kv <値>: expected fp16, q8 or auto` を stdout に出し、status 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:471-481`）。

## 有効になる条件

- 対象は `engine/src/hy4flash/run/` の HY4 CUDA/HIP runner。`HY4_KV_Q8` の読み取りは共通の GPU model 計画処理と HIP graph runner にあり、Metal / SYCL には読み取り実装がない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:454-458`、`engine/src/hy4flash/run/hy4_graph.hip.h:1601`）。
- GPU runner の通常の起動経路では、CLI 引数処理後に `plan_memory(...)` が環境値を読み、モデル読み込み後に `Runner::init(...)` が再び読む。よってこの経路で Q8 が有効になるのは、二つの読み取り時点で値が非ゼロである場合（または CLI が両方より前に `1` を設定した場合）である（`engine/src/hy4flash/run/hy4_main.hip.cpp:471-481,648-659,692-705`）。
- Q8 が切り替えるのは MLA KV cache の格納形式と、それに基づくメモリ見積もり。KV の初期 slot 数や GPU / host 配置を決める別設定（`HY4_KV_INIT_SLOTS`、`HY4_KV_DEVPOS`、`HY4_KV_HOST` など）は独立して判定される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:459-481,515-535`、`engine/src/hy4flash/run/hy4_graph.hip.h:1598-1625`）。

## 実行時の詳細

起動時、CLI parser は `--kv` の明示値をプロセス環境へ書き込む（Windows は `_putenv_s`、それ以外は上書き指定付き `setenv`。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410`）。その後 `plan_memory` が Q8 / FP16 の 1 slot サイズを選び、KV サイズと chunk / reserve 計画を出す。さらに `Runner::init` が同じ値を `kv_q8` に読み込み、cache buffer のサイズを決めて確保する。通常の実行中に環境変数をポーリングする処理はなく、この bool が KV 書き込み、圧縮・compact、attention 引数へ渡される（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659,692-705`、`engine/src/hy4flash/run/hy4_graph.hip.h:1601-1625,2102-2107,2140-2149,2880-2883`）。

Q8 選択時は `mla_cache_bytes` が 656-byte row を使い、KV 書き込みと speculative/tree compact で Q8 用 kernel を選ぶ。attention 側も `kv_q8` により Q8 向け kernel を選択し、fallback 経路でも Q8 用 kernel を使う（`engine/src/hy4flash/run/mla_attn.hip.cpp:2044-2046,2178-2189,2193-2217`）。

## ログと測定値

stderr の `[plan]` 行には `kv=q8` または `kv=fp16` と初期 KV 見積もりが出る。runner 初期化後は `[runner] kv cache ... (Q8, ...)` または `(FP16, ...)` の形式で実 cache サイズが出る（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`、`engine/src/hy4flash/run/hy4_graph.hip.h:1753-1756`）。

cache の `hipMalloc` / `hipMemset` が失敗すると `HCK` が `HIP error %d (%s) at %s:%d` を stderr に出し、status 3 で終了する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`、`engine/src/hy4flash/run/hy4_graph.hip.h:1613-1624`）。

ここでは速度・精度の測定値は記載しない。候補一覧は grep 由来であり、`terminal/strata_control/hy4_fit.py` の `kv_q8` は関数引数であって環境変数読み取りではない。ソース全体の完全一致検索で環境を読む実装として確認できたのは、上記 GPU model planner と graph runner の二箇所だった。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410,452-458,564-566` — CLI 設定時の環境上書き、値の parse、メモリ計画ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:471-481,648-659,692-705` — `--kv` の受理値・エラー、および計画から runner 初期化までの順序。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1596-1625,1748-1756,2102-2107,2140-2149,2880-2883` — runner 側の読み取り、cache 確保と KV 処理への伝播、実行時ログ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — HIP API エラーの stderr 出力と終了 status。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:2044-2046,2178-2189,2193-2217` — row byte 数と Q8/FP16 の write・compact・attention 分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`、`engine/src/hy4flash/sycl/sy_main.cpp:144-150` — 別 backend の `--kv` 扱い。
