# `--cpu-threads`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--cpu-threads` |
| 別名 | なし。`--pool-workers` も同じ変数を設定する別オプション |
| 値 | 整数。CPU expert pool の worker 数として渡される |

## 役割

Qwen3.6 エンジンが routed expert を VRAM に全て置けず、hybrid 配置で CPU expert pool を使うときの worker 数を指定します。全 expert が VRAM に収まる経路では pool を作らないため、この値は worker 数に反映されません。

## 使い方

```sh
# Qwen3.6 モデルを読み込み、CPU pool が必要な場合の worker 数を 6 に指定
strata-q36 --model ./model.gguf --cpu-threads 6 --tokens "1 2 3" --n 1
```

`strata --model ...` で Qwen3.6 family に振り分けられた場合も、Qwen3.6 parser が同じ引数を処理します。

## 値と既定値

- 値は次の argv 要素から `std::atoi` で整数化されます。`--cpu-threads` 単独では値不足として stderr に `strata-q36: --cpu-threads needs a value` を出し、終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5348-5352,5385`）。
- parser に正数範囲の検証はありません。整数化後の値が正数なら明示 worker 数として使われ、0 以下なら自動選択に回ります。自動選択では CPU topology や pool の配置計画から worker 数を決めます（`engine/src/kernels/cpu/pool.cpp:865-881`）。
- 省略時の初期値は 0 なので自動選択です（`engine/src/qwen35/q36_engine.cu:5342`）。
- 同じオプションを複数回指定した場合、parser は順に変数へ代入するため最後の値が残ります。`--pool-workers N` も同じ `cpu_threads` 変数に代入するので、両方を指定した場合も最後に現れた方が適用されます（`engine/src/qwen35/q36_engine.cu:5358,5385`）。
- `--cpu-threads=N` の等号形式は parser に定義されていません。通常の非 serve 引数解析では未認識引数となり、usage を stderr に表示して終了コード 2 になります（`engine/src/qwen35/q36_engine.cu:5412-5417`）。

## 実行時の動作

parser は値を `cpu_threads` に格納し、初期化後に expert 配置関数 `place_experts` へ渡します。hybrid 経路では `ExpertPool(threads)` を生成し、正数指定は worker 数として採用されます。0 以下の場合は、明示 core 指定があればその数、hybrid CPU なら P-core 数など、CPU topology と配置計画に基づき選びます（`engine/src/qwen35/q36_engine.cu:5522-5523,4528`; `engine/src/kernels/cpu/pool.cpp:865-881`）。

## 適用条件と副作用

- この値が worker 数に効くのは CPU expert pool が使われる場合です。`place_experts` は全 routed expert が VRAM に収まると配置を完了して pool を作らずに戻ります（`engine/src/qwen35/q36_engine.cu:4318-4335,4528`）。
- hybrid CPU pool のコードは `STRATA_NATIVE_EXPERTS` が有効な build で組み込まれます（`engine/cmake/strata_gpu_engine.cmake:571-579`）。その機能がない build では、expert が VRAM に収まらないと配置関数が失敗し、「CPU expert pool がない」旨を返します。呼び出し元はエラーを stderr に出して終了コード 1 を返します（`engine/src/qwen35/q36_engine.cu:4337-4342,5523-5526`）。
- 明示した正数が CPU に適した数を超える場合も値を強制的に変更せず、pool 実装は警告を stderr に出すだけです（`engine/src/kernels/cpu/pool.cpp:980-988`）。worker thread は pool 作成時に起動します（同 `:991-1002`）。

## 出力とエラー

- hybrid 経路の起動ログには、batch の CPU 処理に使う worker 数が表示されます（`engine/src/qwen35/q36_engine.cu:4535-4539`）。
- worker 数の不足・過剰などを理由に `--cpu-threads` 自体を拒否する parser validation は確認できません。値の不正形式を `atoi` がどう変換するかは C ランタイム側の仕様に依存するため、Strata 側の独自エラー動作としては断定しません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5342,5348-5352,5385` — 初期値、値取得、および `atoi` による parser 定義。
- `engine/src/qwen35/q36_engine.cu:5358,5522-5523` — `--pool-workers` との同一変数の共有と expert 配置関数への引き渡し。
- `engine/src/qwen35/q36_engine.cu:4318-4335,4337-4342,4528,4535-4539` — VRAM 配置で pool を省略する分岐、pool 不在 build の失敗、hybrid pool 生成と起動ログ。
- `engine/src/kernels/cpu/pool.cpp:865-881,980-1002` — 正数指定・自動 worker 選択、過剰値の警告、および worker thread の起動。
- `engine/cmake/strata_gpu_engine.cmake:571-579` — `STRATA_NATIVE_EXPERTS` と Qwen3.6 CPU pool の build 条件。
