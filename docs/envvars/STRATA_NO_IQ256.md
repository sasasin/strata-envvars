# `STRATA_NO_IQ256`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

## 役割

CPU の native expert gate/up 計算で、AVX2 の i-quant multi-token kernel を選ばないようにする環境変数。`engine/src/kernels/cpu/native_expert.cpp` の `native_gu_rows_impl` が AVX2 対応 CPU と変数の未設定を確認し、条件を満たす i-quant 行に `iq256_gu_rows` を使う。変数が設定されていればこの選択を止める。AVX-512 kernel など、先行する別経路の条件が満たされる場合はそちらが優先され、それ以外は通常の dot 経路へ進む。未設定時も CPU の AVX2 対応、対象形式、token 数などの条件が揃わなければ AVX2 kernel は使われない（`engine/src/kernels/cpu/native_expert.cpp:559-576, 681-709`）。

このスイッチが直接制御するのは上記 i-quant gate/up kernel である。IQ4_NL down の AVX2 kernel、Q4_K gate/up や Q5_1/Q8_0 down の別スイッチ付き kernel、NVFP4 kernel を一括して無効にはしない（`engine/src/kernels/cpu/native_expert.cpp:656-674, 681-709, 792-843, 849-856`）。

## 値と判定

値の内容は変換せず、`std::getenv(...) == nullptr` かどうかだけを見る。したがって未設定なら AVX2 選択を許し、環境変数が存在すれば値を問わず AVX2 選択を禁止する。空文字、`0`、`false`、`1`、その他の文字列はいずれも同じ「設定済み」扱い。数値変換、文字列比較、大文字小文字判定、範囲・境界チェックはない（`engine/src/kernels/cpu/native_expert.cpp:554-555, 576`）。

| 条件 | 未設定 | 設定ありの値（例） | 無効値・境界 |
| --- | --- | --- | --- |
| CPU native expert の AVX2 IQ 判定 | AVX2 kernel の候補になる | 空文字、`0`、`false`、`1`、任意の文字列で AVX2 IQ kernel を候補から外す | 値として無効な文字列という区別はない。値は一切 parse されない |

## 有効になる条件

- `cpu_avx2_ok()` が真であること。CPU が AVX2 を実行できない場合、この変数の有無にかかわらず AVX2 IQ kernel は候補にならない（`engine/src/kernels/cpu/native_expert.cpp:569-576`）。
- native expert の gate/up 行が `native_gu_rows_impl` に到達し、対象 i-quant type であること。コード上の対象 type 値は 16、17、18、21、22、23。AVX-512 側の `iq512_supported` は 16、17、18、21、22 で、23 は AVX2 側だけの対象だが、type 23 は `cpu_vnni_ok()` が真のときの外側条件を満たさない（`engine/src/kernels/cpu/native_expert.cpp:280-286, 681-703`）。
- `nt >= native_gu_mt_min(f.gu_type)` が必要。`STRATA_IQ_MT_MIN` が未設定なら閾値は 2、設定時は `std::atoi` の結果。さらに `NativeArithmetic::WindowInvariant` の実装では `mt_min > 1` のとき singleton IQ を避けるため AVX2 multi-token kernel を呼ばず、通常の dot 経路へ進む（`engine/src/kernels/cpu/native_expert.cpp:540-556, 654-655, 685-703`）。
- AVX-512 kernel が使える場合は AVX-512 が先に選ばれる。`STRATA_NO_IQ256` は AVX-512 判定を無効化しない（`engine/src/kernels/cpu/native_expert.cpp:568, 681-703`）。
- `STRATA_IQ3S_MT1` が設定され、`STRATA_IQ_MT_MIN` が未設定、AVX2 が使用可能、AVX-512 不在、gather 条件も満たされると、IQ3_S gate/up の単一 token 閾値を 1 にする経路がある。`STRATA_NO_IQ256` が設定されている場合、この特別な単一 token 適用も成立しない（`engine/src/kernels/cpu/native_expert.cpp:545-556`）。
- CLI 引数や設定ファイルによる上書きは、この読み取り箇所では行われない。CPU native expert kernel を呼ぶ経路で評価されるため、GPU backend を使う実行でも CPU native expert 計算がなければ効果はない。ソース上、この変数による OS・serve/CLI モード別の値規則はない（`engine/src/kernels/cpu/pool.cpp:1290-1309, 1429-1453`）。

## 実行時の詳細

実際の kernel 選択では、`native_gu_rows_impl` 内の関数ローカル `static const bool avx2` が初回評価時に `cpu_avx2_ok()` と変数の未設定状態を保存する。以後その static の値は同一プロセス内で再利用され、実行中に環境を変更してもこの判定には反映されない。`native_gu_mt_min` の閾値も別の関数ローカル static として初回に読み取られる（`engine/src/kernels/cpu/native_expert.cpp:540-556, 559-576`）。

AVX2 kernel が選択候補となる場面で変数が設定されていると、`iq256_gu_rows` の呼び出しを通らない。AVX-512 など先行する別経路に該当しなければ、通常の `traits(f.gu_type).dot` を各 token・row に適用する経路へ進む。gate/up の後続処理（SiLU gate と up の積）は共通の行計算部分に残る。したがってこの変数は対象 dot kernel の選択を変えるもので、Strata のソースから token 選択やモデル出力が同一になることまでは保証できない（`engine/src/kernels/cpu/native_expert.cpp:681-709, 734-789`）。

関数外の読み取りは engine が CPU expert kernel tier を stderr に表示する際の判定で、実計算の static 判定とは別に `getenv` を呼ぶ。標準 engine は native pack かつ `!cpu_vnni_ok()` の分岐で表示し、SYCL engine も `!cpu_vnni_ok()` のときに表示する。表示は AVX2 対応 CPU で変数が設定済みなら、それぞれ `ggml-cpu (STRATA_NO_IQ256 set)` または `ggml-cpu vec_dot (STRATA_NO_IQ256 set)` とするが、これは tier の説明であり、実計算では対象形式・token 数等の条件を個別に判定する（`engine/src/program/generate.cpp:5619-5635`; `engine/sycl/src/program/generate.cpp:2900-2909`）。

ソース全体の名前検索では、CPU/SYCL の parity test 登録がテスト実行時に `STRATA_NO_IQ256=1` を設定する記述、`terminal/data/settings-register.json` の環境変数台帳、コメント・benchmark 文書にも名前がある。これらは製品 runtime の追加読み取り箇所ではない。動的な名前を env helper に渡して読む箇所も確認されなかった（テスト登録: `engine/cmake/backends/cpu.cmake:407`, `engine/sycl/CMakeLists.txt:445`）。

## ログと測定値

標準 engine と SYCL engine は上記条件下で stderr に CPU expert kernel tier を表示する。AVX2 対応で変数が設定済みの場合の末尾は `ggml-cpu (STRATA_NO_IQ256 set)`（標準 engine）または `ggml-cpu vec_dot (STRATA_NO_IQ256 set)`（SYCL engine）。AVX2 非対応時は別の older-CPU 表示となり、この変数名を含む表示にはならない。標準 engine の tier 表示は native pack かつ `!cpu_vnni_ok()` の場合だけで、SYCL engine も `!cpu_vnni_ok()` の場合に限られる（`engine/src/program/generate.cpp:5598-5635`; `engine/sycl/src/program/generate.cpp:2880-2909`）。

この変数を設定した状態での性能値や出力一致を一般化できる測定根拠は、調査対象ソースから確認していないため記載しない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:540-556` — `STRATA_IQ3S_MT1` と対象変数の相互作用、multi-token 閾値。
- `engine/src/kernels/cpu/native_expert.cpp:559-576` — AVX-512/AVX2 判定と static cache。
- `engine/src/kernels/cpu/native_expert.cpp:280-286, 681-709` — 対象 type と kernel 選択順。
- `engine/src/kernels/cpu/native_expert.cpp:734-789` — fallback dot と共通の gate/up 後続処理。
- `engine/src/kernels/cpu/pool.cpp:1290-1309, 1429-1453` — native expert worker からの呼び出し。
- `engine/src/program/generate.cpp:5619-5635` — 標準 engine の tier 表示。
- `engine/sycl/src/program/generate.cpp:2900-2909` — SYCL engine の tier 表示。
