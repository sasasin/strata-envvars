# `DS4_IQ_GATHER`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数は、DeepSeek-V4.1 の GGUF CPU expert lane にある独自 AVX2 IQ 行カーネルで、IQ3_XXS / IQ3_S のグリッド展開に `vpgatherdd` を使う形式を選ぶための開発・性能比較用フックとしてコードに現れます。ただし、現行ソースではその読み取りコードがコンパイル対象から外れているため、実行中の Strata に対する実効的な設定ではありません。

## 値と判定

`src/dsv41/ds4_iq_cpu.cpp` の `own()` 内では `std::getenv("DS4_IQ_GATHER")` を読み、未設定なら `force_gather=false`、設定時は `std::atoi(v) != 0` を `force_gather` に入れる記述があります。したがって、そのコードが有効な場合は `1`, `-1`, `2abc` など `atoi` の結果が 0 以外となる文字列が真になり、未設定、空文字、`0`, `abc` は偽になります。`atoi` は先頭の空白と符号付き10進数字列を読むため、数値の後ろにある文字は判定を変えません。

この判定は現行コードでは `#if defined(STRATA_NATIVE_EXPERTS)` の内側にありますが、同ファイル9行目で `STRATA_NATIVE_EXPERTS` を無条件に `#undef` してから分岐しているため、実際のビルドでは到達不能です。従って、現行実行ファイルでの値ごとの違いはありません。

## 有効になる条件

現行 HEAD の `src/dsv41/ds4_iq_cpu.cpp` では、ビルド設定に関係なく同ファイル内の `STRATA_NATIVE_EXPERTS` 定義を消してから条件分岐するため、`DS4_IQ_GATHER` の読み取り部分は有効になりません。CMake では `STRATA_NATIVE_EXPERTS` が既定 ON で、DS4.1 のターゲットにこのソースを含めますが（`CMakeLists.txt:128,810,837-845`）、そのビルド定義だけではファイル内の `#undef` を越えられません。

有効でないコード側の条件も、現行動作とは区別が必要です。仮に `own()` の実装がコンパイルされる構成なら、x86-64 で、CPU と OS が AVX2/FMA と YMM 状態を利用可能と判定され、さらに `DS4_IQ_OWN` が未設定または `atoi` が非0である場合に独自行カーネルが候補になります。`DS4_IQ_OWN` の `atoi` 結果が0なら独自カーネルを無効にします。`DS4_IQ_GATHER` は独立して独自カーネルを有効化しません。

## 実行時の詳細

現行コードの `#else` 側では `iq_cpu_own_rows()` は常に `false` を返し、IQ 低ビット型向けの `iq_cpu_fmt()` は CPU lane がない旨のエラーを返します。よって `DS4_IQ_GATHER` を設定しても CPU 行カーネルの形式選択、演算、ログに影響せず、この変数専用のログもありません（`src/dsv41/ds4_iq_cpu.cpp:758-780`）。呼び出し元の `ds4_model.cu` は IQ CPU lane の形式を通じて gate/up と down 処理を呼びますが、現行の無効化状態では独自 `own()` 分岐に到達しません（`src/dsv41/ds4_model.cu:5784-5808`）。

`#undef` より前のコメントと除外された実装では、このフックは `DS4_IQ_OWN` の `atoi` 結果が非0のときに IQ3 の gather 形式を強制候補にします。候補形式は `own_check()` で数値一致を確認し、失敗すれば gather 形式を採用しません。`DS4_IQ_OWN` が未設定の自動選択モードでは、native / blend / gather の各形式を計測して選択するため、`DS4_IQ_GATHER` の `force_gather` はそのモードの選択を強制しません。IQ2_XXS では同じフラグが別の one-table 形式に使われ、IQ2_S には対応する gather フラグがありません。この説明は除外コードの記述であり、現行バイナリの挙動を示すものではありません。

## 根拠

- `src/dsv41/ds4_iq_cpu.cpp:7-10`: `STRATA_NATIVE_EXPERTS` を無条件に undef した後、同マクロで実装を分岐する。
- `src/dsv41/ds4_iq_cpu.cpp:69-103,623-685`: 除外される x86 ISA 判定、`own()` 実装、`DS4_IQ_OWN` と `DS4_IQ_GATHER` の parse、検証・自動計測分岐。
- `src/dsv41/ds4_iq_cpu.cpp:758-780`: 現行の stub 実装。`iq_cpu_own_rows()` は `false`、IQ CPU lane の format は失敗する。
- `src/dsv41/ds4_model.cu:5784-5808`: IQ CPU lane の gate/up と down 呼び出し。
- `CMakeLists.txt:128,809-811,833-835,1665,1770`: `STRATA_NATIVE_EXPERTS` の既定値、DS4.1 ターゲットのソース構成とコンパイル定義。コンパイル定義はファイル内 `#undef` によりこの実装を有効化しない。

`docs/DETAILS.md` に `DS4_IQ_GATHER` の説明やこのフックに結び付く測定値は見つかりませんでした。したがって、性能上の効果や通常利用者向けの推奨値は記載していません。
