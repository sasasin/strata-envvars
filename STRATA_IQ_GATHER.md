# `STRATA_IQ_GATHER`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

AVX-512 CPU 用の IQ expert gate/up カーネルで、IQ3_XXS と IQ3_S のコードブック値を scalar lookup で組み立てる代わりに AVX-512 gather 命令で読みます。IQ3_XXS は 8-bit の grid index、IQ3_S は `qh` 由来の上位 bit を加えた 9-bit index を使います。実装コメントは gather と scalar lookup が同じ grid 値・結果になるとしています。この変数は処理方式を選び、値の数値や文字列内容で処理を変えません。

## 値と判定

`src/kernels/cpu/iq_avx512.cpp` の名前空間スコープにある `const bool gather` が `std::getenv("STRATA_IQ_GATHER") != nullptr` で初期化されます。文字列比較や数値変換はありません。

| 環境変数の状態 | `gather` | 動作 |
|---|---:|---|
| unset | `false` | scalar lookup |
| 設定あり（空文字を含む） | `true` | AVX-512 gather |

したがって `STRATA_IQ_GATHER=0`、`false`、`1` はいずれも gather を選びます。大文字小文字、空白、文字列全体の妥当性は検査されません。初期化時に一度値が保存されるため、初期化後の環境変更はこの判定に反映されません。

## 有効になる条件

変数が設定されていても、実際の gather 命令に到達するには、Strata の native CPU expert 経路が使われ、CPU が AVX-512 kernel を実行でき、gate/up の型が IQ3_XXS（ggml type 18）または IQ3_S（type 21）で、token 数が `STRATA_IQ_MT_MIN` から得た閾値以上である必要があります。`STRATA_IQ_MT_MIN` 未設定時の閾値は 2 です。AVX-512 kernel は CPU 機能判定を通った場合に限って dispatch されます。

`STRATA_NO_IQ512` が設定されて AVX-512 kernel が選ばれない場合、AVX2 kernel または ggml-cpu の経路になります。AVX2 kernel の gather 判定に使うのは別変数 `STRATA_IQ256_GATHER` であり、`STRATA_IQ_GATHER` はその経路を制御しません。IQ2_XXS、IQ2_XS、IQ2_S の decode にもこの変数の分岐はありません。

## 実行時の詳細

Strata の CPU pool が native expert の gate/up 行を計算すると `native_gu_rows()` に入り、対応型・token 数・CPU 機能と `STRATA_NO_IQ512` の状態に応じて `iq512_gu_rows()` を呼びます。IQ3_XXS では `Fmt<18>::decode()`、IQ3_S では `Fmt<21>::decode()` が `gather` を参照し、設定時は `_mm512_i32gather_epi32` で grid を読みます。未設定時は同じ index から scalar で grid を読んで vector を組み立てます。他の IQ format はこの bool を参照しません。

この選択について専用のログ、警告、エラー出力は実装にありません。カーネルのコメントは Ryzen 5 7600（Zen 4）で gather が scalar lookup より 3–5% 遅かったとして opt-in にしています。この記述はソースコメントにある測定メモで、条件や測定手順を含む `docs/DETAILS.md` の性能説明は確認できませんでした。結果を他 CPU に一般化できる根拠はありません。

## 根拠

- `src/kernels/cpu/iq_avx512.cpp:31-39` — gather と prefetch の環境変数判定、初期値。
- `src/kernels/cpu/iq_avx512.cpp:108-118,130-147` — IQ3_XXS / IQ3_S の gather と scalar lookup。
- `src/kernels/cpu/iq_avx512.cpp:245-255` — AVX-512 gate/up 関数が対応する型。
- `src/kernels/cpu/native_expert.cpp:37-43,134-180` — 対応型、CPU/設定/token 数による native kernel の dispatch。
- `src/kernels/cpu/pool.cpp:629-652` — CPU pool の gate/up 行から `native_gu_rows()` を呼ぶ箇所。
- `CMakeLists.txt:1265-1285` — AVX-512 kernel の CPU kernel library への組み込みと ISA compile option。
- `docs/DETAILS.md` — `STRATA_IQ_GATHER` の直接説明はありません。`bench/results/2026-10-09-community-rtx-5080-w7-2475x-ud-iq4xs-786k/README.md:48-65` には値 `1` を含む実行設定がありますが、同ファイルは `STRATA_IQ_*` をまとめて CPU pool switches として記すだけで、この変数単体の効果は切り分けていません。
