# `STRATA_NO_Q8K_AVX1`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの内部動作は対象外。

## 役割

CPU の native expert 経路で、AVX1 専用 Q8_K 活性量子化器を使わず、ggml-cpu の `from_float` 関数へ戻すための抑止用フックです。AVX2 が使えず AVX1 が使える CPU に限って判定されます。AVX2 対応 CPU の Q8_K 量子化器は別の `STRATA_NO_Q8K_AVX2` で制御されます。

native expert は、CPU 上で GGUF 形式の expert を処理するビルド機能です。CMake の `STRATA_NATIVE_EXPERTS` は既定で ON です。対象機能がビルドに含まれない構成では、この環境変数による実用上の効果はありません。

## 値と判定

値の内容は parse せず、`std::getenv(...) == nullptr` かどうかだけを見ます。

| 状態 | AVX1 Q8_K 専用量子化器 |
|---|---|
| 未設定 | CPU 条件を満たせば使用する（既定） |
| 空文字を含む任意の値を設定 | 使用しない。ggml-cpu の `from_float` にフォールバック |

したがって `STRATA_NO_Q8K_AVX1=0` も抑止になります。`1` との文字列比較や真偽値変換はありません。判定結果は `q8k_avx1()` 内の `static const bool` に保持され、最初の呼び出し後に環境を書き換えても再評価されません。根拠: `src/kernels/cpu/native_expert.cpp:95-100`。

## 有効になる条件

- `native_expert.cpp` を含む native expert ビルドであること（`CMakeLists.txt:1210,1218,1265-1269`）。
- 実行 CPU で `cpu_avx2_ok()` が false、かつ `cpu_avx1_ok()` が true であること。
- 対象の量子化活性型が `GGML_TYPE_Q8_K` であること。
- `STRATA_NO_Q8K_AVX1` が未設定であること。

CPU 判定は実行時に行われます。AVX1 判定は AVX と OSXSAVE、OS が YMM 状態を保存することを確認し、AVX2 判定はさらに FMA、F16C、OS の AVX 状態保存および CPUID の AVX2 ビットを確認します（`src/kernels/cpu/expert_layout.cpp:106-160`）。AVX2 のない AVX1 CPU 以外ではこの変数は量子化器の選択を変えません。

## 実行時の詳細

`native_quant_act()` は gate/up 用活性を、`native_quant_h()` は down 用活性を量子化します。どちらもまず AVX2 Q8_K 量子化器、次にこの環境変数で制御される AVX1 Q8_K 量子化器を確認し、どちらも選ばれなければ `traits(...)->from_float(...)` を呼びます（`src/kernels/cpu/native_expert.cpp:103-112`）。AVX1 量子化器が選ばれるのは対象活性形式が Q8_K のときだけです。

この経路は prompt prefill の CPU native expert 処理でも使われます。CPU に割り当てた expert が必要とする token の活性に `native_quant_act()` を呼び、その後 CPU expert pool に仕事を渡します（`src/prefill/prefill.cpp:3300-3333`）。API の戻り値、ログ出力、エラー動作をこの環境変数が変える処理は見当たりません。

AVX1 実装は ggml の Q8_K 参照量子化と同じ算術を使うことをコードコメントで説明しており、専用の parity ツールもあります。ただしこれは実装資料上の説明であり、この調査ではテストや測定を実行していません（`src/kernels/cpu/iq_avx1.cpp:448-453`; `src/kernels/cpu/q8k_quant_parity.cpp:1-7,96-120`）。

## 根拠

- 環境変数の読み取りと CPU/型条件: `src/kernels/cpu/native_expert.cpp:95-112`。
- AVX1/AVX2 実行時能力判定: `src/kernels/cpu/expert_layout.cpp:106-163`。
- CPU native expert 機能のビルド条件とソース登録: `CMakeLists.txt:1210-1218,1265-1269`。
- 呼び出し元の prompt prefill 経路: `src/prefill/prefill.cpp:3300-3333`。
- `docs/DETAILS.md` には CPU expert pool の説明がありますが、この変数固有の値判定や効果についての説明は確認できませんでした。
