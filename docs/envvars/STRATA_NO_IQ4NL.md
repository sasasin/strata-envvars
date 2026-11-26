# `STRATA_NO_IQ4NL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native expert の down projection が IQ4_NL（型 ID 20）である場合に使う、AVX2 multi-token 行カーネルを無効にする。未設定なら条件を満たすと `iq4nl256_down_rows` に分岐し、設定されていればその分岐を通さず、後続の通常の dot 経路へ進む。これは native expert の CPU 行計算に限った切替で、gate/up 行や CUDA/SYCL の IQ4_NL カーネルを切り替える読み取りではない（`engine/src/kernels/cpu/native_expert.cpp:792-839`）。

## 値と判定

`std::getenv("STRATA_NO_IQ4NL") == nullptr` の結果だけを見る。文字列を parse せず、未設定なら multi-token カーネルを許可し、設定済みなら値にかかわらず抑止する。したがって空文字、`0`、`1`、`false`、任意の文字列はいずれも同じ「抑止」扱いである。境界値や大文字小文字の判定はない（`engine/src/kernels/cpu/native_expert.cpp:797-798`）。

| 条件 | unset | 設定済みの値（例） |
| --- | --- | --- |
| CPU native expert の down-row dispatch | `iq4nl_mt == true` | 空文字、`0`、`1`、`false` を含め `iq4nl_mt == false` |

## 有効になる条件

- `engine/src/kernels/cpu/native_expert.cpp` を含む CPU native-expert backend がビルドされ、その CPU native-expert down-row dispatch が実行されること。同ファイルは CPU backend の `strata_cpu_native_experts` で `strata_kernels_cpu` に加えられ、同 backend は `STRATA_NATIVE_EXPERTS=1` を定義する（`engine/cmake/backends/cpu.cmake:303-317, 370`）。
- down-row の型 `f.d_type` が IQ4_NL の型 ID `20`、CPU が AVX2 対応、かつ `nt >= STRATA_IQ_MT_MIN` であること。`STRATA_IQ_MT_MIN` は別の環境変数で、未設定時 `2`、設定時は `std::atoi` で一度読み取られる。これらを満たし、かつ本変数が未設定なら `Default` arithmetic では `iq4nl256_down_rows` が選ばれる。`WindowInvariant` arithmetic では `mt_min <= 1` なら同じ kernel、それ以外は x86-64・AVX2 flavor・`iq4nl_reference_ok()` 成功時に `iq4nl_reference_rows` が選ばれ、条件不成立または照合失敗時は後続の一般 dot 経路へ進む（`engine/src/kernels/cpu/native_expert.cpp:797-798, 828-839`）。
- この条件を満たしても本変数が設定済みなら AVX2 multi-token 分岐を飛ばす。AVX2 がない CPU では当該分岐自体が成立しないため、この変数による追加の切替はない（同: `828-843`）。
- 型 ID 20 の場合、後続の旧 CPU 向け AVX1 分岐は AVX2 非対応・AVX1 対応・`STRATA_NO_IQ128` 未設定のときに別途成立し得る。本変数はこの分岐を無効化しない（同: `840-843`）。
- CPU native expert の外側の呼び出し経路も必要である。`ExpertPool::native_rows` と依存タスク処理から native down-row 関数が呼ばれ、通常の `NativeArithmetic::Default` と `WindowInvariant` の双方が同じ環境判定を持つ実装に到達する（`engine/src/kernels/cpu/pool.cpp:1274-1310, 1433-1453`; `engine/src/kernels/cpu/native_expert.cpp:903-915`）。

## 実行時の詳細

判定は `native_down_rows_impl` 内の関数ローカル `static const bool` であり、最初にそのテンプレート実体（`Default` または `WindowInvariant`）へ入ったときに初期化され、その実体についてプロセス内で cache される。以降に環境を変更しても、初期化済みの実体の判定は変わらない。CPU native expert では down-row の型・token 数などを見て IQ4_NL multi-token kernel を選ぶ条件にこの値を使う（`engine/src/kernels/cpu/native_expert.cpp:792-798, 828-839, 903-915`）。

抑止時、または型・CPU・token 数の条件を満たさないときは、IQ4_NL multi-token 分岐を通らず後続の一般行処理へ進む。AVX1 専用経路が成立しなければ、各行・各 token について `traits(f.d_type).dot(...)` を呼ぶ経路となる。`STRATA_OWN_CPU_QUANT` が有効な build では `traits` は Strata quant layer の dot kernel を参照し、無効な build では ggml-cpu の type traits を参照するため、fallback の実装元は build 設定によって異なる（`engine/src/kernels/cpu/native_expert.cpp:840-893`; `engine/include/strata/kernels/cpu/pool_quant.hpp:4-5, 32-64, 78-91`; `engine/CMakeLists.txt:184`）。この変数が変えるのは CPU native expert の down-row 計算経路であり、ルーティングや expert の選択条件を変更する処理はここにはない。

## ログと測定値

この変数の読み取り・分岐に伴う専用ログ、警告、終了処理はない（`engine/src/kernels/cpu/native_expert.cpp:792-893`）。IQ4_NL multi-token kernel と通常の dot 経路の性能差をこの調査で測定していない。ソースコメントには multi-token kernel が block ごとの decode を token ごとに繰り返さない設計との説明があるが、測定値や一般的な速度向上としては扱わない（同: `795-797`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:792-839` — 環境判定、CPU・型・token 数の条件、AVX2 / AVX1 の経路。
- `engine/src/kernels/cpu/native_expert.cpp:840-893` — multi-token 分岐を通らない場合の行 dot 処理。
- `engine/src/kernels/cpu/native_expert.cpp:903-915` — 通常・WindowInvariant entry point とテンプレート実装への接続。
- `engine/src/kernels/cpu/pool.cpp:1274-1310, 1433-1453` — ExpertPool の native down-row dispatch。
- `engine/include/strata/kernels/cpu/pool_quant.hpp:4-5, 32-64, 78-91` — build による `traits().dot` の実装元。
- `engine/cmake/backends/cpu.cmake:303-317, 370-374` — CPU native-expert ソースの登録と build macro。

