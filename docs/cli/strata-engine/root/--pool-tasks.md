# `--pool-tasks`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数。Terminal CLI の wrapper ではない） |
| オプション | `--pool-tasks` |
| 別名 | なし |
| 値 | 整数 `N`、`0..4096` |

## 役割

バッチ処理される CPU expert の Gate/Up と Down の各行フェーズを、いくつの row task に分割するか指定します。task 数を指定するオプションであり、CPU pool の worker 数を指定するものではありません。worker 数は `--pool-workers` が担当します。parser の説明と `ExpertPool` の引数・task 数計算は `src/program/generate.cpp:1030-1031` と `src/kernels/cpu/pool.hpp:199-202` にあります。

## 使い方

```sh
strata --native /path/to/model.gguf --pool-tasks 192
```

`--native` とモデル指定は例の実行文脈です。`--pool-tasks` は値を1つ取ります。モデルを読み込んだあと、起動時に実際の pool に値が渡されます（`src/program/generate.cpp:5971-5978`）。

## 値と既定値

- 省略時の内部値は `0` です。`0` は自動設定で、各 row phase の task 数は参加 thread 数の3倍になります。既定では host thread も pool の drain に参加するため、thread 数は `workers + 1` です（`src/program/generate.cpp:519`、`src/kernels/cpu/pool.cpp:1316-1318`、`src/program/generate.cpp:5973-5977`）。
- `1..4096` は各 row phase の目標 task 数です。通常の batched path では、その phase の総行数を超えないよう `min(行数, N)` に制限されます（`src/kernels/cpu/pool.cpp:1316-1318`）。
- 同じ引数を複数回指定した場合は parser が都度同じ値を上書きするため、最後の指定が残ります（`src/program/generate.cpp:2416-2421`、`src/program/generate.cpp:2511-2519`）。
- NUMA slice を使う native row path では、明示値を2 slice に共有し、各 slice に `max(1, N / 2)` を割り当てたうえで slice 内の行数を上限にします。従って奇数値や小さい slice では、全 slice の合計 task 数が指定値と一致しないことがあります（`src/kernels/cpu/pool.cpp:1086-1100`）。

## 実行時の動作

parser は値を `strtol` で10進整数として読み、変換できたこと、数値の後ろに未変換文字が残らないこと、`0..ExpertPool::kMaxTasks` の範囲内であることを検査します。従って空値、整数でない値、末尾に文字が付いた値、範囲外の値は受け付けません。`strtol` が許す先頭空白や符号付き表記は parser 独自には拒否されません（`src/program/generate.cpp:2511-2519`、上限定義は `src/kernels/cpu/pool.hpp:201-202`）。

通常の batched multi-token path は Gate/Up と Down それぞれの総行数から task 数を決めて pool に渡します（`src/kernels/cpu/pool.cpp:1320-1349`）。native path は各 expert batch の `n_ff` 行と `n_embd` 行を別々の phase として処理し、指定 task 数を各 phase に適用します（`src/kernels/cpu/pool.cpp:1359-1380`）。task は連続した行範囲に分割され、複数 worker が処理します（`src/kernels/cpu/pool.cpp:1200-1216`、`src/kernels/cpu/pool.cpp:1248-1265`）。

`--pool-affinity measure` を併用すると、起動時の `all` / `p-cores` 比較で作る測定用 pool にも同じ task 数が渡ります（`src/program/generate.cpp:2088-2128`、`src/program/generate.cpp:5971-5974`）。この値は行の割り当て粒度を変えます。ソースから性能の向上を一律に保証することはできません。

## 適用条件と副作用

- この指定は pool の worker 数、CPU affinity、カーネル自体を変更しません。変えるのは複数行 row phase の分割数です（`src/kernels/cpu/pool.cpp:1212-1216`）。
- single-token の `run()` / `run_split()` 経路は `tasks_` を参照せず、従来の job 単位で処理します（`src/kernels/cpu/pool.cpp:1300-1318`）。oracle Q8_0 有効時や multi path の容量超過時は single-token 経路へ fallback するため、そこで `--pool-tasks` は row 分割を制御しません（`src/kernels/cpu/pool.cpp:1300-1303`、`src/kernels/cpu/pool.cpp:1320-1335`）。
- `--no-pool` を指定した実行では CPU pool の仕事を無効化するため、この task 数設定は実処理に使われません。起動ログにも `UNUSED: --no-pool` と表示する分岐があります（`src/program/generate.cpp:6928-6936`）。
- `generate.cpp` が通常 parser に入る前に Qwen3.5 専用 engine へ引数を転送する場合、専用 parser は `--pool-tasks` を定義していません。通常の実行では未知引数として usage を出して終了コード `2` になります。専用 parser がその引数を読む時点ですでに `--serve` を処理している場合は、未知の `--` 引数を値とともに無視し、stderr に警告を出すため、設定しても効果はありません（振り分け: `src/program/generate.cpp:2393-2407`、専用 parser: `src/qwen35/q36_engine.cu:3742-3753`、未知引数処理: `src/qwen35/q36_engine.cu:3782-3795`）。

## 出力とエラー

- 値を省略すると `--pool-tasks needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。
- 整数でない値、`0..4096` の範囲外の値では `strata generate: --pool-tasks expects an integer in 0..4096 (0 = automatic)` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2514-2518`）。
- pool 起動後、stderr に `CPU pool tasks/phase` と参加 thread 数を出します。`0` の場合は自動 task 数、明示値の場合は「capped by rows」と表示します（`src/program/generate.cpp:5973-5978`）。NUMA slice 経路での実際の slice ごとの件数は、この表示だけでは分かりません。

## 根拠

索引では `strata-engine` のトップレベル parser (`src/program/generate.cpp`) に属する option として掲載されています（`docs/cli/README.md`）。上記の説明は同一 checkout の parser、pool 実装、Qwen3.5 の委譲先 parser を確認したものです。既存バイナリの `--help` は実行していません。
