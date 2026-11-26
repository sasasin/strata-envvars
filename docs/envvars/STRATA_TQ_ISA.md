# `STRATA_TQ_ISA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CPU の trellis 量子化（TQ/Gyro）expert 行カーネルが使う命令セットを上限指定する。値は `tq_isa()` が選ぶ ISA を scalar または AVX2 に制限できる。未指定時は x86 CPU が使える AVX-512、AVX2、scalar の順に選ぶ。これはモデルの量子化形式や GPU カーネルを切り替える設定ではなく、CPU native expert の trellis 行処理に渡す ISA の選択だけを変える（`engine/src/kernels/cpu/tq_cpu.cpp:48-55,167-175`、`engine/src/kernels/cpu/native_expert.cpp:675-679,803-805`）。

## 値と判定

`std::getenv` で文字列を取得し、未設定または空文字なら上限 `2`（制限なし）とする。文字列全体を大文字小文字を区別して比較するのは `scalar` と `avx2` だけで、それぞれ上限 `0` と `1`。それ以外はすべて上限 `2` になる。数値変換や前後空白の除去はない（`engine/src/kernels/cpu/tq_cpu.cpp:48-55`）。

| 条件 | unset / 空文字 | 値と選択への上限 | 無効値の扱い |
|---|---|---|---|
| x86-64 | 上限 2。実 CPU で実行可能なら AVX-512、次に AVX2、どちらも不可なら scalar | `scalar` → 0（scalar 固定）、`avx2` → 1（AVX2 以下）。`avx512` も特別分岐はないが、その他の文字列と同じ上限 2 | `0`、`1`、`true`、`false`、`AVX2`、`avx2 ` などは上限 2となり、未指定時と同じ自動選択 |
| x86-64 以外（AVX ユニットを含まないビルド） | scalar | 指定値にかかわらず scalar | 不正値エラーや警告はなく scalar |

x86 の AVX-512 と AVX2 はそれぞれ `cpu_avx512_ok()` / `cpu_avx2_ok()` が true の場合だけ候補になる。環境変数が CPU にない命令を強制することはなく、`avx2` 指定でも AVX2 非対応なら scalar に落ちる（`engine/src/kernels/cpu/tq_cpu.cpp:155-164,167-175`）。

## 有効になる条件

- `tq_cpu.cpp` を含む CPU native expert ビルドであること。x86 の通常ビルドでは AVX2 / AVX-512 の各翻訳単位もビルド対象になり、非 x86 では dispatcher と scalar 行カーネルを含む（`engine/cmake/backends/cpu.cmake:303-317,343-346`）。Metal は `tq_cpu.cpp` の scalar 実装を含む（`engine/metal/CMakeLists.txt:145-146`）。SYCL も CPU native expert 用に trellis CPU 行カーネル一式を加え、コメント上 GPU 側の trellis 経路とは区別されている（`engine/sycl/CMakeLists.txt:220-240`）。
- 実行時に CPU native expert の gate/up または down 行処理へ trellis 型が渡ること。gate/up は `tq_rows_own(f.gu_type)`、down は `tq_rows_own(f.d_type)` が真のとき `tq_isa()` を渡す（`engine/src/kernels/cpu/native_expert.cpp:38-48,675-679,803-805`）。非 trellis 型や他の実行経路ではこの変数を参照しない。
- `STRATA_NO_TQ_KERNELS` との関係: `tq_rows_own` は trellis 型で、`tq_kernels_enabled()` が true なら常に Strata の行カーネルを使う。`STRATA_NO_TQ_KERNELS` が `atoi` で非ゼロとなる場合は、ggml 型情報に dot 実装があるか、`STRATA_OWN_CPU_QUANT` が有効かによって Strata の行カーネルがなお選ばれる場合がある。したがってこの別変数が有効な環境では、`STRATA_TQ_ISA` の選択結果が使われるかはその分岐にも依存する（`engine/src/kernels/cpu/tq_cpu.cpp:177-185`、`engine/src/kernels/cpu/native_expert.cpp:38-48`）。
- CLI 引数、設定ファイル、別の ISA 指定による上書きは見つからなかった。`STRATA_TQ_ISA` は CPU feature 判定で選択できる最大 ISA を制限するだけである（`engine/src/kernels/cpu/tq_cpu.cpp:167-175`）。

## 実行時の詳細

最初に `tq_isa()` が呼ばれた時に `static const TqIsa` を初期化し、その中で `STRATA_TQ_ISA` を一度読む。選んだ値はプロセス内に保持されるため、その後の環境変更は反映されない（`engine/src/kernels/cpu/tq_cpu.cpp:48-55,167-175`）。コマンド行やリクエストごとの再評価はない。

native expert の gate/up では `tq_gu_rows()` に、down では `tq_rows()` に選択 ISA が渡る。通常の trellis レイアウトでは scalar / AVX2 / AVX-512 の対応行カーネルへ分岐する。Gyro-L の pair layout は AVX-512 選択時も pair 用 AVX2 実装を使い、scalar 指定時だけ scalar pair 実装を使う（`engine/src/kernels/cpu/native_expert.cpp:675-679,803-805`、`engine/src/kernels/cpu/tq_cpu.cpp:238-276`）。不正な ISA を直接渡す呼び出し側バグには `tq_rows` / `tq_gu_rows` が `std::abort()` するが、この環境変数の不正値は自動選択扱いなので、その経路にはならない（`engine/src/kernels/cpu/tq_cpu.cpp:266-281`）。

## ログと測定値

この変数の読み取り、未認識値、ISA 選択について Strata のログ出力はない。無効値も警告されず自動選択される。CPU が実行できない ISA は選択されず、環境変数に起因する終了・timeout の経路はない（`engine/src/kernels/cpu/tq_cpu.cpp:48-55,155-175`）。

`docs/GYRO.md:262-265` は `avx2` と `scalar` が命令セットを cap すると説明しているが、実装で `avx512` は上限 2 の自動選択と同じ扱いである。同資料の約 45% という記述は AVX2 上での trellis CPU カーネルと ggml-cpu の時間比較についての資料上の主張であり、この環境変数の効果を測定した値ではない。`docs/SETTINGS.md:344` の `on / off` 分類も値判定を示すものではなく、実装は真偽値を解釈しない。

## 根拠

- 読み取りと値判定、ISA 選択の cache、CPU feature guard: `engine/src/kernels/cpu/tq_cpu.cpp:48-55,155-175`
- ISA ごとの行カーネル分岐と不正な内部 ISA の abort: `engine/src/kernels/cpu/tq_cpu.cpp:238-281`
- native expert での trellis 型選別、gate/up・down 呼び出し: `engine/src/kernels/cpu/native_expert.cpp:38-48,363-385,675-679,803-805`
- CPU / Metal / SYCL のビルド対象: `engine/cmake/backends/cpu.cmake:303-317,343-346`、`engine/metal/CMakeLists.txt:145-146`、`engine/sycl/CMakeLists.txt:220-240`
- 関連資料と分類: `docs/GYRO.md:262-265`、`docs/SETTINGS.md:344`
