# `STRATA_NO_IQ4NL`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

CPU native expert 経路で、IQ4_NL 形式の down projection に使う AVX2 複数 token カーネルを無効にする開発・診断用スイッチです。無効にすると、このカーネルの代わりに後続の実装選択（ggml-cpu の dot、または AVX2 非対応 CPU で使える AVX1 カーネル）が行われます。ゲート/up projection や GPU 側の IQ4_NL カーネルはこの変数では切り替わりません。

## 値と判定

数値や文字列を parse せず、`std::getenv("STRATA_NO_IQ4NL") != nullptr` の結果だけを使います。

| 環境変数の状態 | IQ4_NL AVX2 複数 token カーネル |
|---|---|
| 未設定 | 使用候補になる |
| 値が設定されている（`1`、`0`、任意の文字列、空文字を含む） | 無効 |

判定結果は `native_down_rows()` 内の `static const bool` に初回評価時に保存されます。同じプロセスで後から環境変数を変更しても、この判定は再評価されません。

## 有効になる条件

未設定であっても、次の条件を満たす場合だけ AVX2 複数 token カーネルを呼びます。

- Strata の native expert CPU 経路を実行している。
- down projection の型が IQ4_NL（ggml type `20`）。
- CPU の AVX2 が利用可能と判定される。
- token グループの大きさ `nt` が `STRATA_IQ_MT_MIN` の閾値以上。

`STRATA_IQ_MT_MIN` は未設定なら `2`、設定時は `std::atoi()` の結果です。したがって既定では `nt == 1` のとき、この AVX2 複数 token カーネルは使いません。`STRATA_NO_IQ4NL` が設定されている場合も、条件式が偽になり同じカーネルを使いません。

AVX2 が使えない CPU では、この AVX2 経路自体が選ばれません。後続の分岐で AVX1 が利用可能かつ IQ4_NL down に対応していれば AVX1 カーネルを使います。この AVX1 選択には `STRATA_NO_IQ4NL` の判定がなく、この変数は AVX1 経路を無効にしません。

## 実行時の詳細

Qwen 3.5/3.8 系 engine の hybrid 実行では、GPU に resident でない routed expert を CPU pool に送り、`run_split_multi_native()` で native expert の gate/up と down を処理します。CPU pool の down phase は Q2_0 等の専用経路に該当しない場合 `native_down_rows()` を呼びます。IQ4_NL はそこで AVX2 条件を満たすと `iq4nl256_down_rows()` に渡されます。

この複数 token カーネルは、IQ4_NL の nibble を decode して重みを処理する作業を block ごとにまとめて行います。無効時に AVX2 CPU で到達する汎用 fallback は `ggml-cpu` の `vec_dot` を各 row・各 token に適用する経路です。AVX2 非対応 CPU では前述の AVX1 対応分岐が先に評価されます。値の parse に伴う警告や、この変数専用のログ出力はありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:233-239`: IQ4_NL 用フラグの有無判定と `STRATA_IQ_MT_MIN` の既定値・parse。
- `src/kernels/cpu/native_expert.cpp:240-257`: AVX2、token 数、down 型によるカーネル選択、AVX1 fallback。
- `src/kernels/cpu/native_expert.cpp:270-277`: 専用カーネルに入らない場合の `ggml-cpu` `vec_dot` fallback。
- `src/kernels/cpu/iq_avx2.cpp:503-519`: IQ4_NL 複数 token カーネルの入口と、AVX-VNNI variant の選択。
- `src/kernels/cpu/pool.cpp:709-719,817-838`: native down rows を使う CPU pool phase と複数 native expert の実行。
- `src/qwen35/q36_engine.cu:1665-1693`: hybrid engine が CPU 側 routed expert を native pool に渡し、結果を GPU 側へ戻す処理。
- `docs/DETAILS.md:288-290`: CPU i-quant / IQ4_NL 行カーネルと `STRATA_NO_AVXVNNI` の説明はあるが、`STRATA_NO_IQ4NL` の記載はありません。
