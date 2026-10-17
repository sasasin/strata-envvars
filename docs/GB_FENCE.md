# `GB_FENCE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Metal の `gridbar_bench` が実行時にコンパイルする `gridbar.metal` に、device-scope の atomic thread fence を組み込むかを選びます。参照は `metal/tests/gridbar_bench.cpp` だけにあり、通常の Strata 実行エンジンからは読み取られません。このため、Metal の grid barrier ベンチ用の切り替えです。

## 値と判定

| 環境変数 | 判定 | コンパイル時の指定 |
|---|---|---|
| 未設定 | `std::getenv("GB_FENCE")` が `nullptr` | `NO_GGML_COMMON` のみ定義し、`GB_FENCE` は定義しない |
| 設定あり | 戻り値が `nullptr` でない | `NO_GGML_COMMON` と `GB_FENCE` を定義 |

値の内容は parse も比較もされません。空文字を含め、どんな値でも環境変数が存在すれば有効側です。設定値はベンチの `main()` 内で一度だけ検査され、そこで選んだソース定義を使って Metal ライブラリをコンパイルします。

## 有効になる条件

`metal/tests/gridbar_bench` を実行し、その実行環境に `GB_FENCE` が設定されている場合に限り、この判定が使われます。Strata の通常の Metal エンジンのカーネルコンパイル経路にはこの環境変数の参照がありません。

## 実行時の詳細

`gridbar_bench` は `gridbar.metal` をコンパイルし、dispatch 境界による phase 分離と、カーネル内 grid barrier による phase 分離を比較します。`GB_FENCE` が設定されている場合、`grid_barrier()` の threadgroup barrier の直後と、threadgroup が atomic counter を更新・待機した後の threadgroup barrier の直後に、それぞれ `atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device)` を含むビルドになります。未設定の場合、これら2箇所は `#ifdef GB_FENCE` によってコンパイルされません。

ベンチは `grid barrier` の計測値に `stale flags seen` の数を出力しますが、`GB_FENCE` の設定状態そのものを示すログはありません。コードから確認できるのはフェンス呼び出しを含む／含まないカーネルをコンパイルする点までで、性能や可視性の保証はこの調査では評価していません。

## 根拠

- `metal/tests/gridbar_bench.cpp:11-17` — 起動引数の既定値、環境変数の有無判定、カーネルのコンパイル時に渡す定義。
- `metal/kernels/gridbar.metal:9-21` — `GB_FENCE` 定義時に挿入される2つの fence 呼び出しと grid barrier。
- `metal/tests/gridbar_bench.cpp:42-64` — grid barrier 計測と stale flag 数の出力。
