# `STRATA_NO_IQ128`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

AVX2 を使えない一方で AVX1 を使える CPU 上の native expert 計算で、Strata 独自の 128-bit i-quant CPU カーネルを使わず、ggml-cpu の `vec_dot` にフォールバックさせるための開発・診断用スイッチである。通常の canonical pack 向け CPU expert 実装や CUDA/HIP/SYCL の GPU カーネルを切り替える変数ではない。

対象の native expert は native pack のゲート／アップ行とダウン行を CPU pool から計算する経路である。ゲート／アップでは IQ3_XXS、IQ3_S、IQ2_S、ダウンでは IQ4_NL、Q2_0 が 128-bit カーネルの対応形式。IQ4_XS のゲート／アップ行はこのカーネルの対応形式に含まれず、もともと ggml-cpu の dot に進む。

## 値と判定

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | `std::getenv(...) == nullptr` となり、CPU 条件も満たせば 128-bit カーネルを候補にする |
| 設定あり（空文字を含む） | `std::getenv(...) != nullptr` となり、128-bit カーネルを無効にする |

値を数値や真偽値に変換せず、文字列の内容も比較しない。したがって `0`、`1`、その他の文字列はいずれも「設定あり」として同じ無効化判定になる。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS=ON` でビルドされ、native expert の実装が組み込まれていること。CMake では同機能が既定で ON だが、ビルド時に OFF にできる。
- 実行時 CPU が `cpu_avx1_ok()` を満たし、`cpu_avx2_ok()` を満たさないこと。AVX1 判定は AVX、OSXSAVE、および OS による SSE/AVX 状態保存を確認する。
- native expert の形式が該当カーネルに対応すること。

AVX2 対応 CPU では AVX1 カーネル選択条件を満たさず、この変数はその経路の選択に影響しない。AVX1 非対応 CPU でも同様に AVX1 カーネルは使われない。別の `STRATA_NO_IQ256` は AVX2 側の選択スイッチであり、この変数とは独立している。

## 実行時の詳細

`native_gu_rows` は、AVX1 カーネルを使える CPU で、`STRATA_NO_IQ128` が未設定であり、かつトークン数 `nt` が `STRATA_IQ_MT_MIN` の閾値以上の場合に、対応するゲート／アップ行を 128-bit カーネルで処理する。`STRATA_IQ_MT_MIN` の既定値は 2 で、値は `atoi` で整数化される。閾値に達しない場合、または本変数が設定されている場合は ggml-cpu の `vec_dot` を各行・各トークンに適用する。

`native_down_rows` は、AVX1 カーネルを使える CPU で本変数が未設定なら、対応するダウン行を 128-bit カーネルへ渡す。この箇所には `nt` の閾値条件がない。本変数が設定されている場合は ggml-cpu の `vec_dot` にフォールバックする。Q2_0 ダウン行は AVX2 対応 CPU では pool 側の別カーネル経路に入るため、この AVX1 選択条件の対象にならない。

両カーネル選択関数内の判定は関数ローカル `static const bool` として初回呼び出し時に評価され、その値がプロセス内で再利用される。起動後に環境を変更しても、既に初期化されたカーネル選択値には反映されない。`strata generate` は native pack の起動時に CPU が AVX-512 非対応なら、同じ設定有無を直接確認し、stderr に利用する CPU カーネル系統（AVX1 128-bit または ggml-cpu）を表示する。

## 根拠

- `CMakeLists.txt:1210-1218,1265-1270` — native expert 機能の既定オプションと、CPU カーネル群をビルドへ追加する条件。
- `src/kernels/cpu/native_expert.cpp:134-158,167-195` — native ゲート／アップ行の CPU 条件、環境判定、`STRATA_IQ_MT_MIN` との相互作用、および ggml-cpu へのフォールバック。
- `src/kernels/cpu/native_expert.cpp:199-233` — ダウン行の AVX1 選択とフォールバック。
- `src/kernels/cpu/iq_avx1.cpp:396-405` — 128-bit ゲート／アップおよびダウンカーネルが対応する GGML type。
- `src/kernels/cpu/expert_layout.cpp:139-163` — AVX1 CPU 機能判定。
- `src/kernels/cpu/pool.cpp:649-662`; `include/strata/kernels/cpu/expert_layout.hpp:81` — native expert pool から各行処理が呼ばれることと、Q2_0 の AVX2 条件付き別経路。
- `src/program/generate.cpp:2714-2715,2774-2783` — native pack の識別、canonical pack の CPU 要件確認、および起動時の stderr 表示。
- `CMakeLists.txt:1227-1248,1299-1305` — portable／ISA floor 別の ggml CPU ビルド条件と AVX1 floor の定義。
- `docs/DETAILS.md:215-228` — native pack の GGUF 読み取りと Linux file-tier I/O の説明。本変数や AVX1 CPU カーネル選択の説明はなく、詳細な切り替え条件は上記ソースに基づく。
