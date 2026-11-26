# `--kv-resident`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数。索引では `strata` の root scope） |
| オプション | `--kv-resident` |
| 別名 | なし |
| 値 | `N`: 10 進整数。各 QSA 層で VRAM に保持する KV cell 数。`0` は通常全 KV を VRAM に置く。 |

## 役割

各 QSA 層の KV cache の一部を VRAM に置き、残りを pinned host RAM に置いて必要なブロックを読み戻す KV streaming を設定する。長い context で KV が占める VRAM を抑え、その分を expert cache などに回せる一方、全 KV 分の pinned RAM が必要になり、host と GPU 間の転送も発生する。オプション値はセッション初期化前に設定される。

## 使い方

```sh
# 32,768 cells を各 QSA 層の VRAM resident window にする
strata generate --pack ./pack/full --tokens "1,2,3" --kv-resident 32768
```

## 値と既定値

- `N` が省略された場合の parser 既定値は `0`。値が後続引数にない場合は stderr に `--kv-resident needs a value` を出して終了コード 2 で終了する。値は `std::atoll` で整数化され、負数は後段の validation で拒否される（`engine/src/program/generate.cpp:825,3842-3847,3907,5028-5032`、SYCL parser: `engine/sycl/src/program/generate.cpp:509,1882-1887,1946,2542-2546`）。
- 数値形式の厳密な検査はなく、`std::atoll` が整数として読めない値は `0` になり、数値の後ろにある非数字は値の解析を止める（同 parser 箇所）。
- 同じ引数を複数回渡すと parser は順に同じフィールドへ代入するため、最後の値が使われる（上記 parser 分岐）。
- `N < 0` は stderr に `strata generate: --kv-resident must be >= 0` を出して終了コード 2。`N = 0` は共通設定関数で全 VRAM 常駐を意味するが、下記の SYCL 自動選択条件では自動値を選ぶ合図にもなる（`engine/src/core/layer.cpp:769-785`; `engine/sycl/src/core/layer.cpp:753-755`）。
- 正数は要求値として保持される。実際の resident page 数はページ単位に切り上げられ、実装下限より小さい正数は下限へ引き上げられる。context の全 cell 数がその window 以下なら streaming にはならない（`engine/src/core/layer.cpp:738-755,771-785`; `engine/sycl/src/core/layer.cpp:722-739,753-755`）。
- 通常の CUDA/HIP 実装での下限は 4096 cells（`STRATA_KV_RESIDENT_MIN` が 1024 以上ならその値で上書き）。Metal は既定 20480 cells。同名 help 表示は「min 20480」としているが、CUDA/HIP の現行ソース実装とは一致しない（`engine/src/program/generate.cpp:1235-1237`; `engine/src/core/layer.cpp:771-785`）。SYCL 実装の下限は 20480 cells（`engine/sycl/src/core/layer.cpp:753-755`）。

## 実行時の動作

- parser は値を `Options::kv_resident` に取り込み、負数 validation 後に `qsa_set_kv_resident` へ渡す（CUDA/HIP: `engine/src/program/generate.cpp:825,3907,5028-5032`; SYCL: `engine/sycl/src/program/generate.cpp:509,1946,2542-2546`）。
- CUDA/HIP では正数かつ context が値より大きい場合、QSA 層ごとの KV 全体を pinned host copy として確保し、resident window を VRAM に割り当てる。選択された attention block を読み出す前に必要な block を resident にする。値が `0` 以下なら全 KV を VRAM に置く（`engine/src/core/layer.cpp:738-755,920-942,1284-1285`; `engine/include/strata/core/layer.hpp:234-237,288-292`）。
- SYCL では `N <= 0`、`--max-context > 20480`、単一 GPU、`--kv-grow` 無効、expert cache 有効、unified-memory device ではない、という条件で VRAM 容量を検査し、自動的に streaming window を選ぶ。候補は 65536、32768、20480 cells の順で、収まる最大値を選び、どれも収まらない場合は 20480 を選ぶ。RAM の空きが算出した KV streaming 必要量に届かない場合は自動選択を取り消し、stderr に理由を出す。したがって、この条件下では明示的な `--kv-resident 0` も自動選択を止めない（`engine/sycl/src/program/generate.cpp:4234-4277`; `engine/sycl/include/strata/core/short_cache.hpp:42-50`）。
- `--kv int8`、`q4_0`、`k8v4` などの KV 格納形式と組み合わせ可能。streaming は KV 全体の形式を変えず、その host copy と VRAM window に適用される（`engine/src/program/generate.cpp:1230-1237,5020-5027`; `engine/src/core/layer.cpp:757-765`）。
- `--kv-grow` は「全 KV を VRAM に置き、必要に応じて割り当てる」別方式で、CUDA/HIP では `--kv-resident` が正数だと有効条件を満たさない（`engine/src/program/generate.cpp:7715-7729`; `engine/include/strata/core/layer.hpp:288-297`）。

## 適用条件と副作用

- QSA 層を持つモデルの KV state に作用する。context が指定値以下なら streaming mode にならない。MTP drafter の KV ring にも streaming の仕組みがあるが、ring window は別途 drafter の window 値から sizing される（`engine/src/core/layer.cpp:743-755`; `engine/sycl/src/core/layer.cpp:727-739`; `engine/include/strata/core/layer.hpp:288-292`）。
- streaming 時は KV 全体に対応する pinned host memory を確保する。CUDA/HIP は CUDA host allocation / registration を試し、失敗時は別方式へ fallback する。SYCL は `sycl::malloc_host` を使う（`engine/src/core/layer.cpp:577-620,925-942`; `engine/sycl/src/core/layer.cpp:917-927`）。
- pinned RAM を確保できない場合は stderr に確保失敗と対処案を出して state initialization が失敗し、エンジンは `session_init failed` で終了する（CUDA/HIP: `engine/src/core/layer.cpp:930-937`, `engine/src/program/generate.cpp:7738-7740`; SYCL: `engine/sycl/src/core/layer.cpp:917-925`）。
- 初期化が成功して streaming mode が有効なとき、CUDA/HIP は resident cells、context、pinned RAM 使用量を stderr に表示する（`engine/src/program/generate.cpp:7742-7746`）。

## 根拠

- `engine/src/program/generate.cpp:825,1235-1237,3907,5028-5032` — CUDA/HIP parser option の既定値、help、値の読み込み、負数 validation と設定。
- `engine/sycl/src/program/generate.cpp:509,1946,2542-2546,4234-4277` — SYCL parser と自動 window 選択、RAM 条件。
- `engine/src/core/layer.cpp:738-785,920-942,1284-1285` — CUDA/HIP の window sizing、下限、pinned copy と attention 前の block 解決。
- `engine/sycl/src/core/layer.cpp:722-755,917-927`; `engine/sycl/include/strata/core/short_cache.hpp:42-50` — SYCL の window sizing、下限、pinned allocation と自動候補。
- `engine/include/strata/core/layer.hpp:234-237,288-292` — resident/streaming state の意味と初期化前設定の契約。
