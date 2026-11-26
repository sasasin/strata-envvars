# `STRATA_NO_NVFP4_512`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の native CPU expert 行計算で、NVFP4 用の AVX-512 実装を選ばないための設定です。gate/up と down の双方でこの変数が未設定、CPU の AVX-512 条件が成立し、行幅がカーネルの対応範囲なら `nvfp4_avx512` の実装を使います。変数が設定されている場合はこの分岐を飛ばし、後続の NVFP4 AVX2 実装（条件を満たす場合）または既定の dot 実装へ進みます。CPU の NVFP4 行 dispatch のみを制御し、GPU の経路を設定する読み取りは見つかりませんでした。`engine/src/kernels/cpu/native_expert.cpp:720-740,847-863`。

## 値と判定

値の内容は parse されません。gate/up と down のそれぞれで `std::getenv(...) == nullptr` を判定するため、未設定だけが AVX-512 許可です。空文字を含め、何らかの値が設定されていると無効化されます。`1`、`0`、`true`、`false`、大文字小文字、前後の空白、数値としての妥当性は区別されません。`engine/src/kernels/cpu/native_expert.cpp:722-723,849-850`。

| 条件 | 未設定 | AVX-512 を許可する値 | AVX-512 を止める値 |
| --- | --- | --- | --- |
| native CPU expert の gate/up または down 行 | AVX-512 条件と行幅条件を満たせば候補になる | なし（未設定時のみ） | 空文字、`0`、`1`、`false`、任意の文字列 |

この変数自体に数値変換・範囲・境界値はありません。無効値として reject する値もありません。設定の有無だけで判定します。`engine/src/kernels/cpu/native_expert.cpp:722-724,849-852`。

## 有効になる条件

- native expert の CPU 行 dispatcher が呼ばれ、対象の gate/up type または down type が NVFP4 であること。gate/up と down は別々の分岐で判定されます。`engine/src/kernels/cpu/native_expert.cpp:723-725,850-852,898-915`。
- AVX-512 カーネルのビルド対象である x86 CPU build であること。CMake は native expert dispatcher を加え、`STRATA_CPU_X86` の場合に限り NVFP4 AVX-512 ソースをコンパイルします。x86 以外では `cpu_avx512_ok()` は false を返します。`engine/cmake/backends/cpu.cmake:303-317`、`engine/src/kernels/cpu/expert_layout.cpp:42-49`。
- 実行 CPU と OS が `cpu_avx512_ok()` の条件を満たすこと。同関数は `STRATA_FORCE_AVX2` 等の ISA 制限、OSXSAVE、XCR0 の AVX-512 状態保存、および CPUID の機能ビットを確認します。`engine/src/kernels/cpu/expert_layout.cpp:74-112`。
- NVFP4 の行幅 `n` が `nvfp4_512_fits(n)` を満たすこと。これは `n % QK_NVFP4 == 0` かつ block 数が `kMaxBlocks` 以下である条件です。満たさない場合はこの AVX-512 実装を選びません。`engine/src/kernels/cpu/native_expert.cpp:723-725,850-852`、`engine/src/kernels/cpu/nvfp4_avx512.cpp:152`。
- この変数が設定され AVX-512 分岐を止めた後に AVX2 へ進むには、`STRATA_NO_NVFP4_256` も未設定で、CPU が `cpu_avx2_ok()` を満たし、AVX2 の行幅条件も成立する必要があります。したがってこの変数単独では NVFP4 の最適化全体を止めません。`engine/src/kernels/cpu/native_expert.cpp:727-740,854-863`。

## 実行時の詳細

この変数はプロセス起動時ではなく、native CPU expert の gate/up または down 行実装が初めて評価されたときに読み取られます。読み取り結果は関数内 `static const bool` に保存されます。gate/up と down、および `NativeArithmetic` の各テンプレート特殊化にはそれぞれ static があるため、各経路で最初に呼ばれた時点の環境値が使われ、その後の環境変更はその経路の判定に反映されません。公開 row 関数は同じ実装テンプレートへ渡し、pool の処理から呼び出されます。`engine/src/kernels/cpu/native_expert.cpp:560-561,722-725,793-794,849-852,898-915`、`engine/src/kernels/cpu/pool.cpp:1290-1309,1423-1453`。

AVX-512 分岐を使わない NVFP4 行は、まず別設定 `STRATA_NO_NVFP4_256` と CPU / 行幅条件を使って AVX2 実装を試します。その条件も満たさなければ `traits(f.gu_type)` または `traits(f.d_type)` から dot を取得する既定経路へ進みます。`STRATA_OWN_CPU_QUANT` が有効な build では既定 dot は Strata quant layer の traits、無効な build では `pool_quant.hpp` の ggml-cpu traits 側です。いずれの場合も、この変数が直接選択するのは AVX-512 分岐の可否です。`engine/src/kernels/cpu/native_expert.cpp:727-740,854-863`、`engine/cmake/backends/cpu.cmake:364-374`。

## ログと測定値

この設定を読んだこと、AVX-512 を無効にしたこと、または AVX2 / dot に fallback したことを示すログ・警告・終了処理は該当分岐にありません。分岐は計算カーネルの選択を変えます。ソースコメントは AVX-512 経路の測定値として gate/up が 1 token で 1.8x、7 tokens で 3.7x と記していますが、文書 `docs/NVFP4.md` によると測定は cache-resident な 1 expert の gate+up（1280/2560 rows）、AVX-512 CPU 上で、Strata version と機種は記録されていません。この条件を超えた性能差はここでは主張しません。`engine/src/kernels/cpu/native_expert.cpp:720-721`、`docs/NVFP4.md:130-149`。

## 根拠

- 直接読み取りと AVX-512 / AVX2 / dot の gate/up 分岐: `engine/src/kernels/cpu/native_expert.cpp:720-740`
- down 行の同じ分岐: `engine/src/kernels/cpu/native_expert.cpp:847-863`
- AVX-512 CPU 判定と OS / ISA 条件: `engine/src/kernels/cpu/expert_layout.cpp:42-49,74-112`
- NVFP4 AVX-512 build 条件: `engine/cmake/backends/cpu.cmake:303-317`
- NVFP4 AVX-512 行幅条件: `engine/src/kernels/cpu/nvfp4_avx512.cpp:152`
- pool から row dispatcher を呼ぶ箇所: `engine/src/kernels/cpu/pool.cpp:1290-1309,1423-1453`
- 性能値の条件と記載: `docs/NVFP4.md:130-149`
