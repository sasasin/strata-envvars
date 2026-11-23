# `STRATA_TQP_AVX2_FAST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU の TQP（Gyro-L の pair-trellis、型 147–149）で、既定の AVX2 カーネル `rows_tqp_t` の代わりに `rows_tqp_fast_t` を選ぶ開発・比較用の切替です。fast 側は各状態を求める際にストリーム末尾へ先頭 4 byte を足したバッファを使い、状態ごとの 32-bit 読み取りにします。いずれも AVX2 の pair-trellis 計算で、CUDA/HIP のカーネルや CLI 設定を切り替える変数ではありません。実装と分岐は `engine/src/kernels/cpu/tq_avx2.cpp:147-193,197-207` にあります。

ソースコメントは fast 形式の出力 bytes が既定形式と同じと述べていますが、この調査では実行・測定して照合していません。同コメントは Ryzen 5 5600X / GCC の paired A/B で PR の性能向上を再現できなかったとも記しますが、詳細な測定条件や数値は示していません（`engine/src/kernels/cpu/tq_avx2.cpp:144-146,189`）。

## 値と判定

`tqp_fast_on()` は `std::getenv` の戻り値が null でないことに加えて、`v[0] == '1'` かを判定します。文字列全体の比較や数値変換はしません（`engine/src/kernels/cpu/tq_avx2.cpp:190-193`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| AVX2 TQP カーネルが呼ばれる場合 | 無効 | `1`, `10`, `1anything`（先頭 byte が ASCII `1`） | 空文字、`0`, `01`, `true`, ` 1` |
| AVX2 TQP カーネルが呼ばれない場合 | 読み取りなし | 該当なし | 値にかかわらずこの変数は効果を持たない |

`TRUE` など大文字表記も先頭 byte が `1` でないため無効です。先頭が `1` なら後続文字の妥当性は検査しません。未設定・空文字・その他の先頭文字では既定の `rows_tqp_t` が選ばれます（`engine/src/kernels/cpu/tq_avx2.cpp:190-207`）。

## 有効になる条件

- Strata が x86-64 CPU カーネルを含むビルドであり、実行時に Strata の native CPU trellis rows が使われること。x86-64 ビルドは `tq_avx2.cpp` を含み、非 x86 ビルドは `tq_cpu.cpp` の scalar 実装だけを含みます（`engine/cmake/backends/cpu.cmake:303-313,339-342`）。
- 対象 row が TQP5/TQP6/TQP7（GGML 型 147–149）であること。Strata はこれらを pair-layout として `tq_rows` / `tq_gu_rows` から pair kernel に渡します（`engine/src/kernels/cpu/tq_cpu.cpp:249-262,266-276,293-300`）。
- `tq_isa()` が `scalar` 以外を選ぶこと。既定では CPU が対応する AVX-512、次いで AVX2 を選び、`STRATA_TQ_ISA=scalar` は scalar に制限します。AVX-512 が選ばれていても pair-layout は AVX2 pair kernel に渡されます（`engine/src/kernels/cpu/tq_cpu.cpp:48-55,155-175,249-261`）。AVX2 の実行可否は CPU feature と OS の YMM state を確認して決まります（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。
- `STRATA_NO_TQ_KERNELS` が `atoi` で非 0 と判定されても、リンクされた ggml に対象型の dot 実装がないため Strata 独自 rows が必要な場合は対象経路に残り得ます。独自 rows を避けられ、かつ ggml が型を実装する場合はその dot に進み、この変数を読む AVX2 関数には入りません（`engine/src/kernels/cpu/tq_cpu.cpp:177-185`; `engine/src/kernels/cpu/native_expert.cpp:37-46`）。
- CPU 専用の選択です。GPU 側の TQP 実装は別の CUDA ソースにあり、この変数への参照はありません（CPU 側の読み取り箇所: `engine/src/kernels/cpu/tq_avx2.cpp:190-191`）。

サーバーモードや CLI 引数による直接の上書きは、この変数の読み取り・分岐箇所にはありません。`STRATA_TQ_ISA` が scalar を選ぶ場合は、この値が有効でも AVX2 TQP 関数が呼ばれず、効果はありません（`engine/src/kernels/cpu/tq_cpu.cpp:48-55,167-175,249-261`）。

## 実行時の詳細

値はプロセス起動時ではなく、`tq_rows_avx2_tqp()` の最初の呼び出し時に `tqp_fast_on()` が評価します。関数内の `static const bool` に保存されるため、そのプロセスで後から環境を変更しても再評価されません。AVX2 TQP 経路が一度も呼ばれなければ、この変数は読み取られません（`engine/src/kernels/cpu/tq_avx2.cpp:190-205`）。

有効判定時は TQP の bit 幅 `kb` が 5 または 6 なら対応する `rows_tqp_fast_t<5/6>`、それ以外なら `<7>` を呼び出し、無効判定時は同じ分岐で `rows_tqp_t` を呼びます。fast 側は各 128-value block の状態列と state table の先頭 pair を使って AVX2 整数積和を行い、scale を適用して `out` の row 値を書きます。読み取り関数にも選択分岐にも、この環境変数専用のログ・警告・エラー処理はありません（`engine/src/kernels/cpu/tq_avx2.cpp:97-142,147-187,190-207`）。

## ログと測定値

この環境変数の設定値や有効化理由を出力するログは、Strata の読み取り・分岐箇所にありません。上記の性能コメント以外に、この変数を条件とした数値測定は `docs/DETAILS.md` に見当たりません。性能向上は保証されず、記載済みコメントにも Ryzen 5 5600X / GCC の paired A/B で PR の向上を再現しなかったとあります（`engine/src/kernels/cpu/tq_avx2.cpp:189-193`）。

## 根拠

- `engine/src/kernels/cpu/tq_avx2.cpp:147-187,190-207` — fast / 通常実装、値判定、cache、呼び出し分岐。
- `engine/src/kernels/cpu/tq_cpu.cpp:48-55,155-175,249-276,279-305` — ISA 選択、CPU pair-layout の dispatch、native rows の呼び出し。
- `engine/src/kernels/cpu/expert_layout.cpp:206-238` — AVX2 実行可否。
- `engine/src/kernels/cpu/native_expert.cpp:37-46,674-678,802-804` — 独自 TQ rows と ggml dot の選択、gate/up・down rows からの呼び出し。
- `engine/cmake/backends/cpu.cmake:303-313,339-342` — x86 と非 x86 のソース構成・AVX2 translation unit の compile options。
- `docs/GYRO.md:42-45` — Gyro-L の型・CPU/GPU 経路の説明。対象変数固有の挙動は記載なし。
