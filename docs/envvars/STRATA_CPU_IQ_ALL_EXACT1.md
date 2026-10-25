# `STRATA_CPU_IQ_ALL_EXACT1`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

CPU native expert の gate/up 行計算で、通常は ggml-cpu の `vec_dot` に渡す単一 token の i-quant 計算を、Strata の AVX2 実装へ切り替えます。実装は ggml-cpu の AVX2 単一 token 計算と同じ結果を狙った専用経路です。down 行や通常の GPU expert 計算を切り替える変数ではありません。

## 値と判定

環境変数は `native_gu_rows()` 内の関数ローカル `static const bool` 初期化時に読みます。設定文字列全体が厳密に `1` の場合だけ値判定を通過します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| `1` | 後述する CPU・形式・token 数の条件を満たす場合に有効 |
| 空文字、`0`、`01`、`10`、`true`、前後に空白のある値など | 無効 |

`atoi` や真偽値変換は行わず、`v[0] == '1' && v[1] == 0` で文字列全体を比較します。初回の `native_gu_rows()` 呼び出し後にプロセス内の環境を変更しても再評価されません。

## 有効になる条件

値が厳密に `1` でも、次の条件をすべて満たす gate/up 行呼び出しでだけ専用経路に入ります。

- `ggml_cpu_has_avx2()` が真で、`ggml_cpu_has_avx512()` が偽。ggml-cpu 自体が AVX2 用である必要があります。
- Strata 側で `cpu_avx2_ok()` が真で、`STRATA_NO_IQ256` が未設定。`STRATA_NO_IQ256` が設定されていると Strata の AVX2 i-quant 経路が選ばれません。
- 呼び出しの token 数 `nt` がちょうど `1` で、`nt < native_gu_mt_min(f.gu_type)`。
- gate/up 形式が IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S のいずれか（内部 type 値 `16, 17, 18, 21, 22`）。

`native_gu_mt_min()` は `STRATA_IQ_MT_MIN` が未設定なら `2` を返すため、通常はこの条件が満たされます。同変数を `1` にすると単一 token も multi-token kernel 側へ送られ、この分岐は使われません。`STRATA_IQ3S_MT1` の条件が成立して `STRATA_IQ_MT_MIN` 未設定時の IQ3_S 閾値を `1` にした場合も、IQ3_S ではこの分岐を通りません。

## 実行時の詳細

CPU expert pool の native gate/up 行処理は `native_gu_rows()` を呼びます。条件を満たした場合、対象行について `iq256_gu_rows_exact_one()` を実行して戻ります。それ以外は通常の dispatch が続き、単一 token かつ multi-token 閾値未満では ggml-cpu の `vec_dot` に到達します。

専用経路が実際に初めて使われると、プロセス中一度だけ stderr に `strata ab: GATE=STRATA_CPU_IQ_ALL_EXACT1 active=1` を出します。値を `1` にしても CPU 条件や呼び出し条件が合わなければこのログは出ません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:144-183` — 環境変数の厳密な文字列判定、CPU・形式・token 数の条件、専用 kernel の呼び出し、stderr ログ。
- `src/kernels/cpu/native_expert.cpp:125-142` — `STRATA_IQ_MT_MIN` と `STRATA_IQ3S_MT1` が multi-token の閾値に与える影響。
- `src/kernels/cpu/pool.cpp:708-742` — native expert pool の gate/up 行処理から `native_gu_rows()` への呼び出し。
- `include/strata/kernels/cpu/native_expert.hpp:49-54` — `native_gu_rows()` の単一 token / multi-token dispatch 契約。
- `docs/DETAILS.md:316-328` — 対応形式、測定結果と測定環境。資料は「同スイッチで 5 形式それぞれ 5,120 出力中差異 0」と記載し、複数 CPU/GPU 構成での測定値を示す一方、全体性能の向上が +3% に届かなかったため既定 OFF と説明しています。これらは資料に記載された結果であり、本調査で測定を再実施したものではありません。
