# `DS4_IQ_OWN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数は、DeepSeek-V4.1 (DS4) の CPU lane で一部の低ビット IQ expert の行計算に Strata 独自の実装を使うかどうかを選ぶ目的でソースに現れます。ただし、調査対象 revision ではその実装を含むプリプロセッサ分岐が無効です。実行されるスタブは環境変数を参照せず `false` を返すため、現在の Strata 実行ファイルで `DS4_IQ_OWN` を設定しても挙動は変わりません。

## 値と判定

現行ビルドでは値を読む処理がコンパイル対象にならず、未設定・空文字・数値・無効な文字列のいずれにも Strata 上の効果はありません。

無効な分岐内には将来の実装として `std::getenv("DS4_IQ_OWN")` と `std::atoi` による判定があります。そこでは未設定が `-1`（CPU ごとに実測して選択）、`atoi` の結果が 0 なら無効、0 以外なら常時選択の mode になります。したがって、そのコードが有効な別 revision では空文字や数字で始まらない文字列は 0、`-1` や `1suffix` は非 0 と判定されます。この判定は現在の revision の実行時動作ではありません。

## 有効になる条件

現在のソースでは有効化できません。`src/dsv41/ds4_iq_cpu.cpp` は `STRATA_NATIVE_EXPERTS` を明示的に `#undef` してから、その macro の有無で実装を分けています。そのためビルド時に同 macro を定義しても、このファイル内では `#if defined(STRATA_NATIVE_EXPERTS)` が成立せず、環境変数を読む側の実装は除外されます。

## 実行時の詳細

コンパイルされる側の `iq_cpu_own_rows(int)` は常に `false` を返します。`iq_cpu_gate_up` と `iq_cpu_down` のスタブ経路は、それぞれ GG/TQ CPU lane の処理へ委譲します。DS4 独自の AVX2/AVX-512 IQ 行計算や、`DS4_IQ_OWN` の読み取り・ログ出力はこの経路で行われません。プロセス起動後の値変更、子プロセスへの転送、リクエスト単位の評価についても、この変数に関する実装はありません。

## 根拠

- `src/dsv41/ds4_iq_cpu.cpp:7-18`: `STRATA_NATIVE_EXPERTS` を `#undef` した後に、その macro で本体とスタブを切り替える。
- `src/dsv41/ds4_iq_cpu.cpp:627-650`: 無効な本体側の mode 判定。`DS4_IQ_OWN` は `atoi` の 0/非 0 と未設定を区別するが、この領域は上記の条件分岐で除外される。
- `src/dsv41/ds4_iq_cpu.cpp:716-779`: `#else` 側は GG/TQ lane に委譲し、`iq_cpu_own_rows` のスタブは `false` を返す。
- `src/dsv41/ds4_gguf_cpu.hpp:92-94`: ヘッダーコメントも、独自行計算の選択 API を宣言している。現行の実装上の有効性は `.cpp` の macro 条件に従う。

`docs/DETAILS.md` には `DS4_IQ_OWN` の利用説明は見つかりませんでした。ここでは性能や数値同一性を現行実行時の確認結果として扱っていません。
