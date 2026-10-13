# `STRATA_NO_Q8K_AVX2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。Strata 所有ソースを対象とし、外部ライブラリ内部の挙動は対象外。

## 役割

native expert 経路で使う Q8_K 活性値量子化について、Strata 内蔵の AVX2 版を使わず、ggml-cpu の `from_float` 量子化器へ切り替えるための抑止スイッチです。CPU native expert の gate/up 入力と down 入力の両方に影響します。通常の非 native expert 経路や、Q8_K 以外の活性値型を選んだ経路を切り替える変数ではありません。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_NO_Q8K_AVX2") == nullptr` かどうかだけを見ます。

| 環境の状態 | AVX2 Q8_K 量子化器 |
|---|---|
| 未設定 | CPU の AVX2 実行条件を満たせば使用可能 |
| 設定あり（空文字を含む） | 使用しない |

したがって `STRATA_NO_Q8K_AVX2=0` も AVX2 版を無効にします。`1` だけを有効・無効値として扱う判定、数値変換、空白除去、大文字小文字比較はありません。値による警告やログ出力もありません。

## 有効になる条件

- `native_expert.cpp` の実装が使われるビルドであること。`STRATA_NATIVE_EXPERTS` がないビルドでは `expert_layout.cpp` が native expert 読み込みを拒否し、native quant 関数も到達不能の abort stub です。
- native expert 経路が選ばれ、対象活性値の型が `GGML_TYPE_Q8_K` であること。
- `cpu_avx2_ok()` が true であること。同関数は ISA cap、CPUID の AVX/FMA/F16C/AVX2 feature bits、および OS が有効な AVX 状態を保存するかを確認します。

Q8_K でない場合や AVX2 条件を満たさない場合、この変数で AVX2 版が新たに選択されることはありません。AVX2 非対応CPUで AVX1 版量子化器を使うかどうかは別変数 `STRATA_NO_Q8K_AVX1` が制御します。AVX2 対応CPUで本変数を設定した場合は AVX1 へ切り替わらず、ggml-cpu の `from_float` にフォールバックします。

## 実行時の詳細

`q8k_avx2()` 内の `static const bool on` が、`cpu_avx2_ok()` と環境変数の有無を一度評価して保持します。評価はプロセス起動時ではなく、この関数への初回到達時です。その後の環境変更は反映されません。`q8k_avx2()` は各 native Q8_K 量子化の判定経路から呼ばれます。

`native_quant_act()` は `f.gu_act` が Q8_K なら入力 `x` の `n_embd` 要素を量子化し、`native_quant_h()` は `f.d_act` が Q8_K なら `h` の `n_ff` 要素を量子化します。AVX2 版を使わない場合、どちらも `traits(type)->from_float(...)` を呼びます。gate/up 活性値は native expert decode/prompt の CPU 側計算に渡され、down 活性値は CPU expert pool の down-row 計算に渡されます。Strata のソースコメントは AVX2 版が ggml-cpu の参照実装と同じバイト列を書くとしており、切り替え先はその ggml-cpu 参照量子化です。

プロンプト経路では Q2_0 native pack の場合に別の `ActQ` 経路が選ばれ、本変数の対象外です。CUDA/SYCL などGPU backend のホスト側で CPU expert を計算する処理も `native_quant_act` を呼ぶ場合はこの判定を通ります。GPU の量子化 kernel 自体を切り替える変数ではありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:87-100`: Q8_K AVX2/AVX1 各判定、環境変数の存在判定、AVX2設定条件。
- `src/kernels/cpu/native_expert.cpp:103-112`: gate/up と down の量子化、AVX2/AVX1/ggml の選択。
- `src/kernels/cpu/expert_layout.cpp:106-137`: AVX2 の CPU/OS 実行可否判定。
- `src/kernels/cpu/pool.cpp:629-663,761-781`: native expert の行計算と down 活性値量子化の呼び出し。
- `src/prefill/prefill.cpp:3300-3317`: CUDA prefill の CPU expert 用 gate/up 活性値量子化。
- `sycl/src/core/expert_source.cpp:2715-2725`: SYCL native expert 経路の CPU 活性値量子化。
- `src/kernels/cpu/expert_layout.cpp:368-376`: native expert 無効ビルドの stub。
- `docs/DETAILS.md:215-223`: native pack の GGUF expert 読み込み経路の説明。本変数や AVX2 量子化切替に関する利用者向け説明は確認できませんでした。
