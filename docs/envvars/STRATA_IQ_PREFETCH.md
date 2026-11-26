# `STRATA_IQ_PREFETCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の x86 CPU expert row kernels が、重みブロックの読み取り中に現在のブロックから何 byte 先をソフトウェア prefetch するかを指定する。AVX1、AVX2、AVX-512 の各実装で `std::getenv` から読み、正の値なら現在の重みブロック `blk` から `N` byte と `N+64` byte の 2 箇所に `_MM_HINT_T0` の prefetch を要求する。0 以下ではこの要求を行わない。行の積和計算、expert の選択、出力値を直接変更する分岐ではない（`engine/src/kernels/cpu/iq_avx1.cpp:133-145,239-245`; `engine/src/kernels/cpu/iq_avx2.cpp:178-195`; `engine/src/kernels/cpu/iq_avx512.cpp:48-53,216-224`）。

この変数が使われるのは native CPU expert dispatcher が対応 kernel を選んだ場合だけである。AVX2 側は gate/up i-quant rows と IQ4_NL down rows、AVX-512 側は gate/up i-quant rows と Q5_0 down rows、AVX1 側は gate/up rows と IQ4_NL / Q2_0 down rows に組み込まれている（`engine/src/kernels/cpu/native_expert.cpp:681-708,820-835,840-844`; `engine/src/kernels/cpu/iq_avx1.cpp:310-326,345-361,394-444`; `engine/src/kernels/cpu/iq_avx2_rows.inl:618-625`; `engine/src/kernels/cpu/iq_avx512.cpp:795-807`）。pool の native expert 経路から dispatcher が呼ばれる（`engine/src/kernels/cpu/pool.cpp:1290-1309`）。

## 値と判定

各実装は `std::getenv` の返す文字列を `std::atoi` に渡す。未設定だけが既定値 `2048` になる。空文字は設定済みなので `atoi("") == 0` となり prefetch を無効にする。文字列全体の検証や上限 clamp はなく、`atoi` が先頭から変換できる整数を返すため、例として `64tail` は 64、`true`・空白だけ・`0anything` は 0、`-1` は負値になる。先頭の空白や符号は `atoi` の規則で扱われる。大文字小文字の比較はない。数値変換可能範囲を超える入力の結果は C の `atoi` の範囲外動作となり、Strata 側に独自のエラー処理はない（`engine/src/kernels/cpu/iq_avx1.cpp:134-139`; `engine/src/kernels/cpu/iq_avx2.cpp:184-190`; `engine/src/kernels/cpu/iq_avx512.cpp:50-53`）。

| 読み取り実装 | unset | 正の変換値 | 0 / 負値 / 変換できない値 |
|---|---:|---|---|
| AVX1 (`iq_avx1.cpp`) | 2048 byte | `blk + N`, `blk + N + 64` を prefetch | prefetch なし |
| AVX2 (`iq_avx2.cpp`) | 2048 byte | `blk + N`, `blk + N + 64` を prefetch | prefetch なし |
| AVX-512 (`iq_avx512.cpp`) | 2048 byte | `blk + N`, `blk + N + 64` を prefetch | prefetch なし |

`1` は 1 byte 先、`2048` は 2048 byte 先、`16384` は 16384 byte 先を指す。正の値に下限以外の妥当性検査はなく、設定値の単位は byte である。AVX1/AVX2 は関数内 `static const int` に初回評価値を保存し、AVX-512 は translation unit の静的初期化時に値を保存する。したがって実行中に環境を変更しても再読込されない（同上）。

## 有効になる条件

- x86 向け native CPU kernels が build に含まれていること。CPU CMake は `STRATA_CPU_X86` の場合に AVX1/2/512 のソースを追加する。SYCL の native-expert 構成も同ソースを含む（`engine/cmake/backends/cpu.cmake:303-317`; `engine/sycl/CMakeLists.txt:220-247`）。非 x86 build にはこれらの x86 kernel translation units が追加されない（`engine/cmake/backends/cpu.cmake:308-317`）。
- 実行時に pool が native expert row dispatcher を通り、対応する kernel が選択されること（`engine/src/kernels/cpu/pool.cpp:1290-1309`; `engine/src/kernels/cpu/native_expert.cpp:560-584,681-708,820-844`）。CPU ISA、format、token 数の threshold によって generic ggml dot や別 kernel に進む場合、この値はその row 計算には使われない。AVX2 の exact-one gate/up 分岐は `gu_ggml_one` を呼び、通常の row loop の `prefetch_distance()` を通らない（`engine/src/kernels/cpu/native_expert.cpp:594-599`; `engine/src/kernels/cpu/iq_avx2.cpp:457-489`）。
- AVX-512 gate/up kernel は `cpu_vnni_ok()` と `STRATA_NO_IQ512` 未設定が選択条件。AVX2 は `cpu_avx2_ok()` と `STRATA_NO_IQ256` 未設定、AVX1 は AVX2 がなく `cpu_avx1_ok()` かつ `STRATA_NO_IQ128` 未設定が条件（`engine/src/kernels/cpu/native_expert.cpp:568-584,694-708`）。これらの `STRATA_NO_*` 値の parse は別設定であり、本変数の値の parse には影響しない。
- AVX1 down kernel は IQ4_NL (type 20) と Q2_0 (type 42) のみ。AVX1 gate/up dispatcher が直接対応するのは IQ3_XXS (18), IQ3_S (21), IQ2_S (22)（`engine/src/kernels/cpu/iq_avx1.cpp:394-404`）。AVX2 gate/up rows は native dispatcher の `iq256_supported` 判定を通る形式、AVX2 down は IQ4_NL (type 20) の経路（`engine/src/kernels/cpu/native_expert.cpp:681-703,828-831`）。AVX-512 gate/up rows は types 16, 17, 18, 21, 22 を switch で処理し、down 側では Q5_0 (type 6) 分岐が `q50_512_down_rows` を呼ぶ（`engine/src/kernels/cpu/iq_avx512.cpp:618-628,641-649`; `engine/src/kernels/cpu/native_expert.cpp:820-826`）。
- `STRATA_IQ_PREFETCH` を無効化・上書きする専用 CLI 引数や設定ファイルの読み取りは、Strata ソース内で確認できない。別 ISA kernel/generic fallback への dispatcher 選択や、format・token 条件の不成立は結果的に本値を使わない。

## 実行時の詳細

AVX1/AVX2 では `prefetch_distance()` の最初の呼び出しで環境変数を取得して関数内 static に保存する。その後、row dot の各 weight block loop が保存値を `rows_ahead` に渡し、正値の場合だけ 64 byte 間隔の 2 箇所に T0 prefetch を発行する（`engine/src/kernels/cpu/iq_avx1.cpp:134-145,237-245`; `engine/src/kernels/cpu/iq_avx2.cpp:184-195`; `engine/src/kernels/cpu/iq_avx2_rows.inl:81-88`）。AVX1 の IQ4_NL と Q2_0 down rows も同じ helper を使う（`engine/src/kernels/cpu/iq_avx1.cpp:310-326,345-361`）。AVX2 の IQ4_NL down rows も `prefetch_distance()` を使う（`engine/src/kernels/cpu/iq_avx2_rows.inl:618-625`）。

AVX-512 は `prefetch_ahead` を静的初期化で一度決め、i-quant row loops と Q5_0 down rows で正値の場合に同じ 2 箇所を prefetch する（`engine/src/kernels/cpu/iq_avx512.cpp:50-53,206-224,795-807`）。値を CLI・リクエストごとに再評価する処理、設定値を検証して失敗させる処理、値に関する fallback や理由ログは見当たらない。0 以下は単に prefetch 呼び出しを skip する。Strata 側に prefetch が失敗した場合の分岐・終了処理はない。

## ログと測定値

通常の native kernels はこの値をログに出さない。`iq_avx2_parity` 診断プログラムは raw 環境文字列を `STRATA_IQ_PREFETCH` 欄に表示し、未設定なら `-` と表示するが、これは診断プログラムの出力であり通常の engine 起動ログではない（`engine/src/kernels/cpu/iq_avx2_parity.cpp:561-568`）。

ソースコメントは AVX2 の IQ3_S decode について、Zen 3 5700X3D（AVX-512 なし）で gate/up phase 4% 減、行読み取り +1.0 GB/s、round 全体 -1.3% と報告し、AVX-512 コメントは IQ3_S decode の gate/up time 2–3% 減と記す（`engine/src/kernels/cpu/iq_avx2.cpp:178-183`; `engine/src/kernels/cpu/iq_avx512.cpp:48-49`）。コメントに測定手順・反復回数・build 条件の全ては示されていないため、これらはその記述の範囲に限られ、一般的な性能保証ではない。調査中に測定は行っていない。

## 根拠

- `engine/src/kernels/cpu/iq_avx1.cpp:133-145,237-245,310-326,345-361,394-444`
- `engine/src/kernels/cpu/iq_avx2.cpp:178-195`
- `engine/src/kernels/cpu/iq_avx2_rows.inl:81-88,618-625`
- `engine/src/kernels/cpu/iq_avx512.cpp:48-53,206-224,618-628,795-807`
- `engine/src/kernels/cpu/native_expert.cpp:560-584,594-599,681-708,820-844`
- `engine/src/kernels/cpu/pool.cpp:1290-1309`
- `engine/cmake/backends/cpu.cmake:303-317`; `engine/sycl/CMakeLists.txt:220-247`
- `engine/src/kernels/cpu/iq_avx2_parity.cpp:561-568`
