# `STRATA_NO_IQ128`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

x86 CPU の AVX1 用 i-quant expert 行カーネルを選ばないための停止スイッチ。未設定なら AVX2 を持たず AVX1 を使える CPU で gate/up と一部 down 行を Strata の 128-bit 実装に渡し、設定されていればその条件を外して後続の ggml-cpu dot に進ませる。値が `1` かどうかではなく、環境変数の存在だけで判定する（`engine/src/kernels/cpu/native_expert.cpp:584,706-708,841-844`）。

## 値と判定

`std::getenv("STRATA_NO_IQ128") == nullptr` を調べ、文字列変換・内容検証はしない。未設定だけが AVX1 行カーネルを許可する。空文字、`0`、`1`、`true`、`false`、空白を含む値はいずれも「設定あり」として無効化する。値域や数値境界はない（`engine/src/kernels/cpu/native_expert.cpp:584,841`）。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| AVX1 行カーネルの選択判定 | 判定を通過し得る | 該当なし | 空文字を含む任意の値（`0`、`1`、`true`、`false` など） |

この表の「判定を通過し得る」はカーネル選択を保証しない。CPU と型、token 数などの追加条件が必要（次節）。

Strata の設定レジストリにある「未設定または `0` なら有効」という自動注記は、現行の実装と一致しない。実装は値を読まず、`0` を含む設定済みの値をすべて停止条件として扱う（`terminal/data/settings-register.json:26818-26834`; `engine/src/kernels/cpu/native_expert.cpp:584,841`）。

## 有効になる条件

- Strata の x86 CPU 実装で、native expert 行処理に到達すること。ARM64 の `portable.cpp` は AVX1 関数を未実装 stub に置き換え、`cpu_avx1_ok()` も false を返すため対象外（`engine/CMakeLists.txt:73-78`; `engine/src/kernels/cpu/expert_layout.cpp:241-267`; `engine/src/kernels/cpu/portable.cpp:212-215`）。
- 実行 CPU が AVX1 を使え、AVX2 を使えないこと。どちらも実行時 CPU 判定で gate される（`engine/src/kernels/cpu/native_expert.cpp:584,841`; `engine/src/kernels/cpu/expert_layout.cpp:241-267`）。通常の AVX2 CPU ではこの変数にかかわらず AVX1 経路を選ばない。
- gate/up は ggml type 18 (IQ3_XXS)、21 (IQ3_S)、22 (IQ2_S) のみが AVX1 対応。加えて `nt >= native_gu_mt_min(type)` が必要で、しきい値は `STRATA_IQ_MT_MIN` の `atoi` 値、未設定なら 2。`STRATA_IQ3S_MT1` などの条件で IQ3_S のしきい値が 1 になる例外もある（`engine/src/kernels/cpu/iq_avx1.cpp:394-400`; `engine/src/kernels/cpu/native_expert.cpp:540-556,654-656,706-708`）。
- down は ggml type 20 (IQ4_NL) と 42 (Q2_0) のみが AVX1 対応。`native_down_rows_impl` では token 数による追加しきい値はない（`engine/src/kernels/cpu/iq_avx1.cpp:402-404`; `engine/src/kernels/cpu/native_expert.cpp:841-844`）。
- 変数が設定されている場合、上記 AVX1 分岐は通らず後続の処理へ進む。Strata のコードは、この変数による代替経路の選択や警告を追加せず、通常の残りの dispatch に任せる（`engine/src/kernels/cpu/native_expert.cpp:706-710,841-859`）。

## 実行時の詳細

native CPU expert pool の gate/up 行処理と down 行処理から `native_gu_rows_impl` / `native_down_rows_impl` が呼ばれる（`engine/src/kernels/cpu/pool.cpp:1296,1309,1429,1453`; `engine/src/kernels/cpu/native_expert.cpp:898-915`）。AVX1 gate/up が選ばれた場合は `iq128_gu_rows`、down は `iq128_down_rows` を実行し、変数の設定時はこれらの呼び出しを飛ばす（`engine/src/kernels/cpu/native_expert.cpp:706-708,841-844`）。

判定は関数内 `static const bool` なので、それぞれのテンプレート実体（通常算術／window-invariant 算術）の最初の呼び出し時に評価され、その実体では後続呼び出しに cache される。down 側も同様。環境を実行中に変更しても、すでに初期化された判定には反映されない。生成プログラムの CPU-kernel 表示箇所は static cache ではなく、その表示時点で設定有無を読み直す（`engine/src/kernels/cpu/native_expert.cpp:559-560,584,793-794,841`; `engine/src/program/generate.cpp:5628-5634`）。

CLI 引数による上書きや、子プロセス向けに値を設定・転送する Strata のコードは見つからなかった。CPU 行カーネルの選択停止スイッチであり、GPU 行カーネルの直接的な切替ではない。CUDA/HIP を使う生成経路でも、native CPU expert pool の行処理が呼ばれ、かつ上記 CPU 条件を満たす場合に限り影響する。

## ログと測定値

この変数専用の警告・エラー・終了経路はない。CUDA/HIP の生成プログラムで native pack を使い、CPU に VNNI がない場合は CPU kernel 名を stderr に表示する。AVX2 がなく AVX1 が使えるとき、未設定なら `strata generate: CPU expert kernels: AVX1 (older-CPU build)`、設定済みなら `strata generate: CPU expert kernels: ggml-cpu (older-CPU build)` となる。この表示は全処理開始時の説明で、個々の行の選択ログではない（`engine/src/program/generate.cpp:5598-5634`）。

この文書では性能値を記載しない。ソースコメント中のベンチマーク値は条件付きの設計メモであり、この調査で測定し直した結果ではない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:584,706-708,841-844` — 変数の存在判定と gate/up・down の AVX1 行 dispatch。
- `engine/src/kernels/cpu/iq_avx1.cpp:394-404` — gate/up・down が受け付ける ggml type。
- `engine/src/kernels/cpu/native_expert.cpp:540-556` — gate/up の token 数しきい値。
- `engine/src/kernels/cpu/pool.cpp:1296,1309,1429,1453` — CPU expert pool から行関数への呼び出し。
- `engine/src/program/generate.cpp:5628-5634` — 起動時 CPU-kernel 表示での設定有無判定。
- `engine/src/kernels/cpu/expert_layout.cpp:241-267`, `engine/src/kernels/cpu/portable.cpp:212-215`, `engine/CMakeLists.txt:73-78` — x86 AVX1 判定と ARM64 の非対応経路。
