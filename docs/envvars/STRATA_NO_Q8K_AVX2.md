# `STRATA_NO_Q8K_AVX2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native-expert 経路で、Q8_K activation の AVX2 量子化器を使わないようにするスイッチです。`native_quant_act()` が gate/up 入力を、`native_quant_h()` が down 入力を Q8_K に量子化するとき、AVX2 用関数を選ぶ条件からこの変数の存在を除外します。AVX2 が利用可能な CPU でこの変数が設定されると、AVX1 用関数の条件も満たさないため、`traits(...).from_float()` に処理を渡します。AVX2 が利用できない場合には別途 AVX1 用関数が選ばれる可能性があります（`engine/src/kernels/cpu/native_expert.cpp:415-428,514-537`）。ソースコメントは AVX2 量子化器が既存の量子化器と同じバイト列を書くとしています（同:416-419）。

この設定は CPU native-expert の Q8_K activation 量子化に限られます。native expert を使わない経路、Q8_K 以外の activation、または AVX2 dispatch が成立しない環境では AVX2 側の分岐を変えません。native experts は `STRATA_NATIVE_EXPERTS` が有効なビルドで追加され、x86 build では AVX2 kernel 群もビルド対象です（`engine/CMakeLists.txt:178,725-735`; `engine/cmake/backends/cpu.cmake:303-317,370-374`）。

## 値と判定

値の文字列や数値は変換せず、`std::getenv(...) == nullptr` かどうかだけを判定します。したがって未設定なら AVX2 用量子化器の候補になり、空文字を含む何らかの値が設定されていれば候補から外れます（`engine/src/kernels/cpu/native_expert.cpp:420-423`）。

| 条件 | unset | AVX2 用量子化器を抑止する値 | 判定上は抑止しない値 |
|---|---|---|---|
| すべての build / platform | 未設定なので、別条件を満たせば使用可能 | 空文字、`0`、`1`、`true`、`false`、その他すべての設定値 | なし（設定された値は内容にかかわらず抑止） |

数値としての妥当性、大文字小文字、空白、文字列全体は検査しません。`0` も「無効」にはならず、値が存在するため AVX2 量子化器を抑止します。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` を含む build で native-expert 処理を使うこと。通常の dense layer や native-expert を使わない実行には関与しません（`engine/CMakeLists.txt:178,725-735`）。
- 量子化対象の `gu_act` または `d_act` が Q8_K (`kTQ8_K`) であること。AVX2 用関数の返り値はさらに `type == kTQ8_K` を要求します（`engine/src/kernels/cpu/native_expert.cpp:420-428`）。
- `cpu_avx2_ok()` が true であること。この判定には AVX2 CPU feature に加え、FMA・OSXSAVE・AVX・F16C と OS の YMM 保存状態が必要です（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。`STRATA_FORCE_ISA` により ISA 上限が `avx` 以下なら false になります（同:26-39）。この変数が設定済みでも、AVX2 判定が false なら AVX2 量子化器はもともと選ばれません。AVX1 が利用可能で `STRATA_NO_Q8K_AVX1` が未設定なら、次の判定で AVX1 用量子化器が選択されます（`engine/src/kernels/cpu/native_expert.cpp:424-428`）。
- `STRATA_NO_Q8K_AVX2` が設定されていないこと。設定されていると上記の他条件が成立していても AVX2 用の分岐を通りません（`engine/src/kernels/cpu/native_expert.cpp:420-423`）。

Q8_K 以外で `native_quant_act()` / `native_quant_h()` に渡された場合はこのスイッチの影響を受けず、AVX2 helper の型判定が false となって通常の `from_float` 経路へ進みます（`engine/src/kernels/cpu/native_expert.cpp:522-524,535-537`）。

## 実行時の詳細

`q8k_avx2()` 内の `static const bool on` が、CPU の AVX2 可否と変数の未設定状態を初回呼び出し時に一度だけ評価・保存します。プロセス起動時ではなく最初の `q8k_avx2()` 呼び出し時の環境が使われ、その後プロセス内で環境を変更してもこの判定には反映されません（`engine/src/kernels/cpu/native_expert.cpp:420-423`）。CLI 引数による上書きや、この変数を子プロセスへ転送する処理は見つかりませんでした。

AVX2 が選ばれない場合、AVX1 の条件も偽なら Q8_K activation は `traits(f.gu_act).from_float(...)` または `traits(f.d_act).from_float(...)` に渡されます。`traits` は `STRATA_OWN_CPU_QUANT` build では Strata quant layer の関数、無効 build では ggml-cpu の型別関数を指します（`engine/src/kernels/cpu/native_expert.cpp:522-524,535-537`; `engine/include/strata/kernels/cpu/pool_quant.hpp:1-5,32-64,78-84`）。この文書ではそれらの実装側の挙動を Strata の挙動としては扱いません。

実際の呼び出し元には、CPU に割り当てられた native experts 向け activation の準備があります。`expert_source.cpp` は CPU expert がある場合に Q2_0 専用処理と native quantization を分け、native pack の Q2_0 以外で `native_quant_act()` を呼びます（`engine/src/core/expert_source.cpp:5747-5758`）。prefill の CPU expert 経路も Q2_0 以外で同関数を呼びます（`engine/src/prefill/prefill.cpp:6266-6298`）。down 入力の量子化は CPU pool が `native_quant_h()` を呼ぶ経路です（`engine/src/kernels/cpu/pool.cpp:1440,1593`）。Q2_0 専用 `act_quant_any()` の経路にはこのスイッチは適用されません。

AVX2 用の Q8_K 量子化器を選ぶかどうかだけを切り替えるコードで、Strata 内の明示的なログ、警告、終了、失敗処理はありません（`engine/src/kernels/cpu/native_expert.cpp:420-428,514-537`）。この AVX2 無効化によって AVX1 が新たに選ばれることはありません。AVX1 判定は `!cpu_avx2_ok()` を要求するためです（同:424-428）。

## ログと測定値

該当なし。対象の分岐はログやエラーを出しません。ソースコメントにはスカラー参照の host 量子化に関する所要時間の記載がありますが、対象機材・測定条件が示されていないため、測定値として本書には転記していません（`engine/src/kernels/cpu/native_expert.cpp:416-419`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:415-428` — Q8_K AVX2 / AVX1 量子化器の選択条件。
- `engine/src/kernels/cpu/native_expert.cpp:514-537` — gate/up と down activation の量子化と fallback。
- `engine/src/kernels/cpu/expert_layout.cpp:26-39,206-238` — `STRATA_FORCE_ISA` と AVX2 能力判定。
- `engine/src/core/expert_source.cpp:5747-5758`, `engine/src/prefill/prefill.cpp:6266-6298`, `engine/src/kernels/cpu/pool.cpp:1440,1593` — 実行経路から量子化関数への呼び出し。
- `engine/CMakeLists.txt:178,725-735`, `engine/cmake/backends/cpu.cmake:303-317,370-374` — native experts build の条件。
- `engine/include/strata/kernels/cpu/pool_quant.hpp:1-5,32-64,78-84` — build による `traits(...).from_float()` の実装選択。
