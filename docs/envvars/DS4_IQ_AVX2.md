# `DS4_IQ_AVX2`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この HEAD では、`DS4_IQ_AVX2` を実行時に読む処理は有効になりません。`src/dsv41/ds4_iq_cpu.cpp` は `STRATA_NATIVE_EXPERTS` を無条件に `#undef` した後、その macro が定義されている場合だけ含める実装を `#if` で囲んでいます。そのブロック内に `DS4_IQ_AVX2` の読み取りが2か所ありますが、このファイルではブロックが常にプリプロセスで除外されます。実際に残る側の関数は汎用 CPU 経路へ委譲し、独自 IQ rows の判定関数は `false` を返します。したがって、この変数を設定してもこの HEAD の Strata 実行ファイルの挙動は変わりません。

除外されたコードのコメントと実装上は、AVX-512 対応 CPU でも独自 IQ 行カーネルの AVX2 版を選ぶためのフックです。ただし、これは現行実行時の機能ではなく、無効なソース分岐に書かれた挙動です。

## 値と判定

現行の有効経路には値の判定がありません。プリプロセス除外されたコードの読み取り箇所では `std::atoi` の結果を使い、未設定でなければ非ゼロを true とします。そこでは空文字や整数として始まらない文字列は `atoi` により 0 となり false、`1`, `-1`, ` 1tail` のように整数接頭部が非ゼロなら true です。文字列全体の一致判定ではありません。

除外コード内でも判定結果は用途ごとに異なります:

- `iq_rows_n<TY>` の `w512` は、`TY` が IQ3_XXS / IQ3_S、コード表が利用可能、CPU が AVX-512 対応であり、かつ `DS4_IQ_AVX2` が非ゼロでない場合に true です。true の場合は AVX-512 rows、false の場合は AVX2 rows に進みます。
- `own(type)` は `DS4_IQ_AVX2` の非ゼロを `force_avx2` として保持します。IQ2_XXS / IQ2_S では AVX-512 対応 CPU 上の独自 rows を通常は除外し、この値が非ゼロならその除外を解除します。
- `DS4_IQ_OWN=0` により独自 rows 自体が無効なら、`DS4_IQ_AVX2` が非ゼロでも独自 rows は使われません。

この値判定の説明はすべてプリプロセスで除外されるコードに関するものです。現在の実行ファイルに有効な既定値や設定値はありません。

## 有効になる条件

現行 HEAD では、CPU アーキテクチャ、IQ type、`DS4_IQ_OWN` の値にかかわらず有効になりません。理由は実行時条件より前に、同じソースファイル内の無条件 `#undef STRATA_NATIVE_EXPERTS` が独自実装ブロックを除外するためです。

除外された実装をソース上で読むと、x86-64 (`IQ_X86`) と AVX2 対応 CPU が必要です。AVX-512 rows との切替は IQ3_XXS / IQ3_S に関係し、AVX-512 対応 CPU 上で IQ2_XXS / IQ2_S の独自 rows を使う場合にも `DS4_IQ_AVX2` が関係します。これらは現在の実行経路の有効条件ではありません。

## 実行時の詳細

有効な `#else` 側では、`iq_cpu_gate_up` と `iq_cpu_down` が trellis type なら trellis CPU 実装、それ以外なら `gg_cpu_*` 実装へ委譲します。`iq_cpu_own_rows` は常に `false` を返します。この側には `DS4_IQ_AVX2` の参照がなく、値の読み取り、キャッシュ、ログ出力もありません。

無効側に書かれた読み取りは、`own(type)` の関数内 static 初期化と `iq_rows_n<TY>` の関数内 static 初期化で行われる設計です。仮にこのブロックが有効なら各初期化時に一度値を取り込み、後からプロセス環境を変更しても再評価しません。しかし現行ソースでは、この初期化コードも実行ファイルに入りません。

## 根拠

- `src/dsv41/ds4_iq_cpu.cpp:7-18`: `STRATA_NATIVE_EXPERTS` を無条件に解除し、その定義を条件に実装を選ぶ。
- `src/dsv41/ds4_iq_cpu.cpp:491-524`: 除外ブロック内の IQ3 AVX-512 / AVX2 rows 選択と `DS4_IQ_AVX2` の値判定。
- `src/dsv41/ds4_iq_cpu.cpp:623-685`: 除外ブロック内の独自 rows 選択、`DS4_IQ_OWN` との相互作用、および `DS4_IQ_AVX2` による AVX-512 CPU 上の IQ2 rows の許可。
- `src/dsv41/ds4_iq_cpu.cpp:716-779`: gate/up/down の有効な `#else` 側の委譲と `iq_cpu_own_rows` の `false` 戻り値。

