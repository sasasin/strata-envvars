# `STRATA_NO_IQ256`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数や内部動作は対象外。

## 役割

native expert を CPU で計算するとき、AVX2 版の i-quant gate/up 行カーネルを選ばないための開発・診断用スイッチです。値の内容は使わず、環境変数が存在するかどうかで判定します。無効化された経路は ggml-cpu の `vec_dot` にフォールバックします。

対象の AVX2 カーネルは `iq256_supported()` が列挙する型（型 ID 16、17、18、21、22、23）です。`native_gu_rows()` が処理する gate/up 行に限られ、`native_down_rows()` の AVX2 経路（IQ4_NL、`STRATA_KQ256` による Q5_1/Q8_0）はこの変数では無効化されません。

## 値と判定

| 状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | `getenv()` が `nullptr` | CPU が AVX2 対応なら、他の dispatch 条件に従い AVX2 カーネルを選べる |
| 設定済み | `getenv()` が非 `nullptr` | AVX2 i-quant gate/up カーネルを選ばない |

空文字、`0`、`1`、その他の文字列を区別せず、設定されていれば無効化します。数値変換や空白除去はありません。既定は未設定であり、別の設定ファイルや CLI 引数による優先順位はこのコードにはありません。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS=ON` でビルドされ、native expert の CPU 実装が含まれること。CMake のこのオプションは既定で `ON` です。
- native pack の expert を CPU で計算する経路に入ること。通常の canonical pack の AVX-512 expert 経路を切り替える変数ではありません。
- AVX2 カーネルが候補となるのは AVX2 対応 CPU です。AVX2 がなければ元からそのカーネルを呼ばず、ggml-cpu または別の older-CPU 経路を使います。
- AVX-512 対応 CPU では gate/up の dispatch は AVX-512 対応型に AVX-512 カーネルを優先します。IQ4_XS のように AVX-512 対応型一覧にない型も `cpu512` 条件により AVX2 側へ進まないため、この変数の AVX2 選択への影響はありません。`STRATA_NO_IQ512` を設定して AVX-512 カーネルを止めた場合も、ハードウェア判定 `cpu512` 自体は変わらないため、この分岐条件は同じです。
- `STRATA_IQ3S_MT1` が設定され、`STRATA_IQ_MT_MIN` が未設定の場合に限る IQ3_S の単一 token 用 multi-token 閾値引き下げも、この変数が設定されていると成立しません。`STRATA_IQ_MT_MIN` が明示されている場合はそちらの値が使われます。

## 実行時の詳細

`native_gu_rows()` 内の `static const bool avx2` が初期化される際に環境変数を読み、結果をプロセス内に保持します。対応形式で、CPU が AVX-512 ではなく、token 数が `native_gu_mt_min()` の閾値以上なら、変数未設定時は `iq256_gu_rows()` を呼びます。設定時はその分岐を通らず、各 gate/up 行と各 token について ggml-cpu の `vec_dot` を呼び、SwiGLU 値を計算します。値が設定されたことで AVX2 非対応 CPU から AVX2 命令を実行することはありません。AVX2 可否の CPU probe も必要条件です。

同じ値は `native_gu_mt_min()` の IQ3_S 特例の条件にも使われ、そこでは初回の呼び出し時に判定されます。カーネルの選択と閾値のキャッシュはそれぞれの `static` 初期化時点で固定され、その後の環境変更では再評価されません。

`strata generate` は native pack で AVX-512 非対応 CPU の場合、起動時に stderr へ CPU expert 経路を説明する行を出します。AVX2 対応でこの変数が設定されていると、文言は `ggml-cpu vec_dot (STRATA_NO_IQ256 set)` になります。SYCL 側にも同じ形式の起動ログがあります。このログは選択経路の表示で、処理結果の正確性や速度を測定したものではありません。

`docs/DETAILS.md` は `STRATA_IQ3S_MT1` と multi-token 閾値の関係を説明していますが、`STRATA_NO_IQ256` 自体の説明は見つかりませんでした。ここでは実装の dispatch 条件を根拠にしています。

## 根拠

- `CMakeLists.txt:1205-1210,1265-1269` — native expert の CMake オプション（既定 `ON`）と CPU 実装のビルド対象。
- `src/kernels/cpu/native_expert.cpp:41-43` — AVX2 IQ gate/up カーネルが対応する型 ID。
- `src/kernels/cpu/native_expert.cpp:115-131` — `STRATA_IQ_MT_MIN` の既定値と `STRATA_IQ3S_MT1` 特例、および `STRATA_NO_IQ256` による特例抑制。
- `src/kernels/cpu/native_expert.cpp:134-197` — AVX-512/AVX2 の dispatch、`STRATA_NO_IQ256` の設定有無判定と ggml-cpu への fallback。
- `src/kernels/cpu/native_expert.cpp:199-233` — down 行処理が別 dispatch であり、この変数を参照しないこと。
- `src/kernels/cpu/pool.cpp:630-662` — native expert の gate/up と down 行処理の呼び出し。
- `src/program/generate.cpp:2774-2783`, `sycl/src/program/generate.cpp:2572-2578` — CPU 条件と環境変数に応じた起動ログ。
- `docs/DETAILS.md:97-105` — 関連する `STRATA_IQ_MT_MIN` / `STRATA_IQ3S_MT1` の説明。
