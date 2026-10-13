# `STRATA_NO_IQ512`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。調査開始時の作業ツリーは `main` で、`bench/results/2026-10-12-community-ai-pro-r9700-qwen3-8-flash-next-iq2-xs/` が未追跡だった。

## 役割

CPU native expert の gate/up 行計算で、AVX-512 IQ kernel を選ばないようにするための開発・実行時切替です。変数が設定されていると、AVX-512 対応 CPU でも AVX-512 kernel を選択せず、条件が合えば AVX2 kernel、そうでなければ ggml-cpu の `vec_dot` に進みます。down 行計算はこの変数を参照しません。

この経路は native expert 対応ビルドで使われます。モデルの native expert を CPU pool で計算し、複数 token の gate/up 行を処理するときに `native_gu_rows()` へ到達します。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_NO_IQ512") != nullptr` かどうかだけを判定します。

| 環境の状態 | AVX-512 kernel の選択 |
|---|---|
| 未設定 | CPU が AVX-512 対応なら選択候補になる |
| 空文字を含む何らかの値を設定 | 選択しない |

したがって `0` も `false` も抑止として扱われます。判定結果は `native_gu_rows()` 内の `static const bool` に初回呼び出し時に保存されます。以降にプロセス環境を変更しても再評価されません。

## 有効になる条件

- CPU native expert 機能を含むビルドであること。CMake の `STRATA_NATIVE_EXPERTS` が有効な場合、AVX-512/AVX2 実装を含む CPU kernel 群が `strata_kernels_cpu` に追加されます。無効ビルドでは native pack の読み込み経路が拒否され、この関数の abort stub は到達しない設計です。
- CPU が AVX-512 対応であること。非対応 CPU では `cpu_avx512_ok()` が false となり、この変数を設定しても選択は変わりません。
- `native_gu_rows()` が扱う型であること。`iq512_supported()` は type ID `16, 17, 18, 21, 22` のみを AVX-512 kernel 対象とします。
- AVX-512 を抑止した後に AVX2 kernel を使うには、CPU が AVX2 対応で、型が `iq256_supported()` の対象であり、token 数が `native_gu_mt_min()` の閾値以上である必要があります。AVX2 kernel 自体も `STRATA_NO_IQ256` の設定で無効化できます。
- AVX2 に進めない場合、または対象型・token 数が条件を満たさない場合は ggml-cpu の `vec_dot` を token ごとに呼びます。AVX-512 対応 CPU 上では、IQ4_XS のように AVX2 kernel だけが実装されている型は、従来どおりこの経路に留まります。

## 実行時の詳細

Prefill の CPU-share 経路は、CPU で処理する expert の入力を量子化し、expert pool に複数 token の job を渡します。pool の native gate/up phase（mode 5）は `native_gu_rows()` を呼び出します。そこで AVX-512 が有効なら対象型を `iq512_gu_rows()` で処理します。`STRATA_NO_IQ512` が設定されている場合はその分岐を飛ばし、次の AVX2 条件を調べてから ggml-cpu の dot へ fallback します。

この変数によるログ出力やエラー処理はありません。環境変数自体は計算値に渡されず、kernel 選択だけを変えます。実行時の精度や速度への影響はこの調査では測定していません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:37-43`: AVX-512/AVX2 kernel の型判定。
- `src/kernels/cpu/native_expert.cpp:134-149`: gate/up kernel の AVX-512 判定、環境変数読み取り、AVX2 の別条件。
- `src/kernels/cpu/native_expert.cpp:167-195`: AVX-512 → AVX2 → ggml-cpu `vec_dot` の順の分岐と fallback。
- `src/kernels/cpu/pool.cpp:629-652,761-773`: native pool phase から `native_gu_rows()` への呼び出し。
- `src/prefill/prefill.cpp:3278-3324`: prefill CPU-share 経路で CPU expert jobs を準備する処理。
- `CMakeLists.txt:1210-1218,1265-1270,1304-1305`: native expert 機能と CPU kernel 群のビルド条件。
- `src/kernels/cpu/expert_layout.cpp:368-376`: native expert 無効ビルド時の stub と到達前提。
