# `STRATA_IQ_PREFETCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

CPU の i-quant expert row カーネルが、重みブロックの読み取りに先立って発行するソフトウェアプリフェッチの先読み距離をバイト単位で指定します。AVX1、AVX2（AVX-VNNI を含む）、AVX-512 の各実装に同じ名前の設定があります。プリフェッチ命令には `_MM_HINT_T0` が指定されます。設定は算術結果や出力値を直接変更しません。

## 値と判定

各実装は `std::getenv()` の値を `std::atoi()` で整数に変換します。文字列全体の妥当性検査や範囲 clamp はありません。

| 設定 | 判定と動作 |
|---|---|
| unset | 既定値 `2048` バイトを使用 |
| `0`、負数、空文字、数値に変換できない文字列 | `atoi` の結果が 0 以下となり、プリフェッチを発行しない |
| 正の整数 | 現在の重みブロック先頭からそのバイト数先、およびさらに64バイト先をプリフェッチ |
| 数字の後ろに文字が続く値 | 数字部分の先頭を `atoi` が変換する（例: `512tail` は512）。先頭空白や符号も `atoi` の規則で処理される |

設定値は AVX1/AVX2 では関数内の `static const int` に保存され、最初のカーネル呼び出し時に読み取られます。AVX-512 では翻訳単位スコープの `const int` 初期化で読み取られます。いずれも読み取り後にプロセス環境を書き換えても再評価されません。

根拠: `src/kernels/cpu/iq_avx1.cpp:135-148`, `src/kernels/cpu/iq_avx2.cpp:177-195`, `src/kernels/cpu/iq_avx512.cpp:34-39`。

## 有効になる条件

この変数は CPU の Strata native expert カーネルにだけ作用します。要求値が正でも、対応カーネルが実行されない場合は効果がありません。

- AVX-512 カーネルは、CPU が AVX-512 対応で `STRATA_NO_IQ512` が未設定、対象形式が IQ2_XXS / IQ2_XS / IQ3_XXS / IQ3_S / IQ2_S のいずれかで、token 数 `nt` が `STRATA_IQ_MT_MIN` 由来の閾値以上の場合に使われます。
- AVX2 カーネルは、CPU が AVX2 対応で `STRATA_NO_IQ256` が未設定、対象形式に対応し、`nt` が同じ閾値以上の場合に使われます。AVX-512 対応 CPU では対応する AVX-512 カーネルが無効な場合の fallback となり、AVX-512 非対応 CPU では AVX2 が候補になります。閾値は `STRATA_IQ_MT_MIN` 未設定時は2です。
- AVX1 カーネルは、AVX2 非対応かつ AVX1 対応 CPU で `STRATA_NO_IQ128` が未設定、`nt` が閾値以上の場合に使われます。gate/up は IQ3_XXS / IQ3_S / IQ2_S、down は IQ4_NL / Q2_0 が対象です。
- 条件に合わない形式や無効化された経路は、該当する native SIMD カーネルを通らず ggml-cpu 側の dot 経路などへ進みます。その経路にこの設定のプリフェッチ処理はありません。

AVX-512 と AVX2/AVX1 の選択、および閾値・無効化条件は `src/kernels/cpu/native_expert.cpp:124-140,143-193` にあります。AVX-512 の対象形式は `src/kernels/cpu/native_expert.cpp:40-46`、AVX1 の対象形式は `src/kernels/cpu/iq_avx1.cpp:396-405` にあります。

## 実行時の詳細

各 row カーネルは量子化重みのブロックを順に処理し、現在のブロックをデコードする前に `blk + 距離` と `blk + 距離 + 64` をプリフェッチします。AVX1 の i-quant gate/up row と IQ4_NL / Q2_0 down row、AVX2 の i-quant row、AVX-512 の i-quant row で実行されます。値が 0 以下ならこの要求を省きます。engine のカーネル以外では `iq_avx2_parity` が環境変数の現在値（未設定時は `-`）を診断出力に表示しますが、この表示自体は値を解釈・変更しません。engine 側に追加ログ、エラー、終了条件はありません。

根拠: `src/kernels/cpu/iq_avx1.cpp:239-268,312-328,351-364`, `src/kernels/cpu/iq_avx2_rows.inl:31-49,98-104,249-256`, `src/kernels/cpu/iq_avx512.cpp:155-168`, `src/kernels/cpu/iq_avx2_parity.cpp:528-534`。

## 文書・測定値との照合

`docs/DETAILS.md` に `STRATA_IQ_PREFETCH` の記述は見つかりませんでした。AVX2 実装のコメントには Zen 3 5700X3D（AVX-512 なし）の IQ3_S decode で、2048バイト距離により gate/up phase が4%短縮、row throughput が1.0 GB/s増加、round 時間が1.3%短縮した測定とあります（`src/kernels/cpu/iq_avx2.cpp:177-182`）。これは実装コメントに書かれた当該条件の測定値であり、他の CPU やモデルでの効果を示すものではありません。AVX-512 側にも IQ3_S decode の gate/up 時間に関する2–3%の記載がありますが、コメントだけでは測定機材を特定できないため、一般化できる性能値としては扱いません（`src/kernels/cpu/iq_avx512.cpp:34-36`）。
