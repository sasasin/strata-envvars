# `--cpu-threads`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用 parser（単独 executable は `strata-q36`） |
| オプション | `--cpu-threads` |
| 別名 | `--pool-workers`（parser 内で同じ CPU pool 数変数へ代入） |
| 値 | 整数。明示的な範囲検証なし |

## 役割

Qwen3.6 の routed experts が VRAM に収まらず hybrid 配置になるとき、CPU 側で expert 計算を行う worker 数を指定します。モデルが Qwen3.6 family と判定されると `strata` は専用実装へ引き渡し、同じ parser は `strata-q36` からも呼ばれます（`src/program/generate.cpp:2393-2407`、`CMakeLists.txt:776-794`）。

## 使い方

```sh
strata --model /models/qwen36.gguf --cpu-threads 8 --tokens 1,2,3
```

`--tokens` は実行に必要な他の引数の例です。Qwen3.6 専用 parser では `--cpu-threads` と `--pool-workers` のどちらも `cpu_threads` に整数として読み込まれ、後から指定した値が使われます（`src/qwen35/q36_engine.cu:3735-3741, 3778-3780`）。

## 値と既定値

- 省略時の値は `0` です（`src/qwen35/q36_engine.cu:3737`）。
- `std::atoi` で変換されます。parser に数値範囲や形式の検証はありません。値の欠落時は `strata-q36: --cpu-threads needs a value` を stderr に出して終了コード `2` で終了します（`src/qwen35/q36_engine.cu:3742-3746, 3779`）。
- 正の値は CPU pool の worker 数として指定されます。`0` と負数は worker 数の明示指定として扱われず、CPU topology 等から pool が数を選びます。pool は `n_workers > 0` の場合だけ指定値を採用し、選択結果が 1 未満なら 1 に補正します（`src/kernels/cpu/pool.cpp:801-817, 847`）。
- 同じオプションを複数回指定した場合、parser が順に変数へ代入するため最後の値が placement に渡ります（`src/qwen35/q36_engine.cu:3742-3747, 3779`）。

## 実行時の動作

parser の値は `place_experts` に渡され、hybrid 配置で `ExpertPool(threads)` を作る際に使われます（`src/qwen35/q36_engine.cu:3863-3866, 2995`）。正の値は worker 数です。pool の既定 `host_works=true` により、pool を呼び出す host thread も job を処理します。そのためログの CPU thread 数は workers に host thread を加えた数です（`include/strata/kernels/cpu/pool.hpp:196-200`、`src/qwen35/q36_engine.cu:3002-3006`）。

この CPU pool は、VRAM slot にない expert の計算に使われます。decode 等の hybrid 経路では CPU 側 job を pool に送り、結果を GPU に転送して GPU 側の expert 結果と merge します（`src/qwen35/q36_engine.cu:2236-2289`）。プロンプト chunk の一部は別途 staging buffer 経由で GPU に stream されます（`src/qwen35/q36_engine.cu:2792-2795, 2893-2897, 3002-3006`）。

## 適用条件と副作用

- 全 routed experts が VRAM に収まり、`place_experts` が通常配置で成功する場合、同関数は pool を作らず戻ります。この経路では `--cpu-threads` は使われません（`src/qwen35/q36_engine.cu:2865-2879`）。
- hybrid 配置が必要でも `STRATA_NATIVE_EXPERTS` を無効にして CPU pool なしで build した場合、CPU pool は作られず、配置関数は「experts が VRAM に収まらない」旨のエラーで失敗します（`CMakeLists.txt:785-789`、`src/qwen35/q36_engine.cu:2881-2886`）。
- hybrid 経路は GPU 上の expert slot、host memory 上の expert 全体、CPU pool 用の出力・staging buffer を確保します。pinned host allocation が失敗した場合は通常の `malloc` に fallback します（`src/qwen35/q36_engine.cu:2920-2933, 2951-2958, 2975-2995`）。このオプションは GPU slot 数や host allocation の方式を制御せず、CPU pool の並列度を指定します。
- pool が生成される際の worker 配置・自動数選択には CPU topology と pool 関連環境設定が関係します。個々の環境で実際に何 thread が選ばれるかは実行機の topology に依存し、この調査では特定環境の値を確認していません（`src/kernels/cpu/pool.cpp:743-817`）。

## 出力とエラー

- hybrid 配置が成功すると stderr に `hybrid experts` と CPU thread 数などが出力されます。MTP block だけを CPU 側に置く経路では、その旨と VRAM/CPU の expert 数が出力されます（`src/qwen35/q36_engine.cu:2997-3006`）。
- pool を含まない build で VRAM 配置できない場合は、placement error を `strata-q36: ...` として stderr に出し、`run` は `1` を返します（`src/qwen35/q36_engine.cu:3863-3866`）。
- 値自体の範囲エラーや clamp はありません。負数を含む 0 以下は pool constructor の自動 worker 選択へ渡ります（`src/kernels/cpu/pool.cpp:801-817`）。

## 根拠

- parser と値の既定値: `src/qwen35/q36_engine.cu:3735-3780`
- family 判定と専用 parser への委譲: `src/program/generate.cpp:2393-2407`
- placement の分岐、pool 作成、成功ログ: `src/qwen35/q36_engine.cu:2792-3007`
- CPU expert job の pool 実行と GPU への結果転送: `src/qwen35/q36_engine.cu:2236-2289`
- `ExpertPool` の既定値と worker 数選択: `include/strata/kernels/cpu/pool.hpp:196-200`、`src/kernels/cpu/pool.cpp:801-817, 847`
- Qwen3.6 engine の build 条件と CPU pool の有効化: `CMakeLists.txt:776-794`

## 調査範囲

ソース checkout の同一 revision を読み取り専用で確認しました。build、実行、性能測定、テストは行っていません。索引 [`README.md`](../../README.md) は `--pool-workers` も別の予定リンクとして掲載していますが、現行 parser では `--pool-workers` と `--cpu-threads` が同じ `cpu_threads` 変数へ代入されます（`src/qwen35/q36_engine.cu:3752, 3779`）。索引は依頼どおり変更していません。
