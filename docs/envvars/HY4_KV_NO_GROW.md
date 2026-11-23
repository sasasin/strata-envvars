# `HY4_KV_NO_GROW`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の CUDA/HIP GPU 実行で、planner が単一 GPU の小容量カード向けに KV cache を初期枠から段階的に増やすための既定値を自動設定するかを制御する。`plan_memory` の自動 elastic 初期化分岐に入らなくなるだけで、KV の伸長処理そのものを禁止するフラグではない。実装は `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-481` にある。

## 値と判定

値の文字列は変換・比較されず、`getenv("HY4_KV_NO_GROW")` が null かどうかだけを調べる。したがって未設定ならこの条件では無効、空文字を含む何らかの設定値があれば有効（自動 elastic 初期化を抑止）となる。`0`、`1`、`true`、`false`、`0anything` はいずれも「設定あり」と同じ扱いであり、大文字小文字・前後空白・数値としての妥当性も検査しない（同:465）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP Hy4-Flash の単一 GPU、総 VRAM が 44 GiB 未満 | planner の自動設定分岐に入る | 空文字、`0`、`1`、`true` など、環境変数が存在する任意の文字列 | なし（値の内容を見ない） |
| 複数 GPU、または総 VRAM が 44 GiB 以上 | この分岐自体に入らず、変数の有無は影響しない | 同左 | 同左 |

未設定かつ分岐に入る場合、`max_ctx` が VRAM 容量別の目安（9.0 GB 以下なら 4096、13.5 GB 以下なら 8192、それ以外なら 16384）を超えると、planner は `HY4_KV_INIT_SLOTS` と `HY4_KV_STEP_SLOTS` が未設定の場合に限り、それぞれの値を環境へ設定する。`HY4_KV_NO_GROW` が存在すると、この planner による両変数の自動設定を行わない（同:463-481）。

## 有効になる条件

- この変数を読むのは `plan_memory` だけで、Hy4-Flash GPU エンジンの CUDA/HIP ビルドが対象。CMake では `STRATA_BUILD_HY4` が既定 OFF で、ON にする場合 CUDA または HIP が必要とされ、`hy4_main.hip.cpp` をどちらかの言語でコンパイルする（`engine/CMakeLists.txt:846-852,884-890`）。Metal/SYCL の専用実装にこの参照はない。
- planner 分岐が適用されるのは `multi_gpu == false` かつ `total < 44ull << 30`（44 GiB 未満）のときだけ（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:465`）。単一実行経路では `hy4_main.hip.cpp`、サーバー経路では `hy4_serve.hip.h` が planner をモデル読込前に呼ぶ（それぞれ `:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295`）。
- `HY4_KV_INIT_SLOTS` と `HY4_KV_STEP_SLOTS` は `HY4_KV_NO_GROW` とは独立して後段が読み取る。手動で設定されていると、`HY4_KV_NO_GROW` が存在していても初期枠を `HY4_KV_INIT_SLOTS` で制限したり、`HY4_KV_STEP_SLOTS` に従って増分拡張したりできる（`engine/src/hy4flash/run/hy4_graph.hip.h:1596-1609,2795-2801`）。したがって本変数単独では、すでに設定されたこれらの値を消去・上書きしない。
- `HY4_KV_DEVPOS` や `HY4_KV_HOST` など他の KV 配置条件も別途処理される。`HY4_KV_NO_GROW` はそれらの判定を抑止しない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:517-535`）。

## 実行時の詳細

読み取りは `plan_memory` の呼出し時に行われ、関数内 cache はない。CLI 実行とサーバーのモデル初期化でこの planner が呼ばれ、その後 `load_gpu_model` に進む（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295`）。分岐に入ると、未設定時の `init_slots` は `max_ctx` から上記の目安値に下げられ、`kv_step` もその目安値に設定される。上限コンテキストが目安以下なら初期枠は下げず、`HY4_KV_INIT_SLOTS` の自動設定もしないが、未設定の `HY4_KV_STEP_SLOTS` は自動設定される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:463-481`）。

`HY4_KV_NO_GROW` が設定されている場合、この planner 分岐を丸ごと飛ばすため、ここでは初期枠を縮めず `init_slots` は `max_ctx` のまま、増分幅の planner 自動設定も行わない。その後の Runner は、`HY4_KV_INIT_SLOTS` があれば `max_ctx` との小さい方（最低 4096 に丸めた値）を初期枠に使い、なければ `max_ctx` 全体を使う（`engine/src/hy4flash/run/hy4_graph.hip.h:1602-1610`）。

Runner の `kv_grow_to` は `HY4_KV_NO_GROW` を参照しない。必要位置が割当済み枠を超えると、`HY4_KV_STEP_SLOTS`（未設定なら既定 16384、設定値は最低 4096）を使って拡張先を決める。VRAM が不足すれば expert cache の VRAM 解放を試み、その後も不足なら pinned host memory へ移し、確保失敗時にも同じ移行経路を使う（同:2795-2833）。したがって `HY4_KV_NO_GROW` に加えて `HY4_KV_INIT_SLOTS` が設定されず、`HY4_KV_DEVPOS` による上限もない場合は、初期枠が `max_ctx` となり段階拡張は起きない。別途 `HY4_KV_INIT_SLOTS` または有効な `HY4_KV_DEVPOS` で枠を小さくした場合は、この grow 経路が後で動き得る。

## ログと測定値

`HY4_KV_NO_GROW` 専用のログ、警告、エラー文言はない。planner は stderr に `[plan] ctx ... (init ..., kv=...) ...` を出し、計画した初期枠などを表示する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`）。段階拡張が実際に行われれば `[runner] sparse KV + IndexPool grew in VRAM: ...`、ホストメモリ移行が起きれば `[runner] sparse KV + IndexPool moved to pinned host memory ...` が stderr に出る（`engine/src/hy4flash/run/hy4_graph.hip.h:2793,2855-2856`）。対象変数による性能測定値は確認できない。

## 根拠

- 対象変数の唯一の直接参照と planner 条件・自動設定: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:459-481,564-566`
- CUDA/HIP のビルド条件とソース登録: `engine/CMakeLists.txt:846-852,884-890`
- CLI / serve から planner を呼ぶ位置: `engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:291-295`
- Runner の初期 slot 選択と拡張処理: `engine/src/hy4flash/run/hy4_graph.hip.h:1596-1625,2795-2833,2855-2862`
