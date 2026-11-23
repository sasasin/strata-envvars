# `STRATA_NO_DOT_X4`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

CPU の native expert 行計算で使う 4 行共有 activation dot カーネルの選択を止める。未設定なら利用可能な X4 カーネルを試し、設定されていれば値に関係なく選択しない。対象は gate/up 行と down 行で、通常の 1 行 dot にフォールバックする。Strata の quant 層を使う `STRATA_OWN_CPU_QUANT` ビルドでだけこの判定がコンパイルされる（`engine/src/kernels/cpu/native_expert.cpp:734-740, 859-865`、`engine/CMakeLists.txt:179-184`）。

## 値と判定

両方の行計算関数で `std::getenv(...) == nullptr` を `static const bool` に保存する。文字列を parse せず、値が設定されているかだけを見る。空文字も設定済みなので X4 を止める。

| 条件 | unset | X4 を試す | X4 を止める |
|---|---|---|---|
| `STRATA_OWN_CPU_QUANT` が有効 | 有効 | 変数未設定 | `""`、`0`、`1`、`true`、`false`、`0anything`、空白を含む値など、設定された全ての値 |
| `STRATA_OWN_CPU_QUANT` が無効 | 判定コードなし | 該当なし | 該当なし |

`STRATA_OWN_CPU_QUANT` が無効なビルドではこのコードが `#if` ごと除かれ、CPU pool は ggml-cpu の type traits を使うため、この変数は参照されない（`engine/src/kernels/cpu/native_expert.cpp:734-740, 859-865`、`engine/CMakeLists.txt:179-184`）。

## 有効になる条件

- `STRATA_OWN_CPU_QUANT` を有効にしてビルドしていること。CMake option の既定値は ON だが、OFF にすると対象判定はなくなる（`engine/CMakeLists.txt:179-184`）。
- 処理が `native_gu_rows_impl` または `native_down_rows_impl` の末尾に到達すること。これらより前に選択された専用形式カーネルは本変数の判定を通らない（`engine/src/kernels/cpu/native_expert.cpp:653-740, 792-865`）。
- 変数が未設定で、行の型と CPU の ISA に対応する X4 カーネルがあること。lookup は AVX-512 と AVX2 の X4 table から、要求算術 `Avx2` に一致し、CPU が実行可能な最良のカーネルを返す。対象型・ISA がなければ null となり通常 dot に進む（`engine/src/quant/dispatch.cpp:66-85`）。
- `STRATA_FORCE_ISA` の上限も lookup に影響する。`avx2` は AVX-512 を使えなくしつつ AVX2 X4 を残し、`avx` または `sse` は X4 table の ISA 上限を下げるため、X4 lookup は null になる（`engine/include/strata/quant/isa.hpp:27, 43-44`、`engine/src/quant/isa.cpp:48-55, 114-139`、`engine/src/quant/dispatch.cpp:66-85`）。
- gate/up は `Arithmetic == Default` または `flavour_avx2()`、down も同条件であること。`WindowInvariant` は後者の条件を満たさない場合 X4 を使わない（`engine/src/kernels/cpu/native_expert.cpp:737-739, 861-864`）。
- X4 が選ばれても、ループは完全な 4 行まとまりだけを処理する。端数の 1〜3 行は後続の通常 dot で計算する（`engine/src/kernels/cpu/native_expert.cpp:749-789, 871-892`）。

## 実行時の詳細

gate/up と down にそれぞれ `static const` の判定があり、各関数テンプレートの特殊化ごとに、その経路が初めて判定を通る時に環境を読み取る。したがって実行中に環境を変更しても、すでに初期化された判定には反映されない。CLI 引数や別の設定との優先順位はなく、Strata 側の設定上書き・子プロセスへの転送もこの参照箇所にはない（`engine/src/kernels/cpu/native_expert.cpp:734-740, 859-865`）。

X4 カーネルがあれば、gate/up は同じ activation に対する連続 4 行の gate と up の dot を計算し、各結果に scale を適用して SwiGLU を出力する。down は連続 4 行の dot を計算して down scale を掛ける。X4 で処理しない行は `traits(...).dot` による 1 行ずつの計算を行う。X4 の公開契約は `Arith::Avx2` の 1 行 dot と bit-exact な和を返すことだが、性能差はこの調査では測定していない（`engine/src/kernels/cpu/native_expert.cpp:750-789, 872-892`、`engine/include/strata/quant/dot.hpp:18-20`、`engine/include/strata/quant/isa.hpp:6-9`）。

## ログと測定値

この変数の判定、X4 の選択、通常 dot へのフォールバックに関するログや警告はない。Strata の資料にも本変数による測定値は確認できなかった。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:734-740, 749-789` — gate/up の設定有無判定、X4 lookup と計算、通常 dot。
- `engine/src/kernels/cpu/native_expert.cpp:859-865, 871-892` — down の設定有無判定、X4 lookup と計算、通常 dot。
- `engine/src/quant/dispatch.cpp:66-85` — CPU が実行可能な X4 kernel の検索。
- `engine/include/strata/quant/dot.hpp:18-20` — X4 dot の契約。
- `engine/include/strata/quant/isa.hpp:6-9` — `Arith::Avx2` の算術契約。
- `engine/CMakeLists.txt:179-184` — `STRATA_OWN_CPU_QUANT` の既定値と OFF 時の ggml-cpu pool。
