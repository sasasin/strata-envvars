# `STRATA_NO_KQ512`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU の native expert 行計算で使う AVX-512 VNNI の K-quant 多 token カーネルを無効にするスイッチ。無効化対象は gate/up の Q4_K（型 12）と down の Q5_1（型 7）・Q8_0（型 8）。変数が未設定で、ほかの適用条件も満たす場合はこの経路を選択できる。gate/up と down の両方が `native_expert.cpp` から `native_gu_rows` / `native_down_rows` として CPU expert pool に呼ばれる。`STRATA_NATIVE_EXPERTS` が無効な build や CPU native expert 行経路を使わない実行には、この分岐は適用されない（`engine/CMakeLists.txt:178,642-652`; `engine/cmake/backends/cpu.cmake:299-313`; `engine/src/kernels/cpu/pool.cpp:1274-1309`）。

この変数は AVX-512 カーネルを選ばないようにするだけで、出力を捨てたり、CPU expert 処理全体を止めたりするものではない。条件に合わない場合は後続の別カーネルまたは通常の dot 経路へ進む（`engine/src/kernels/cpu/native_expert.cpp:653-675,791-817`）。

## 値と判定

`std::getenv("STRATA_NO_KQ512") == nullptr` だけを条件にする。文字列を数値・真偽値に変換せず、空文字も含め、環境変数が設定されていれば AVX-512 KQ 経路を無効にする（`engine/src/kernels/cpu/native_expert.cpp:661,807`）。

| 条件 | 未設定 | 有効になる値（AVX-512 KQを止める） | 無効になる値（AVX-512 KQを止めない） |
| --- | --- | --- | --- |
| x86 build で CPU native expert 行関数を使う場合 | スイッチなし。AVX-512 CPU判定等を満たせば候補になる | 空文字、`0`、`1`、`false`、任意の文字列（いずれも設定あり） | なし。設定された値の内容は判定しない |
| 非x86 build、AVX-512非対応、または native expert 行経路を使わない場合 | KQ512経路は使われない | 設定値にかかわらず対象外 | 同左 |

数値の境界・負値・大文字小文字・前後空白の規則はない。文字列全体を解釈しないため、たとえば `0anything` や ` FALSE ` も「設定あり」として無効化する側に入る（同上）。

## 有効になる条件

- この変数が未設定であること。明示的な空文字は無効化指定として扱われる（`engine/src/kernels/cpu/native_expert.cpp:661,807`）。
- `STRATA_NATIVE_EXPERTS` を含む CPU native expert の実装が build に入り、その native expert 行処理を実行すること（`engine/CMakeLists.txt:178,642-652`; `engine/cmake/backends/cpu.cmake:299-313`）。
- x86 で AVX-512 対応判定が成功すること。`cpu_avx512_ok()` は OS の AVX-512 状態保存対応と CPUID feature を確認し、`STRATA_FORCE_ISA=avx2` 等の ISA cap や `STRATA_FORCE_AVX2` がその判定を下げる場合は候補にならない。非x86 では判定関数が `false` を返す（`engine/src/kernels/cpu/expert_layout.cpp:26-48,74-112`）。
- 行の型が gate/up なら 12、down なら 7 または 8 であること。さらに、その type の dot/量子化 trait を使う初回照合が成功し、`STRATA_KQ512_MIN` で決まる token 数以上であること（`engine/src/kernels/cpu/native_expert.cpp:294-358,661-665,807-811`）。
- `NativeArithmetic::WindowInvariant` の場合は、上記に加えて `flavour_avx2()` が true であること。既定 arithmetic ではこの追加条件は不要（同上）。
- `STRATA_KQ512_MIN` の既定値は 8。これを指定すると `atoi` で整数化され、範囲制限はない。0 や負数なら正の `nt` は通常この下限を満たし、空文字や数値で始まらない文字列は `atoi` により 0 になる（`engine/src/kernels/cpu/native_expert.cpp:662,664,808,810`）。
- `STRATA_KQ256` は別の AVX2 多 token 経路を有効にできる。`STRATA_NO_KQ512` を設定しても `STRATA_KQ256` の判定は独立しており、AVX2対応かつ同経路の条件を満たせば、その後に `kq256_gu_rows` / `kq256_rows` が選ばれることがある（`engine/src/kernels/cpu/native_expert.cpp:658-672,798,814-817`）。

## 実行時の詳細

gate/up と down の実装はそれぞれ `static const bool kq512` を初回に評価し、その結果を以後の呼び出しで使う。`Default` と `WindowInvariant` はテンプレートの別実体で、gate/up と down も別関数なので、それぞれが初回到達時に判定をキャッシュする。実行中に環境を変更しても、初回評価済みの実体には反映されない。AVX-512 CPU 判定も `cpu_avx512_ok()` 内で static cache される（`engine/src/kernels/cpu/native_expert.cpp:661,807,895-915`; `engine/src/kernels/cpu/expert_layout.cpp:80-112`）。

未設定で AVX-512 が利用可能な場合、行型と `nt` の条件を満たした gate/up は `kq512_gu_rows`、down は `kq512_rows` に渡る。実装は Q4_K gate/up、Q5_1 / Q8_0 down の行を複数 token 単位で計算する。token 下限は別変数 `STRATA_KQ512_MIN` が決める（`engine/src/kernels/cpu/native_expert.cpp:659-665,806-811`; `engine/src/kernels/cpu/kq_avx512.cpp:278-302,305-330`）。

初回の型ごとの照合 `kq512_ok()` は synthetic blocks で当該カーネルの結果と build 内 dot の結果を比較し、結果を型ごとに memoize する。不一致なら `false` となり、AVX-512 行カーネルを選ばず後続の経路へ進む（`engine/src/kernels/cpu/native_expert.cpp:294-358,663-665,809-811`）。

## ログと測定値

`STRATA_NO_KQ512` が設定されていること自体に対するログはない。照合不一致時には stderr に `strata: the AVX-512 rows of type %d differ from this build's dot (n=%d, %d tokens): its dot runs per token instead` を出し、その型の AVX-512 経路を使わない（`engine/src/kernels/cpu/native_expert.cpp:348-350`）。

`docs/DETAILS.md:1183` は unset 時の既定、対象 row、初回照合、`STRATA_KQ512_MIN` を記載している。コードの値判定は設定有無であり、資料表の `STRATA_NO_KQ512=1` は無効化例として読めるが、`=1` のみを有効値とする実装ではない。資料記載の性能値はこの調査で再測定していない。

## 根拠

- 読み取り箇所と gate/up の分岐: `engine/src/kernels/cpu/native_expert.cpp:659-665`
- down の分岐と別 AVX2 経路: `engine/src/kernels/cpu/native_expert.cpp:806-817`
- 対応型・初回照合・不一致時ログ: `engine/src/kernels/cpu/native_expert.cpp:287-358`
- AVX-512 CPU feature / OS state 判定: `engine/src/kernels/cpu/expert_layout.cpp:74-112`
- native expert pool からの呼び出し: `engine/src/kernels/cpu/pool.cpp:1274-1309`
- AVX-512 source の x86 build 条件: `engine/cmake/backends/cpu.cmake:299-313,337-338`
- 補足資料: `docs/DETAILS.md:1176-1184`; 候補一覧の説明は `docs/SETTINGS.md:404`
