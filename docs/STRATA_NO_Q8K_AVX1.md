# `STRATA_NO_Q8K_AVX1`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

native expert CPU 経路が Q8_K 形式の activation を量子化するとき、AVX2 を利用できない AVX CPU 上で使う AVX1 量子化器を無効にするスイッチです。設定すると、Strata 独自の AVX1 実装を使わず、ggml-cpu の `from_float` 関数へフォールバックします。AVX2 対応 CPU の AVX2 量子化器はこの変数では無効になりません。

この経路は `STRATA_NATIVE_EXPERTS` を有効にしてビルドした Strata の native expert 処理に属します。CMake はこの場合に `native_expert.cpp` と AVX1 実装を CPU カーネルライブラリへ追加します。非 native expert ビルドにはこの判定はありません。

## 値と判定

| 状態 | AVX1 Q8_K 量子化器 |
|---|---|
| 未設定 | CPU 条件を満たせば有効 |
| 空文字を含め、何らかの値を設定 | 無効 |

値の内容は parse されません。`getenv(...) == nullptr` かどうかだけを見ているため、`0`、`false`、`1` のいずれも設定されていれば無効化します。

## 有効になる条件

AVX1 量子化器を選ぶには、すべての条件が必要です。

- AVX2 が利用可能でない。
- `cpu_avx1_ok()` が true（CPU と OS が AVX/YMM state を利用可能）である。
- `STRATA_NO_Q8K_AVX1` が未設定。
- 対象 NativeFmt の activation type が `GGML_TYPE_Q8_K`。

AVX2 対応 CPU では AVX2 実装が先に選択候補となり、AVX1 側の CPU 条件は成立しません。この変数は AVX2 実装を抑止しません。また、activation type が Q8_K でない場合も AVX1 量子化器は選ばれません。

## 実行時の詳細

`native_quant_act()` は gate/up activation を、`native_quant_h()` は down activation を変換します。両関数は AVX2 Q8_K 経路を先に確認し、その経路に該当しなければ AVX1 経路を確認します。AVX1 経路が無効、または activation type が Q8_K でなければ `traits(...)->from_float(...)` にフォールバックします。この環境変数に起因するログ出力やエラー処理はありません。

AVX1 条件は関数内の `static const bool` に保存されます。`q8k_avx1()` の初回呼び出し時に環境と CPU 条件を評価し、以降のプロセス実行中に環境を変更しても反映されません。この helper は両方の activation 変換関数から呼ばれます。

## 根拠

- `CMakeLists.txt:1270-1271,1317-1322,1355-1361`: native expert のビルド条件とソース登録。
- `src/kernels/cpu/native_expert.cpp:95-121`: AVX2/AVX1 選択条件、環境変数判定、両 activation 変換関数のフォールバック。
- `src/kernels/cpu/expert_layout.cpp:145-170`: AVX1 CPU 条件が AVX と OS の YMM state を確認。
- `src/kernels/cpu/iq_avx1.cpp:448-453`: AVX1 Q8_K 実装の説明と関数定義。AVX2 Q8_K quantizer と同じ byte を生成する実装と記載。
- `src/core/expert_source.cpp:3890-3900`, `src/prefill/prefill.cpp:3415-3432`: decode と prefill で CPU が処理する native expert 用 activation 変換を呼ぶ経路。
- `docs/DETAILS.md`, `docs/UNSLOTH_Q4.md`, `docs/QUANTS.md`: この変数の個別設定説明は見つかりませんでした。値の判定と挙動は上記ソースを根拠としています。
