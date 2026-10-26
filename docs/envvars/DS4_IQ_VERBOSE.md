# `DS4_IQ_VERBOSE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この HEAD でビルドされる Strata のコードでは、`DS4_IQ_VERBOSE` は実行時の挙動を変えません。名前の唯一の参照は `src/dsv41/ds4_iq_cpu.cpp` 内の `#if defined(STRATA_NATIVE_EXPERTS)` ブロックにありますが、同ファイルがその直前に `#undef STRATA_NATIVE_EXPERTS` を実行するため、そのブロック全体がコンパイル対象から外れます。

無効化されたブロック内の記述は、IQ CPU 行カーネルの選択測定結果を stderr に表示する意図です。これは現在の実行ファイルで利用できる診断設定ではありません。

## 値と判定

実行時の値判定はありません。変数の未設定、空文字、`0`、その他の文字列のいずれも、この HEAD でコンパイルされるコードの動作に影響しません。

無効化されたブロックのテキスト上では、`std::getenv("DS4_IQ_VERBOSE") != nullptr` という設定有無だけの判定です。仮にそのコードがコンパイルされた場合は、値の内容を parse せず、空文字を含む設定済みの値でログを出す条件になります。ただし、これはこの HEAD の実行時挙動ではありません。

## 有効になる条件

このファイルでは `STRATA_NATIVE_EXPERTS` を明示的に `#undef` してから条件付きコンパイルを行っています。そのため、CMake の `STRATA_NATIVE_EXPERTS` オプションが ON でも、同ファイル内の `#if defined(STRATA_NATIVE_EXPERTS)` ブロックは有効になりません。x86 CPU、DeepSeek-V4.1 の実行、IQ 量子化形式などの条件を満たしても、`DS4_IQ_VERBOSE` の読み取りには到達しません。

## 実行時の詳細

コンパイル対象外のコードでは、IQ3_XXS / IQ3_S / IQ2_XXS / IQ2_S 向けの独自 CPU 行実装について、ネイティブ実装との正確性確認後に候補を測定し、その選択結果を stderr に出す構造です。ログ文字列は `ds4: CPU lane %s rows: native ... -> ...` です。判定箇所は `own()` の `std::call_once` 内にあり、出力は初回の型別選択処理に伴うものです（`src/dsv41/ds4_iq_cpu.cpp:627-685`）。

しかし、同ファイルの `#undef` によりこの実装はコンパイルされず、同ファイルの有効な `#else` 側は IQ CPU 関数を別の実装へ委譲し、`iq_cpu_own_rows()` は `false` を返します。したがって `DS4_IQ_VERBOSE` によるログも、実装選択への影響もありません（`src/dsv41/ds4_iq_cpu.cpp:7-18,758-780`）。DeepSeek-V4.1 のモデル側は IQ CPU 関数を呼び出しますが、そのことによって無効化された分岐が復活することはありません（`src/dsv41/ds4_model.cu:5726-5738,5784-5808`）。

## 根拠

- `src/dsv41/ds4_iq_cpu.cpp:7-18` — `STRATA_NATIVE_EXPERTS` を undef し、その後に条件付きブロックを開始。
- `src/dsv41/ds4_iq_cpu.cpp:680-684` — `DS4_IQ_VERBOSE` の唯一の参照と、設定有無に応じた stderr 出力（コンパイル対象外）。
- `src/dsv41/ds4_iq_cpu.cpp:758-780` — コンパイル対象になる `#else` 側の委譲実装と `iq_cpu_own_rows()` の `false` 戻り値。
- `src/dsv41/ds4_model.cu:5726-5738,5784-5808` — IQ CPU 処理の呼び出し元。
- リポジトリ内の `src`、`include`、`sycl`、`serve`、`tools`、`setup.py`、`docs/DETAILS.md` を検索した結果、この環境変数名の他の読み取りや説明は確認できませんでした。
