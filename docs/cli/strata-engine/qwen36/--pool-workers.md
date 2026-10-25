# `--pool-workers`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family parser、または `strata-q36` |
| オプション | `--pool-workers` |
| 別名 | なし（`--cpu-threads` も同じ内部値を設定する別の受理名） |
| 値 | 整数。正数は CPU expert pool の worker 数、0 以下は自動選択 |

## 役割

GPU VRAM に全 routed expert を置けずハイブリッド配置になった場合に、CPU 側で routed expert を計算する worker 数を指定します。全 routed expert が VRAM に収まって CPU expert pool が作られない経路では、この値は実行に使われません。

## 使い方

```sh
strata --model Qwen3.6-35B-A3B.gguf --pool-workers 8 --serve
```

`strata` は `--model` または `--native` で指定された GGUF の family が Qwen3.6 (`qwen35moe`) と判定された場合、引数列を Qwen3.6 parser に渡します。専用 executable では `strata-q36 --model Qwen3.6-35B-A3B.gguf --pool-workers 8 --serve` の形でも指定できます。モデルの family 切替箇所と専用 executable の生成条件は根拠欄を参照してください。

## 値と既定値

- `--pool-workers N` は `std::atoi` で整数化されます。parser による範囲検査や数値全体の形式検査はありません。
- 省略時の内部値は `0` です。`ExpertPool` では `n_workers <= 0` が自動選択となり、CPU topology 等に基づく worker 数が決まります。
- 明示した正数はその数を使います。利用可能な worker core 数より大きい場合も数は切り詰められず、core 一覧を超える worker は pin されずに実行されます。CPU に適した計画数を超えた場合は警告が出ることがあります。
- `0`、負数、および `atoi` が数値として読めない文字列は自動選択になります。複数回指定した場合は parser が順に代入するため最後の値が残ります。
- 値が省略され末尾にオプションだけが残ると、`strata-q36: --pool-workers needs a value` を stderr に出して終了コード 2 になります。値の次が別のオプションでも parser は値として消費し `atoi` に渡すため、数値以外を拒否するとは限りません。

## 実行時の動作

Qwen3.6 parser は `--pool-workers` と `--cpu-threads` のどちらも同じ `cpu_threads` 変数に代入し、その値を `place_experts` に渡します。したがって両方が指定された場合も、引数列で後に現れた方が有効です。

expert 配置処理は、slot 指定がなく全 expert が VRAM 予算に収まる場合、GPU に expert を配置して終了します。この経路では CPU pool を生成しません。expert が収まらない場合はハイブリッド配置へ進み、`STRATA_Q36_CPU_POOL` を有効にしてビルドされていれば `ExpertPool(cpu_threads)` を作ります。この pool は GPU slot にない expert の CPU 計算を担います。`--expert-slots` 等による slot 数、空き VRAM、モデルの MTP block 有無も expert 配置に関係するため、指定 worker 数だけで CPU 計算の発生有無は決まりません。

## 適用条件と副作用

- `strata` の family switch は `--model` / `--native` の GGUF header から family を判定して Qwen3.6 実装を選びます。別 family の `strata` 通常 parser での `--pool-workers` の意味とは別スコープです。
- CPU expert pool は `STRATA_NATIVE_EXPERTS` が有効な build で `STRATA_Q36_CPU_POOL` として組み込まれます。無効な build でも全 expert が VRAM に収まる経路は進めますが、hybrid が必要な場合は「この build has no CPU expert pool」というエラーになり、配置失敗として終了コード 1 を返します。
- pool は worker ごとの状態領域を確保し、指定数の thread を起動します。正数が CPU core 数より大きい場合には余剰 thread は pin されません。構成によっては起動時に stderr へ worker 数・VRAM/host 側の配置情報や worker 数の警告が表示されます。
- 文書調査では `strata` の help は実行していません。Qwen3.6 parser の使用箇所と同一 revision のソースを根拠にしています。

## 出力とエラー

- `--pool-workers` の値自体について、Qwen3.6 parser は負数や不正形式のエラーを出しません（`atoi` の結果が pool に渡ります）。
- hybrid が必要なのに CPU pool 無効の build である場合、配置エラーを stderr に出し、`strata-q36: <配置エラー>` の形式で報告して終了コード 1 になります。
- `ExpertPool` が生成されたとき、明示数が topology に基づく適正計画を超えれば `strata cpu pool: warning: ...` が stderr に出る場合があります。これは推奨警告で、worker 数は指定値のままです。

## 根拠

- `docs/cli/README.md:1318-1322,1348` は `strata-engine` の Qwen3.6 parser scope と、このオプションの索引リンクを示す。
- `src/program/generate.cpp:2393-2407` は `--model` / `--native` の GGUF family 判定後に Qwen3.6 実装へ引数を渡す箇所。
- `src/qwen35/q36_engine.cu:3735-3757,3778-3781` は parser 初期値、`--pool-workers` と `--cpu-threads` の代入、共通の次引数処理を示す。
- `src/qwen35/q36_engine.cu:2792-2796,2865-2886,2888-2899,2995-3007` は expert placement の VRAM / hybrid 分岐、CPU pool 無効時の失敗、pool 生成と worker 数の報告を示す。
- `src/qwen35/q36_engine.cu:2236-2245` は hybrid モードで CPU pool を使って CPU 側 expert 計算を行う関数を示す。
- `src/kernels/cpu/pool.cpp:801-818,840-849` は正数指定と0以下の自動選択、最低 worker 数を示す。同 `:912-945` は明示数の推奨警告と、core 一覧を超えた worker が unpinned になる処理を示す。
- `CMakeLists.txt:781-794` は Qwen3.6 engine の build 条件と、`STRATA_NATIVE_EXPERTS` 有効時の CPU pool 組み込みを示す。
