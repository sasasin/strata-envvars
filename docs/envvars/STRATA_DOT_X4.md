# `STRATA_DOT_X4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata の CPU native expert 経路で、gate/up と down の行ごとの dot product に 4 行まとめて同じ activation を使う x4 kernel を選べるようにする opt-in 変数です。値が有効でも、x4 kernel がビルドされていない、CPU ISA が合わない、対象 weight 型に kernel がない、または処理行が 4 行未満なら、1 行ずつの dot に進みます。読み取り・選択箇所は `engine/src/kernels/cpu/native_expert.cpp:734-740,751-789,859-865,873-893` です。CPU pool から gate/up と down の native rows が呼ばれます（`engine/src/kernels/cpu/pool.cpp:1290-1309,1423-1453`）。

## 値と判定

`dot_x4_enabled` は文字列を数値変換せず、`STRATA_DOT_X4` がちょうど 1 文字の `"1"` である場合だけ有効にします。未設定、空文字、`"0"`、`"11"`、`"1x"`、`"true"`、空白付きの値は無効です。大文字小文字や数値の妥当性を調べる処理はなく、文字列全体を `"1"` と比較しています（`engine/include/strata/quant/dot_x4_policy.hpp:14-17`）。

| 条件 | `STRATA_DOT_X4` が未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 判定関数が呼ばれる CPU native expert 経路 | 無効 | 文字列が厳密に `"1"` | 空文字、`"0"`、`"11"`、`"1x"`、`"true"`、`" 1"` など |
| `STRATA_NO_DOT_X4` も設定 | 無効 | なし | `STRATA_NO_DOT_X4` は値が空でも設定されていれば無効化 |
| `STRATA_OWN_CPU_QUANT` なしの build | この環境変数は参照されない | なし | x4 の選択コード自体が compile-time で除外 |

判定関数は先に `STRATA_NO_DOT_X4 != nullptr` を調べるため、そちらが設定されていれば `STRATA_DOT_X4=1` より優先されます。CLI 引数や設定ファイルによる上書きは、この経路にはありません（`engine/include/strata/quant/dot_x4_policy.hpp:14-17`; `engine/src/kernels/cpu/native_expert.cpp:735-740,860-865`）。

## 有効になる条件

- `STRATA_OWN_CPU_QUANT` を有効にして CPU kernels を build する必要があります。この macro が定義された場合だけ、環境変数判定と x4 kernel lookup のコードがコンパイルされます。root build の option は既定 ON です（`engine/CMakeLists.txt:179-184`; `engine/cmake/backends/cpu.cmake:370-374`）。
- x4 kernel lookup は `STRATA_QUANT_X86_TIERS` がある場合だけ x86 の AVX-512 / AVX2 dot-x4 tables を走査します。該当 build でない場合は lookup が `nullptr` を返し、x4 は使われません（`engine/cmake/backends/quant.cmake:23-28`; `engine/src/quant/dispatch.cpp:66-82`）。
- lookup は weight 型、`Arith::Avx2`、現在の CPU で実行可能な ISA が一致する kernel を探します。gate/up の `WindowInvariant` arithmetic specialization では `flavour_avx2()` が真の場合に限り lookup し、他の specialization ではこの flavor 条件はありません（`engine/src/kernels/cpu/native_expert.cpp:737-740,862-865`; `engine/src/quant/dispatch.cpp:66-78`）。
- `STRATA_NO_DOT_X4` が設定されていると、空文字を含め x4 を無効にします（`engine/include/strata/quant/dot_x4_policy.hpp:14-17`）。
- native expert の gate/up または down fallback dot 部分に到達する必要があります。先行する専用 kernel の分岐で戻る場合、この x4 選択箇所は使われません（`engine/src/kernels/cpu/native_expert.cpp:681-740,751-789,795-865,873-893`）。
- x4 kernel が選ばれても、4 行そろう範囲のみ x4 呼び出しを行い、残りの 0〜3 行は通常の 1 行 dot で処理します（`engine/src/kernels/cpu/native_expert.cpp:751-789,873-893`）。

## 実行時の詳細

gate/up と down それぞれの `native_*_rows_impl` は、専用型 kernel などを試した後、通常 dot に入る位置で環境変数を読みます。判定結果は関数 template 内の `static const bool` に保存されます。したがって各 template specialization について、その箇所に初めて到達した時の値が使われ、その後の同じ specialization ではプロセス実行中の環境変更は再読込されません。gate/up と down、および異なる arithmetic specialization は別々の static です（`engine/src/kernels/cpu/native_expert.cpp:734-740,860-865,898-915`）。

x4 kernel が得られた場合、gate/up は各 token の activation を共有して gate と up の 4 行 dot を計算し、従来どおり scale と SwiGLU を適用します。down は hidden activation を共有して 4 行 dot を計算し、down scale を適用します。処理行が 4 の倍数でないときは端数行を従来の `dot.dot` で計算します。対応 kernel がない場合も `x4 == nullptr` のまま全行が `dot.dot` に進みます（`engine/src/kernels/cpu/native_expert.cpp:751-789,873-893`）。

この変数を読み取るのは Strata の CPU native expert 実装です。CUDA/HIP/SYCL/Metal の GPU dot kernel をこの環境変数が直接切り替える参照は見つかりませんでした。別プロセスへの引き渡しも、この変数の読み取り経路にはありません。起動後に外部から環境を変更しても、上記 static が初期化済みの specialization には反映されません。

## 根拠

- `engine/include/strata/quant/dot_x4_policy.hpp:14-17` — 値の厳密判定と `STRATA_NO_DOT_X4` の優先。
- `engine/src/kernels/cpu/native_expert.cpp:734-789` — gate/up の環境読み取り、kernel lookup、x4 と端数行の処理。
- `engine/src/kernels/cpu/native_expert.cpp:859-893` — down rows の環境読み取り、kernel lookup、x4 と端数行の処理。
- `engine/src/kernels/cpu/pool.cpp:1290-1309,1423-1453` — CPU pool の native gate/up・down 呼び出し。
- `engine/CMakeLists.txt:179-184`; `engine/cmake/backends/cpu.cmake:370-374` — `STRATA_OWN_CPU_QUANT` build option と定義。
- `engine/cmake/backends/quant.cmake:23-28`; `engine/src/quant/dispatch.cpp:66-82` — x86 tier の登録と対応 ISA / 型に対する kernel lookup。
