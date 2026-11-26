# `STRATA_IQ256_GATHER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の x86 AVX2 native expert i-quant 行で、IQ3_XXS・IQ3_S・IQ2_S の格子値を scalar load で組み立てるか、AVX2 gather 命令で読むかを選ぶ。通常の unset は CPU と実行 thread の core type に応じた自動選択で、`0` は全 core で scalar、非ゼロは全 core で gather を選ぶ。`iq256_variant()` は gather bit と、別判定の AVX-VNNI bit を組み合わせる。対象の格子値・計算結果は variant 間で同じとコードコメントに記されているが、この変数が出力選択や model routing を変える分岐はない（`engine/src/kernels/cpu/iq_avx2.cpp:14-19, 491-495`、`engine/include/strata/kernels/cpu/iq_avx2.hpp:33-39`）。

## 値と判定

`iq256_gather_setting()` は `std::getenv` で読み、未設定または空文字なら `-1`（auto）、それ以外は `std::atoi(v) != 0` の結果を `1` または `0` にする。数値文字列全体の検証はせず、`atoi` が先頭から読める整数を使う。したがって先頭空白は許容され、整数の後ろは無視され、数値変換できない文字列は `0` になる（`engine/src/kernels/cpu/expert_layout.cpp:310-317`）。

| 値 | `iq256_gather_setting()` | gather 選択 |
|---|---:|---|
| unset、空文字 | -1 | calling thread の core 判定に従う |
| `0`、`0anything`、`true`、空白だけ | 0 | scalar decode |
| `1`、`2`、`-1`、`1anything` | 1 | gather decode |

負数も `atoi` 結果が非ゼロなので gather になる。大文字小文字の比較はない。文字列が整数に変換できるか以外の妥当性検査、範囲制限、警告・fallback はない（同 `expert_layout.cpp:310-317`）。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` が有効な build で `iq_avx2.cpp` がビルドに含まれ、CPU native expert の AVX2 kernel を使う経路であること。CMake は x86 native expert build に同ファイルを追加し、AVX2/FMA/F16C でコンパイルする（`engine/cmake/backends/cpu.cmake:303-323, 335-370`）。非 x86 では probe が false を返し、x86 gather kernel は選択されない（`engine/src/kernels/cpu/expert_layout.cpp:42-50`）。
- CPU native expert の gate/up kernel が実際に AVX2 IQ kernel に達すること。dispatch は AVX2 capability と `STRATA_NO_IQ256` 未設定を要求し、AVX-512 IQ kernel が選ばれる場合はそちらが先になる。通常の gate/up multi-token 経路では `nt >= native_gu_mt_min(...)` も必要（`engine/src/kernels/cpu/native_expert.cpp:564-576, 654-704`）。
- gather variant が有効でも、gather decode を実装している形式は IQ3_XXS (18)、IQ3_S (21)、IQ2_S (22) のみ。他の IQ format は scalar variant のまま（`engine/src/kernels/cpu/iq_avx2.cpp:314-346, 457-488`）。
- unset の自動判定は x86 の Intel CPU に限る。`cpu_gather_fast()` は `STRATA_FORCE_ISA` が通常上限 (`cpu_isa_cap()==3`) であること、Intel vendor、CPUID leaf 7.1 の AVX-VNNI bit、E-core-only として列挙された model でないことを要求する。hybrid CPU ではさらに calling thread が CPUID core type `40h`（P-core）である必要があり、E-core や不明な hybrid core は scalar を選ぶ。明示的な非ゼロ値はこの性能 probe を使わず全 core で gather を選ぶ（`engine/src/kernels/cpu/expert_layout.cpp:320-358`）。
- IQ3_S は別の単一 token 条件にも影響する。`STRATA_IQ_MT_MIN` が未設定、`STRATA_IQ3S_MT1` が設定あり、AVX2 が利用可能、`STRATA_NO_IQ256` が未設定、AVX-512 が無効、かつこの変数の判定値が `0` でなく `cpu_gather_fast()` が true の場合、`native_gu_mt_min()` は IQ3_S だけ閾値を 1 にする。このため gather が速いと判定された CPU では IQ3_S の単一 token も AVX2 multi-token kernel に入る。`STRATA_IQ_MT_MIN` が設定されていれば（空文字を含む）この自動規則は使われず、`STRATA_IQ3S_MT1` は値を parse せず設定有無だけを見る（`engine/src/kernels/cpu/native_expert.cpp:540-556`）。

## 実行時の詳細

実処理側の環境変数読み取りは `iq256_gather_setting()` 内の関数 static に保存される。最初の問い合わせ時に一度評価し、以後プロセス中に環境を変更しても更新されない。unset の auto 判定では `cpu_gather_fast()` の CPU probe も static、hybrid CPU の core type 判定は `cpu_gather_fast_here()` を呼んだ各 thread ごとに `thread_local` で一度保存される（`engine/src/kernels/cpu/expert_layout.cpp:310-358`）。

AVX2 native gate/up dispatch は対象 kernel を選んだ後、`iq256_gu_rows()` から `iq256_variant()` を呼ぶ。gather bit が立つと IQ3_XXS・IQ3_S・IQ2_S の decode が格子 table への gather load を使い、立たなければ既存の scalar decode を使う。AVX-VNNI の選択は別 bit であり、この変数の値で有効・無効にはならない（`engine/src/kernels/cpu/native_expert.cpp:694-704`、`engine/src/kernels/cpu/iq_avx2.cpp:457-495, 500-535`）。

## ログと測定値

engine の通常 dispatch に、この変数の有効・無効や理由を表示するログは見つからない。`iq_avx2_parity` は起動時に `std::getenv` を包む動的 helper で値を表示するが、これは parity/bench 用ツールの診断表示であり、engine の選択ログではない。AVX2 がなければ同ツールは `iq_avx2_parity: no AVX2 here, nothing to check (the engine takes ggml-cpu's dot)` と出して終了する（`engine/src/kernels/cpu/iq_avx2_parity.cpp:562-575`）。

`docs/DETAILS.md` は `STRATA_IQ_MT_MIN` による CPU IQ arithmetic と出力再現性の説明を載せているが、`STRATA_IQ256_GATHER` 固有の設定説明や測定値は見つからなかった（`docs/DETAILS.md:388-396, 1281`）。このため本書では性能差の数値を記載しない。

## 根拠

- `engine/src/kernels/cpu/expert_layout.cpp:310-317` — 値の読み取り、空文字、整数変換、cache。
- `engine/src/kernels/cpu/expert_layout.cpp:320-358` — auto 用 CPU/core 判定と probe cache。
- `engine/include/strata/kernels/cpu/expert_layout.hpp:73-83` — helper の契約と core 判定の説明。
- `engine/src/kernels/cpu/iq_avx2.cpp:14-21, 314-346, 457-495, 500-535` — gather 対象形式、variant、kernel dispatch。
- `engine/src/kernels/cpu/native_expert.cpp:540-556, 564-576, 654-704` — IQ3_S の単一 token 条件と AVX2 native expert の到達条件。
- `engine/cmake/backends/cpu.cmake:303-323, 335-370` — `STRATA_NATIVE_EXPERTS`、x86 native expert build と AVX2 compile flags。
- `engine/src/kernels/cpu/iq_avx2_parity.cpp:562-575` — parity tool の動的な表示と AVX2 不在時の終了表示。
- `docs/DETAILS.md:388-396, 1281` — 関連する IQ multi-token 説明との照合。
