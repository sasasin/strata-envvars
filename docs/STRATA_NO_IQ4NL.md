# `STRATA_NO_IQ4NL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU expert pool が IQ4_NL 形式の expert down 行を計算するときに使う、AVX2 マルチトークンカーネルを無効にします。無効にすると ggml-cpu の `vec_dot` にフォールバックします。IQ4_NL 自体や他形式のカーネルを無効にするスイッチではありません。

この分岐は Strata の native expert レイアウトを使う経路にあります。Verifier は各レイヤーの native format を渡して grouped expert 計算を行い、CPU pool の down-row phase は Q2_0 専用経路でない場合に `native_down_rows()` を呼びます。ビルドでは `native_expert.cpp` と AVX2 カーネルを CPU kernel library に含めています。

## 値と判定

`std::getenv("STRATA_NO_IQ4NL") == nullptr` の判定です。値の parse や文字列比較はしません。

| 環境状態 | IQ4_NL AVX2 マルチトークン経路 |
|---|---|
| 未設定 | 有効候補（CPU とトークン数の条件も必要） |
| 空文字を含む何らかの値を設定 | 無効 |

`0`、`1`、`false` など、設定時の値はすべて同じ扱いです。環境変数の値を変更しても、`native_down_rows()` 内の `static const bool` 初期化後はそのプロセスでは再評価されません。

## 有効になる条件

変数が未設定でも、AVX2 マルチトークンカーネルが選ばれるには次の条件を満たす必要があります。

- CPU の実行時機能確認で AVX2 が利用可能。
- down weight format が `20`（IQ4_NL）。Q2_0 down は CPU pool の別の `q2_rows_any()` 経路に入ります。
- その expert group のトークン数 `nt` が `STRATA_IQ_MT_MIN` 以上。`STRATA_IQ_MT_MIN` は未設定時 `2`、設定時は `atoi` の結果です。したがって `STRATA_NO_IQ4NL` を設定しても、この閾値や他形式の経路は変更しません。

条件を満たさない場合、AVX2 がない CPU では AVX1 が利用可能かつ `STRATA_NO_IQ128` 未設定なら IQ4_NL を含む AVX1 対応 down kernel が選ばれます。それ以外は ggml-cpu の `vec_dot` をトークンごとに呼びます。特に AVX2 がある CPU で本変数を設定した場合、IQ4_NL はこの ggml-cpu 経路にフォールバックします。

この設定は GPU kernel には作用しません。検証した Strata ソースには本変数によるログ出力やエラー処理はありません。

## 実行時の詳細

native CPU down-row phase で `native_down_rows()` が呼ばれた際に設定有無を初期化し、その後の処理で IQ4_NL の `nt >= mt_min` 判定と合わせて使用します。AVX2 カーネルが選ばれる場合、`iq4nl256_down_rows()` に weight rows、量子化済み activation、出力先と row 範囲を渡します。無効の場合は ggml-cpu の型 trait から `vec_dot` を取得し、各 row・各 token について一回ずつ計算します。

ソースコメントによると、AVX2 マルチトークンカーネルはブロックごとの nibble decode と重み絶対値化を複数 token で共有し、ggml-cpu の dot は single-token です。これは実装の説明であり、この調査では性能差を測定していません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:199-230` — 環境変数判定、IQ4_NL/AVX2/トークン数による分岐、AVX1 と ggml-cpu への fallback。
- `src/kernels/cpu/pool.cpp:653-662` — down format ごとの Q2_0 特別経路と `native_down_rows()` 呼び出し。
- `src/core/verify.cpp:1577-1583` — native format を用いる grouped expert 計算の呼び出し。
- `CMakeLists.txt:1265-1285` — CPU library への native expert / AVX2 ソース登録と AVX2 コンパイル設定。
- `docs/DETAILS.md:215-223` — native pack が `experts.bin` を持たない場合に、GGUF ファイルから各 expert の gate/up/down rows を読む説明。
