# `strata-hy4-sycl --cpu-hi`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（通常実行および `--serve`） |
| オプション | `--cpu-hi` |
| 別名 | なし |
| 値 | 値を取らない真偽スイッチ |

## 役割

Hy4-Flash の SYCL runner で expert の活性値計算を高精度側に切り替えます。名前はCPU向けですが、共通の expert pool 初期化に渡されるため、CPU上の expert に加えて primary GPU のVRAM cacheとpeer GPU cacheの計算経路にも作用します。CPU経路では活性値の残差項を加える2項Q8_1方式、GPU cache経路ではQ8活性値カーネルに代わるFP32/FP16活性値カーネルが選ばれます（`engine/src/hy4flash/sycl/sy_main.cpp:143,237,304`、`engine/src/hy4flash/sycl/sy_graph.h:123-152,214-215`、`engine/src/hy4flash/sycl/sy_vram_cache.h:491-493,903-927`）。

## 使い方

```sh
# 単発実行で高精度活性値経路を指定
strata-hy4-sycl --model SQ32.strata --tokens ids.txt --cpu-hi

# line protocol の serve 実行にも同じ指定を渡す
strata-hy4-sycl --serve --native SQ.strata --cpu-hi
```

## 値と既定値

- 値は不要です。parser は引数文字列が `--cpu-hi` と一致したときに内部フラグを `true` にします。別名や値の validation はありません（`engine/src/hy4flash/sycl/sy_main.cpp:107-116,143`）。
- 指定を省略した場合、CLI側の `hi_act` は `false` です。複数回指定しても同じ `true` を設定するだけです（`engine/src/hy4flash/sycl/sy_main.cpp:99,143`）。
- `--cpu-hi` の後ろに値を置く書式ではありません。例えば `--cpu-hi 0` はフラグを有効にした後、`0` を未知の引数として扱います（未知引数の処理は `engine/src/hy4flash/sycl/sy_main.cpp:190-197`）。
- この runner には別の `--expert-act 0` 指定もあり、単発実行と `--serve` の両方で `hi_act` を有効にします。判定は `--cpu-hi` と `expert_act == 0` の論理和なので、`--expert-act 1` を併記しても `--cpu-hi` を打ち消しません。`expert_act` の初期値は `1` です（`engine/src/hy4flash/sycl/sy_main.cpp:104,160,237,304`）。
- `--cpu-hi` を省略した場合のCPU expert経路は、CPU kernel選択時の初期値と `STRATA_CPUEXP_ACT=hi|q8` にも左右されます。`--cpu-hi` 指定時は `ucx.init()` 後に `set_hi_activations(true)` が呼ばれるため、環境変数で `q8` を選んでいてもCPU経路を高精度側にします（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1857-1862`、`engine/src/hy4flash/sycl/sy_graph.h:214-215`）。環境変数の説明は [`STRATA_CPUEXP_ACT`](../../../envvars/STRATA_CPUEXP_ACT.md) を参照してください。GPU cache経路はCLI側の `hi_act` から直接設定されます。

## 実行時の動作

通常実行では `hi_act || (expert_act == 0)` が expert pool の初期化へ渡されます。`--serve` では同じ条件で `ServeOpts::hi_act` を設定し、serve側も共通初期化関数を呼びます（`engine/src/hy4flash/sycl/sy_main.cpp:215-248,298-306`、`engine/src/hy4flash/sycl/sy_serve.h:28-40,280-285`）。

共通初期化はフラグを反転してVRAM expert cacheとpeer GPU cacheの `q8_act` 設定に渡し、CPU expert poolではフラグが真のとき `set_hi_activations(true)` を呼びます（`engine/src/hy4flash/sycl/sy_graph.h:123-152,214-215`）。VRAM cacheでは偽のときQ8量子化とQ8カーネル、真のときFP32入力を使うFP32/FP16カーネル群が選ばれます（`engine/src/hy4flash/sycl/sy_vram_cache.h:903-927`）。peer GPU cacheも `q8_act_` に応じてテンプレートのQ8活性値経路を選択します（`engine/src/hy4flash/sycl/sy_peer.h:576-588,609-610`）。CPU側は `hi` がジョブへ渡され、入力・中間活性値の残差項を計算・加算する分岐に使われます（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2311-2336,2355-2372,2395-2403,2595-2612,3117`）。

## 適用条件と副作用

- 対象は `strata-hy4-sycl` の通常実行と `--serve` です。expert をCPU RAM、primary GPU VRAM、peer GPU のどこで処理するかは pool の配置結果に依存します。このオプションはその配置予算を変更せず、各配置先での活性値計算経路を変えます（`engine/src/hy4flash/sycl/sy_graph.h:118-126,142-152,173-201`）。
- 高精度側の具体的な計算は配置先で同一ではありません。CPU APIの説明では残差量子化を含む2項Q8_1方式、SYCL VRAM/peer cache側はそれぞれのFP32活性値入力カーネルです。性能向上を保証するソース上の根拠は確認できません。
- CPU設定は初期化後に適用される `set_hi_activations(true)` であり、実行中ジョブがあれば待機してから切り替えるAPIです（`engine/src/hy4flash/run/hy4_cpu_experts.h:103-108`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:3165-3168`）。このCLIでは初期化時に呼ぶため、モデル実行前の設定です。

## 出力とエラー

- 成功時、共通初期化はstderrの `[experts] unified pool (...)` 診断に最終的なCPU expert活性値状態を `act=hi` と表示します（`engine/src/hy4flash/sycl/sy_graph.h:229-234`）。
- フラグ自体に専用の拒否条件はありません。未知の引数は `unknown arg ...` をstderrへ出して終了コード2になります（`engine/src/hy4flash/sycl/sy_main.cpp:190-197`）。expert pool初期化に失敗した場合、通常実行は `experts: ...` をstderrへ出して1、serveはline protocolへ `ERR experts: ...` を出して1を返します（`engine/src/hy4flash/sycl/sy_main.cpp:304-306`、`engine/src/hy4flash/sycl/sy_serve.h:283-285`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99,104,107-116,143,160,190-197` — 内部既定値、引数の受理、関連する `--expert-act`、未知引数の処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,298-306`、`engine/src/hy4flash/sycl/sy_serve.h:28-40,280-285` — 通常実行とserveへの値の伝達および初期化失敗経路。
- `engine/src/hy4flash/sycl/sy_graph.h:118-152,204-235` — expert配置、CPU/GPU cacheへの設定、診断出力。
- `engine/src/hy4flash/sycl/sy_vram_cache.h:491-493,664-665,903-927`、`engine/src/hy4flash/sycl/sy_peer.h:576-610` — GPU cacheのQ8/非Q8活性値計算経路。
- `engine/src/hy4flash/run/hy4_cpu_experts.h:98-108`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1857-1865,2311-2336,2355-2372,2395-2403,2595-2612,3117,3165-3169` — CPU側の既定値・環境変数・高精度活性値計算と設定API。
