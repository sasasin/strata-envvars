# `--no-host-worker`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数。索引上の scope は `root/`） |
| オプション | `--no-host-worker` |
| 別名 | なし |
| 値 | 値なしの真偽フラグ |

## 役割

通常の engine 実行経路で、CPU expert pool の drain（CPU expert の仕事を処理する区間）に host thread を参加させないためのフラグです。既定では pool の worker thread に加えて host thread も job を取り、指定すると worker thread だけが job を処理します。worker 数そのものや host thread の存在を無効化する指定ではありません。

## 使い方

```sh
# 通常の engine 実行で host thread を CPU expert pool の drain から外す
strata generate --pack ./pack --tokens "1,2,3" --no-host-worker
```

エンジンの usage は `--pack DIR` と `--tokens LIST`（または `--tokens-file PATH`）を示しています。モデルやトークン入力など、実行に必要な引数は環境に合わせて指定してください（`engine/src/program/generate.cpp:1208-1214`）。

## 値と既定値

値は取りません。通常 parser は引数が文字列 `--no-host-worker` と一致したとき `o.no_host_worker = true` とし、値の変換・validation は行いません（`engine/src/program/generate.cpp:3976`、SYCL parser は `engine/sycl/src/program/generate.cpp:1994`）。オプション構造体の初期値は `false` です（`engine/src/program/generate.cpp:869-872`、`engine/sycl/src/program/generate.cpp:547-550`）。従って未指定時は host 参加が有効です。同じフラグを複数回指定しても同じ `true` を設定するだけで、重複エラーにはなりません。

## 実行時の動作

通常の CUDA/HIP engine 経路では `!o.no_host_worker` を `ExpertPool` の `host_works` 引数に渡します。`--pool-affinity measure` の起動時測定にも同じ値を渡すため、比較測定時にも host の参加条件が反映されます（`engine/src/program/generate.cpp:9001-9004`）。SYCL 経路でも同じ否定値を `ExpertPool` に渡します（`engine/sycl/src/program/generate.cpp:4803`）。

`ExpertPool::run()` は `host_works_` が真の場合に host thread 自身が job を claim して処理し、偽の場合はその処理をせず、worker の完了を待ちます（`engine/src/kernels/cpu/pool.cpp:1765-1795`）。したがってこのフラグは pool worker の数・CPU affinity を直接指定するものではなく、drain に参加する thread 構成を変えます。起動時の `CPU pool tasks/phase` と `participating threads` の表示も `pool.host_works()` を用いて算出されます（`engine/src/program/generate.cpp:9005-9008`）。`--pool-tasks` が 0 の場合は自動タスク数も参加 thread 数から計算され、明示値の場合はその式を使いません（`engine/src/kernels/cpu/pool.cpp:1516-1517`）。

`--pool-workers` と併用できます。worker 数の決定は `ExpertPool` 側の設定に従い、このフラグは host 参加分だけを切り替えます（`engine/include/strata/kernels/cpu/pool.hpp:186-200`）。性能が改善するかどうかは CPU・モデル・workload に依存し、このソース調査だけからは断定できません。

`STRATA_NUMA_SPLIT` による pool の NUMA 分割判定では、worker 数に host 参加分を足した thread 数を使い、参加する場合は host core も分割判定へ含めます（`engine/src/kernels/cpu/pool.cpp:932-944`）。また Terminal の tuning helper は本フラグを値なしの boolean flag として分類しています（`terminal/strata_control/tune_knobs.py:48-52`）。

## 適用条件と副作用

通常 parser が実行される engine 経路では CUDA/HIP 実装と SYCL 実装の両方にこのフラグがあります。出力・ログに関しては、通常経路で pool の参加 thread 数表示が変わり、host が drain に参加しない場合は配置表示の「draining too」が付きません（`engine/src/program/generate.cpp:9029-9034`）。ファイルやネットワークへの副作用はこのフラグの使用箇所からは確認できません。

例外として、Qwen3.6-35B-A3B は `--model` / `--native` の GGUF header から判定され、通常 parser より前に `strata::qwen35::run()` へ分岐します（`engine/src/program/generate.cpp:3804-3818`）。この別 parser に `--no-host-worker` の処理はありません（`engine/src/qwen35/q36_engine.cu:5339-5363`）。その経路では one-shot 実行時に未知引数として usage を出して終了コード 2 になります。`--serve` が先に解析されている場合は、未知の `--` 引数として警告を出して無視します（`engine/src/qwen35/q36_engine.cu:5405-5417`）。このモデル経路では本オプションによる host 参加の切り替えは確認できません。

## 出力とエラー

通常 parser では本フラグ固有の validation error はありません。通常 parser が受け取らない引数は `unknown argument: ...` と usage を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274`）。本フラグの後ろに値らしい文字列を置いても値として消費されず、その文字列は別引数として処理されます。

Qwen3.6-35B-A3B 経路の未知引数の扱いは実行モードと引数順に依存します。`--serve` より前、または one-shot 経路では usage を stderr に出して終了コード 2、`--serve` の後なら `strata-q36: ignoring ...` の警告を stderr に出して続行します（`engine/src/qwen35/q36_engine.cu:5405-5417`）。

## 根拠

- `engine/src/program/generate.cpp:869-872` — 通常 parser のオプション状態と初期値。
- `engine/src/program/generate.cpp:1440-1442`、`3976` — usage 上の説明と parser 登録。
- `engine/src/program/generate.cpp:9001-9008`、`9029-9034` — affinity 測定・pool 構築への値の転送、起動時表示。
- `engine/sycl/src/program/generate.cpp:547-550`、`997-999`、`1994`、`4803` — SYCL 側の状態、usage、parser、pool 構築。
- `engine/include/strata/kernels/cpu/pool.hpp:189-200`、`225-227`、`engine/src/kernels/cpu/pool.cpp:1765-1795` — `host_works` の意味と drain 実装。
- `engine/src/kernels/cpu/pool.cpp:1516-1517` — 自動タスク数と参加 thread 数の関係。
- `engine/src/kernels/cpu/pool.cpp:932-944` — NUMA 分割時に使う参加 thread 数と host core。
- `terminal/strata_control/tune_knobs.py:48-52` — tuning helper における値なし boolean flag の分類。
- `engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_engine.cu:5339-5363`、`5405-5417` — Qwen3.6-35B-A3B の parser 分岐と未知引数の処理。
- `engine/src/program/generate.cpp:4268-4274` — 通常 parser の未知引数エラー。
