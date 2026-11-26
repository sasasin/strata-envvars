# `--pool-workers`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--pool-workers` |
| 別名 | なし |
| 値 | 整数 `N`。parser は `atoi` で変換する |

## 役割

Qwen3.6 の routed expert が CPU expert pool に割り当てられたとき、CPU 側の worker 数を指定する。GPU に expert が収まり CPU pool が使われない実行では、この値は pool の作成にも使われない。

## 使い方

```sh
# Qwen3.6 の serve 実行で、CPU expert pool の worker 数を 8 に指定
strata --model ./qwen36.gguf --serve --pool-workers 8
```

## 値と既定値

- `N` は `std::atoi` で整数に変換され、専用の範囲 validation はない。値を省略すると `--pool-workers needs a value` を標準エラーに出して終了コード 2 で終了する。
- 初期値は 0。CPU pool が作られる場合、0 以下は明示 worker 数として扱われず、pool の自動選択に進む。自動選択は CPU topology、pool affinity、NUMA 等を使う共通 pool 実装が決める。
- 正数は worker 数として pool に渡される。重複指定では後の `--pool-workers` が前の値を上書きする。
- `--cpu-threads` も同じ変数に代入する。両方を指定した場合は argv 上で後に現れた方が有効になる。
- `atoi` のため、数値として解釈できない文字列は 0 になり、自動選択として扱われる。厳密な数値形式チェックはない。

## 実行時の動作

Qwen3.6 用の `run()` は `--pool-workers N` を `cpu_threads` に読み込み、後で expert placement に渡す。モデルの expert 配置が全て VRAM に収まる場合は配置関数が成功して戻るため CPU pool を作らず、この設定による worker 数の指定は実行に影響しない。VRAM に収まらず CPU pool を使う hybrid 経路では、または MTP block の expert を CPU 側へ置く経路では、`ExpertPool(threads)` が作られ、正数ならその数が worker 数となる。0 以下では pool 実装の自動計画が使われる。

Qwen3.6 は `--model` / `--native` の GGUF family 判定で専用 parser に分岐する。したがって、この文書は索引に記載された `qwen36/` scope の挙動を扱う。同名の共通 engine parser とは別の値処理として扱う。

## 適用条件と副作用

- CPU pool を含むビルドで、expert 配置が CPU pool を必要とする場合に適用される。全 expert が VRAM に収まる経路では worker pool は生成されない。
- CPU pool が有効な経路では CPU worker thread を生成・利用する。値は expert 配置に渡されるが、VRAM 上の expert 配置数や GPU 選択を直接変更する処理は確認できない。
- CPU pool を含まないビルドで expert が VRAM に収まらない場合、配置は失敗する。エラーには `this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)` と示され、呼び出し元は終了コード 1 を返す。

## 出力とエラー

- 引数値の欠落時は標準エラーに `strata-q36: --pool-workers needs a value` を出し、終了コード 2 で終了する。
- オプション名自体は Qwen3.6 parser に受理される。未知オプションは通常、usage を標準エラーに出して終了コード 2 となる（`--serve` 時は未知の `--` オプションを警告して読み飛ばす経路がある）。
- CPU pool を必要とする配置で配置計画が収まらない場合、エラーを標準エラーに出して終了コード 1 で戻る。CPU pool を持たない build の場合も同様に配置エラーとなる。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5358` — Qwen3.6 parser の入口、初期値 0、`--pool-workers` の `atoi` 変換。
- `engine/src/qwen35/q36_engine.cu:5380-5386` — `--cpu-threads` も同じ `cpu_threads` を更新する。
- `engine/src/qwen35/q36_engine.cu:5350-5352,5412-5420` — 値欠落時の標準エラーと終了コード 2、未知オプションおよび必須 `--model` の処理。
- `engine/src/program/generate.cpp:3804-3818` — GGUF の model family により Qwen3.6 専用 `run()` に分岐する。
- `engine/src/qwen35/q36_engine.cu:4318-4345` — expert が VRAM に収まると pool を作らず戻る処理、および CPU pool を含まない build の失敗。
- `engine/src/qwen35/q36_engine.cu:5522-5525,4528-4539` — worker 数を expert placement に渡し、hybrid 配置で CPU expert pool を作成する箇所。
- `engine/src/kernels/cpu/pool.cpp:865-881,904-912` — 正数を指定 worker 数として選び、0 以下では自動計画を使う処理。pool の worker 数を最低 1 にする処理。

