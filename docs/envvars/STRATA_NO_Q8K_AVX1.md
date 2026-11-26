# `STRATA_NO_Q8K_AVX1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native expert の Q8_K 活性量子化で使う AVX1 実装を選ばないためのスイッチ。未設定なら AVX2 が使えず AVX1 が利用可能な環境で `q8k_quant_avx1` を使う候補になり、設定されていれば `traits(...).from_float` に進む。gate/up 入力と down 入力の両方が対象だが、変数は量子化器の選択だけを変え、expert の行計算や routing は直接変更しない（`engine/src/kernels/cpu/native_expert.cpp:416-428,514-537`）。

## 値と判定

値の内容は parse せず、`std::getenv(...) == nullptr` かどうかだけを見る。未設定なら AVX1 を候補にし、空文字を含む何らかの設定があれば AVX1 を無効にする。`0`、`1`、`true`、`false`、大文字小文字、空白、その他の文字列に違いはない（`engine/src/kernels/cpu/native_expert.cpp:426-428`）。

| 条件（build / CPU） | unset | AVX1 を選ぶ候補になる値 | AVX1 を選ばない値 |
|---|---|---|---|
| `STRATA_NATIVE_EXPERTS` を有効にした x86 build、AVX2 使用不可かつ AVX1 使用可 | AVX1 候補 | なし（値ではなく unset が条件） | 空文字、`0`、`1`、`true`、`false`、任意の設定値 |
| AVX2 使用可、AVX1 使用不可、または非 x86 | AVX1 は選ばれない | なし | 設定値にかかわらず AVX1 は選ばれない |

ここで「候補」は入力 activation format が Q8_K（`kTQ8_K`）である場合に限る。Q8_K 以外では `q8k_avx1` が false になる（`engine/src/kernels/cpu/native_expert.cpp:426-428`）。CPU 判定は AVX2 について CPU と OS の AVX/FMA/F16C 条件、AVX2 feature、ISA 上限を確認し、AVX1 について AVX と OSXSAVE、および OS が YMM 状態を保存することを確認する。非 x86 の feature probe は false を返す（`engine/src/kernels/cpu/expert_layout.cpp:42-50,206-238,241-267`）。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` が有効で、CPU native expert 実装を含む build であること。既定は ON で、ON のとき `native_expert.cpp` が CPU kernel library に追加される。x86 では AVX1 実装 `iq_avx1.cpp` も追加される（`engine/CMakeLists.txt:178,725-736`; `engine/cmake/backends/cpu.cmake:303-317,370`）。
- native expert の活性量子化が呼ばれ、その format が Q8_K であること。`native_quant_act` は gate/up 活性、`native_quant_h` は down 活性を量子化し、CPU pool はその後 native expert の行計算へ渡す（`engine/src/kernels/cpu/native_expert.cpp:514-537`; `engine/src/kernels/cpu/pool.cpp:1274-1310`）。
- AVX2 使用不可かつ AVX1 使用可であること。`STRATA_FORCE_ISA=avx` は CPU probe の上限を AVX にし、AVX2 probe を false にするため、AVX1 条件を満たす CPU では AVX1 側の選択を可能にする（`engine/src/kernels/cpu/expert_layout.cpp:26-39,206-208,241-245`）。
- AVX2 CPU で `STRATA_NO_Q8K_AVX2` を設定しても、この変数によって AVX1 へ降格はしない。AVX1 側も `!cpu_avx2_ok()` を要求するため、AVX2 経路を使わない場合は `traits(...).from_float` に進む（`engine/src/kernels/cpu/native_expert.cpp:420-428,522-524,535-537`）。

## 実行時の詳細

`q8k_avx1` 内の `static const bool on` が初めて評価される時に、CPU 判定と環境変数の設定有無を読み取り、その後はプロセス内でキャッシュする。したがって、その評価後にプロセス環境を変更しても判定は変わらない。CPU の AVX2 が使用可能なら AVX1 側の条件式は短絡し、対象変数は読み取られない。`native_quant_act` と `native_quant_h` は AVX2 量子化器を先に試し、次に AVX1、どちらも選ばれない場合に format trait の `from_float` を呼ぶ（`engine/src/kernels/cpu/native_expert.cpp:420-428,514-537`）。

この補助関数は CPU expert pool 以外にも共有される。たとえば CUDA の Qwen 3.5 経路は native expert entry の活性を `native_quant_act` で準備するが、この設定が変えるのはホスト側量子化の選択であり、CUDA kernel の選択ではない（`engine/src/qwen35/q36_engine.cu:3325-3348`）。CLI 引数や設定ファイルによる上書き、子プロセスへの転送を行うコードは、この名前の参照範囲では確認できない。

## ログと測定値

この変数固有のログ、警告、エラー、終了経路はない。Strata の資料にこのスイッチの条件付き測定値は確認できないため、性能差は記載しない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:416-428` — AVX2 / AVX1 Q8_K 判定と対象変数の読み取り。
- `engine/src/kernels/cpu/native_expert.cpp:514-537` — gate/up と down 活性の量子化器選択。
- `engine/src/kernels/cpu/expert_layout.cpp:26-39,42-50,206-238,241-267` — ISA 上限と CPU / OS feature probe。
- `engine/CMakeLists.txt:178,725-736`; `engine/cmake/backends/cpu.cmake:303-317,370` — native expert 実装と AVX1 ソースの build 条件。
- `engine/src/kernels/cpu/pool.cpp:1274-1310`; `engine/src/qwen35/q36_engine.cu:3325-3348` — native quantizer の呼び出し経路。
