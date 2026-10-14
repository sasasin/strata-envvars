# `STRATA_NO_Q8K_AVX2`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。作業ツリーは `main` で `origin/main` と一致し、変更はありませんでした。

## 役割

ネイティブ CPU expert の活性を Q8_K に量子化するとき、Strata の AVX2 実装 `q8k_quant_avx2()` を使わず、ggml-cpu の型 trait に登録された `from_float` 実装へフォールバックさせます。設定名どおり AVX2 版 Q8_K 量子化器だけを抑止します。IQ/K の expert 行ドット計算や、他の量子化器全体を無効にはしません。

この分岐はネイティブ expert の CPU 経路に限られます。通常の expert source では、CPU が担当する token の入力活性を量子化する際に `native_quant_act()` が呼ばれます。prefill の CPU expert 経路でも同じ関数が使われます。Q2 native-kernel 経路は独自の `act_quant_any()` を使うため、この変数の対象外です。

## 値と判定

| 環境変数 | AVX2 Q8_K 量子化器の選択 |
|---|---|
| 未設定 | CPU が AVX2 を実行可能なら選択可能 |
| 設定あり（空文字を含む） | 選択しない |

値は読み取られず、文字列比較や数値変換もありません。`=0`、`=1`、`=false` のいずれも、環境変数が存在するだけで抑止します。選択判定は `q8k_avx2()` 内の `static const bool` に一度だけ保存されるため、最初の判定後にプロセス環境を変更しても反映されません。

## 有効になる条件

この設定が AVX2 実装の選択に影響するのは、ビルドにネイティブ expert 実装が含まれ、CPU が `cpu_avx2_ok()` を満たし、対象の活性型が `GGML_TYPE_Q8_K` の場合です。`cpu_avx2_ok()` は CPU 機能と OS の AVX 状態保存を確認し、結果を static cache します。

Q8_K 以外の活性型には `q8k_avx2()` は一致しません。AVX2 非対応 CPU ではこの AVX2 分岐は初めから不成立です。AVX2 対応 CPU で本変数を設定すると、AVX1 版には切り替わらず ggml-cpu の `from_float` が使われます。AVX1 版は別の条件（AVX2 非対応かつ AVX1 対応）と `STRATA_NO_Q8K_AVX1` で独立に選ばれます。

## 実行時の詳細

`native_quant_act()` は gate/up 側の活性型 `f.gu_act` が Q8_K で AVX2 量子化器が許可されていれば `q8k_quant_avx2(x, ..., f.n_embd)` を呼びます。`native_quant_h()` も down 側の `f.d_act` が Q8_K の場合に同様の選択を行い、長さ `f.n_ff` を量子化します。どちらの AVX2 条件にも合わない場合は `traits(type)->from_float(...)` を呼びます。

decode の expert source では、CPU に expert 処理があるときに対象 token の活性を量子化し、その後 CPU pool に native expert job を渡します。prefill も CPU が担当する expert 用に `native_quant_act()` を呼びます。変数の値に応じた専用ログ、警告、エラー出力は実装にありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:96-121` — 環境変数の設定有無、AVX2/AVX1 の量子化器選択、型 trait への fallback。
- `src/kernels/cpu/iq_avx2.cpp:387-400` — AVX2 Q8_K 量子化器の実装。コメントでは ggml の参照処理と同じ演算・出力 byte になる設計を説明しています。
- `src/kernels/cpu/expert_layout.cpp:110-143` — AVX2 実行可否の CPUID、OSXSAVE、XCR0 判定と結果の static cache。
- `src/core/expert_source.cpp:3887-3901,3942-3970` — decode で CPU expert がある場合の活性量子化と native CPU pool への dispatch。
- `src/prefill/prefill.cpp:3415-3432` — prefill の CPU expert 活性量子化。
- `CMakeLists.txt:1270-1271,1317-1322,1360-1361` — `STRATA_NATIVE_EXPERTS` 有効時に native expert と AVX2 ソースを CPU kernels target に含める設定。
