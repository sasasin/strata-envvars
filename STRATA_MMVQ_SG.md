# `STRATA_MMVQ_SG`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Intel SYCL backend の native MMVQ decode で、32-lane SIMD32 の代わりに 16-lane SIMD16 を使うカーネルを選ぶ実験用設定です。対象分岐は multi-column MMVQ と wide Q6_K MMVQ です。CUDA/HIP engine やサーバー設定を直接変えるものではありません。この候補名は主に SYCL ソースで見つかり、通常利用者向けの共通設定ではなく、SYCL kernel の選択用フックです。

## 値と判定

`mmvq_sg()` は `std::getenv()` の結果が null なら `32`、設定されていれば `std::atoi()` の結果を返します。`atoi` は文字列全体の厳密な数値検証をしません。空文字や先頭が数値でない文字列は `0` になり、先頭の空白・符号と、数値の後ろの非数値部分は `atoi` の変換規則に従います。変換エラーを別途報告したり値を clamp したりする処理はありません。

SIMD16 を選ぶ述語は次の通りです（`v` は上述の整数値）。

| `v` | `mmvq_sg16(iq4xs, n_out)` の結果 |
|---|---|
| `16` | 常に true。該当する呼び出し経路で SIMD16 を選ぶ |
| `1` | `iq4xs == true` のとき true（IQ4_XS 専用） |
| `2` | `n_out <= 1024` のとき true（短い出力行専用） |
| `3` | IQ4_XS または `n_out <= 1024` のとき true |
| その他 | 上の条件に一致しなければ false。通常は SIMD32 側へ進む |

式は `v == 16 || ((v & 1) && v < 4 && iq4xs) || ((v & 2) && v < 4 && n_out <= 1024)` です。したがって `1`、`2`、`3` 以外の小さな値にもビット判定は適用され、たとえば `0` は false です。未設定時の `32` も false となり SIMD16 を選びません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:164-171`。

## 有効になる条件

- この読み取りと選択処理は `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあります。対象の SYCL 実装をビルドして実行していることが前提です。
- multi-column 側では `ncols` が 2〜8 で `launch_multi_n()` に入り、さらに `g_multi_exact` が true の場合だけ SIMD16 判定まで進みます。`g_multi_exact` が false なら別の SIMD32 カーネルを選び、この変数の判定を通りません。
- `ncols == 1` の IQ4_XS 経路は `native_iq4_xs_mmvq()` の通常カーネルを直接起動するため、この `mmvq_sg16` 判定は通りません。
- Q6_K 側は `native_q6_k_mmvq()` が Q6 wide kernel を選んだ場合に限ります。`STRATA_MMVQ_WIDE` が無効、shape 条件（`ncols`、`n_in`、`n_out`）不一致、または wide kernel より前の別経路が成立する場合は、この設定による SIMD16 選択は行われません。さらに `launch_q6k_wide()` 内で `rpw == 1` であり、先行する `q6k_a2()` SIMD32 kernel の分岐に該当しない場合に `mmvq_sg16(false, n_out)` を評価します。
- SIMD16 用 kernel は `[[sycl::reqd_sub_group_size(16)]]` を指定して起動します。実行デバイス・コンパイラがこの SYCL kernel を実行できる条件はビルド構成に依存し、この調査ではビルドや GPU 実行による実機確認はしていません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2013-2046, 2104-2116, 3259-3273, 3426-3446, 1698-1736`。

## 実行時の詳細

`std::getenv("STRATA_MMVQ_SG")` は `mmvq_sg()` の関数内 static local `v` 初期化時に評価され、一度変換された整数がそのプロセス内で再利用されます。したがって最初の評価後にプロセス環境を書き換えても再評価されません。設定値はカーネルの subgroup 幅と、それに合わせた work-group の形状を切り替えます。同じ 128 work-item 数を保つ SIMD16 分岐では 8 subgroup を使います。コードにこの設定値に関するログ出力や警告はありません。

## 文書との照合と制限

`docs/INTEL.md` は `16` を全対象、`1` を IQ4_XS、`2` を短い出力（`n_out <= 1024`）と説明し、既定値を 32 としています。ソースの述語と一致します。同資料の測定記述では `mmvq_sg_bench` 単体で IQ4_XS は最大 1.45 倍、640-row shared-expert projection は最大 1.3 倍、large K-quant projection は 10〜25% 遅く、engine では SIMD32 を上回る設定は run-to-run noise を超えなかったとされています。これらは資料記載の測定結果であり、一般的な性能保証ではありません。資料内にこの値域・性能差の測定条件がすべて記載されているわけではないため、ここでは追加の測定値を推定しません。

参照: `docs/INTEL.md:441-445`。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:160-171` — SIMD16 の用途、既定値、値の判定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2013-2046` — multi-column の SIMD16 分岐と `g_multi_exact` 条件。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2104-2116, 3259-3273` — multi-column 呼び出し範囲と IQ4_XS の単列経路。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1698-1736, 3426-3446` — Q6_K wide kernel 選択と SIMD16 分岐。
- `docs/INTEL.md:441-445` — 設定値と記載された測定結果。
