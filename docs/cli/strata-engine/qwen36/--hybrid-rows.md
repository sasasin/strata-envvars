# `--hybrid-rows`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata-q36`、または Qwen3.6 GGUF を指定した `strata` |
| オプション | `--hybrid-rows` |
| 別名 | なし |
| 値 | 整数。hybrid expert 処理の一回の GPU/CPU 分担対象行数の上限として使われる |

## 役割

GPU メモリに全 routed expert を置けず、CPU expert pool と GPU 上の expert slot を併用する hybrid 配置で、各 batch のうち hybrid rows 経路に送る行数の上限を指定する。対象モデルが Qwen3.6 (`qwen35moe`) のときに使う family 専用 parser のオプションである。全 expert が VRAM に収まる実行では、この値は配置判断に反映されない。

## 使い方

```sh
# Qwen3.6 の token-ID 入力を使う場合の例。モデルのパスと ID 列は実行環境に合わせる
strata-q36 --model <Qwen3.6-GGUF> --hybrid-rows 128 --tokens "<token IDs>"
```

## 値と既定値

- 省略時は `128`。parser は値を `std::atoi` で整数変換する（`engine/src/qwen35/q36_engine.cu:5342,5392`）。
- オプション名の後に値がない場合、`next()` が `needs a value` を stderr に出してプロセスを終了コード `2` で終了する（同 `:5350-5353`）。
- このオプション固有の範囲検証や不正値エラーはない。hybrid 配置に入ると `place_experts` は `max(1, min(指定値, E.tmax))` を使うため、0・負数は 1 に、`E.tmax` より大きい値は `E.tmax` に制限される（同 `:4349`）。`E.tmax` は `Engine::init` で設定され、初期値は 512、初期化時には `max(tmax_, kVerify)` にされる（同 `:1576,1962-1968`）。
- 数字として解釈できない値は `atoi` により 0 となり、hybrid 配置時には 1 へ制限される。複数回指定した場合は parser が都度代入するため、最後に読んだ値が残る（同 `:5348-5353,5392`）。

## 実行時の動作

parser で得た値は `place_experts(m, E, expert_vram, cpu_threads, hybrid_rows, expert_slots, err)` に渡される（`engine/src/qwen35/q36_engine.cu:5522-5526`）。全 routed expert が VRAM に収まる配置では同関数が GPU へ配置して早期 return するため、この値は使われない（同 `:4318-4335`）。CPU expert pool を有効にしていて hybrid 配置となった場合、指定値を上記の範囲に制限し、hybrid batch の行数上限 `E.hybrid_t` として保持する（同 `:4337-4350`）。

各 layer では、その layer が hybrid で、かつ `T <= hybrid_t`（または main layer ではなく MTP block の処理）なら hybrid rows 経路を選ぶ（同 `:2902-2911`）。この経路では VRAM にある expert を GPU で処理し、slot にない expert の分を CPU pool と並行して処理する。大きい prompt chunk は main layers の hybrid rows 上限を超えるため streamed prompt 経路へ進む（同 `:1793-1795,2912-2918`）。

`--chunk` / `--prefill` に対応する streamed prompt path が無効な場合は、実装が `E.hybrid_t` を `E.tmax` に上書きし、全 batch を slots と CPU pool で処理するため、このオプションの指定値は実質反映されない（同 `:4349-4350`）。staging buffer を確保できず fallback する場合も同様に `E.hybrid_t = E.tmax` へ切り替える（同 `:4482-4501`）。

## 適用条件と副作用

- `strata` は `--model` / `--native` が指す GGUF の architecture から Qwen3.6 family を判定し、`qwen35moe` なら同じ引数を `strata::qwen35::run` に渡す。単体 `strata-q36` も同 parser を使う（`engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5`）。
- CPU expert pool を含まない build では、VRAM に expert が収まらない場合、`--hybrid-rows` の値は使われず、`STRATA_NATIVE_EXPERTS=OFF` の build である旨を含むエラーとなる（`engine/src/qwen35/q36_engine.cu:4337-4343`）。
- hybrid 配置では、GPU 上の expert slots・routing table・scratch・必要に応じた prompt staging を確保し、全 expert の host memory を確保する。host arena は pinned allocation を試し、失敗時は pageable host memory に fallback する（同 `:4430-4480`）。CPU pool を作成し、main layers が hybrid の場合は host 処理のため graph を無効化する（同 `:4344-4349,4528-4538`）。これらは hybrid 配置自体の副作用であり、`--hybrid-rows` 単独で必ず発生するわけではない。

## 出力とエラー

- 成功した hybrid 配置では stderr に、GPU slot 数、host memory 種別、`<= E.hybrid_t` 行を CPU pool が処理すること、より大きい prompt chunk が streaming されることなどを含む配置概要が出る（`engine/src/qwen35/q36_engine.cu:4534-4539`）。
- hybrid plan が VRAM 不足で成立しない場合は `place_experts` が失敗し、呼び出し元が `strata-q36: <理由>` を stderr に出して終了コード `1` を返す（同 `:4381-4390,5523-5526`）。この失敗は指定行数だけの値域エラーではない。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5342,5350-5353,5392` — 既定値、値の読み込み、欠落時の失敗。
- `engine/src/qwen35/q36_engine.cu:4318-4351,5522-5526` — VRAM 全配置の早期 return、hybrid 条件、値の clamp と引き渡し。
- `engine/src/qwen35/q36_engine.cu:1793-1795,2902-2918,4337-4349` — hybrid rows と大きい prompt chunk の分岐、CPU pool build 条件。
- `engine/src/qwen35/q36_engine.cu:4430-4480,4482-4501,4528-4539` — hybrid 配置時の memory allocation、fallback、stderr 概要。
- `engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5` — `strata` の Qwen3.6 family switch と単体 executable の入口。
- Qwen3.6 専用の parser 実装に限定して調査した。`--hybrid-rows` の値による性能差や推奨値は、このソース調査では評価していない。
