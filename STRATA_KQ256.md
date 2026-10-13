# `STRATA_KQ256`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

native GGUF pack の CPU expert 計算で、複数 token 分の dot product をまとめて処理する AVX2 カーネルを opt-in で使います。対象は gate/up の Q4_K 行と down の Q5_1 / Q8_0 行です。既定ではこのカーネルを選ばず、ggml-cpu の `vec_dot` を token ごとに呼びます。

これは CPU 側 expert-row の選択です。CUDA/HIP/SYCL の GPU カーネルを切り替える設定ではありません。native pack は `generate.cpp` で判定され、native の gate/up・down 行処理は CPU pool から呼ばれます。

## 値と判定

値は `std::atoi()` で整数に変換し、変換結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | `atoi` の結果が 0 なので無効 |
| `atoi` が 0 以外の整数を変換する文字列 | 有効。例: `1`, `2`, `-1`, `1abc`, `  +3tail` |
| 数字で始まらない、または数値部分が 0 | 無効。例: `true`, `abc1`, `0`, `0.5`, `-0` |

先頭の空白と符号は `atoi` の規則で処理され、数値の後ろにある文字は判定に使われません。範囲制限や無効値用 fallback はありません。整数型に収まらない入力について実装上の検査はありません。

gate/up と down は別々の関数内で `static const bool` を初回評価時に保存します。各関数が初めて呼ばれた後にプロセス内で環境を書き換えても、その関数の判定は再評価されません。二つの関数の初回呼び出し時期が異なれば、各々が別の時点の値をキャッシュします。

根拠: `src/kernels/cpu/native_expert.cpp:162,205`。

## 有効になる条件

- native pack の CPU expert-row 経路を通ること。通常の canonical pack の expert kernel 選択にはこの変数の読み取りがありません。
- 1回の処理に少なくとも2 token があること（`nt >= 2`）。1 token では ggml-cpu の通常 dot path が使われます。
- CPU が実装の `cpu_avx2_ok()` 判定を通ること。ここでは AVX2 命令だけでなく FMA、F16C、OSXSAVE、AVX 状態保存、およびビルドの ISA 上限も確認します。
- gate/up は `f.gu_type == 12`（この経路の Q4_K）のときだけ対象です。down は `f.d_type == 7` または `8`（Q5_1 / Q8_0）のときだけ対象です。他形式や UD-Q4_K_XL の Q5_K gate/up にはこの分岐は適用されません。

有効値でも、条件を満たさなければ通常の dot path に進みます。down 側は環境値の parse 自体に CPU 条件を含めませんが、カーネル呼び出し直前に `cpu_avx2_ok()` を確認します。したがって AVX2 非対応 CPU がこの環境値だけを理由に AVX2 コードを実行する経路にはなっていません。

## 実行時の詳細

native pack の gate/up 行は `native_gu_rows()`、down 行は `native_down_rows()` に渡されます。gate/up は Q4_K かつ2 token以上なら `kq256_gu_rows()` へ進み、そうでなければ後続の実装で各 token の ggml-cpu `vec_dot` を実行します。down は Q5_1 / Q8_0 かつ2 token以上なら `kq256_rows()` を選びます。

AVX2 カーネルは最大8 tokenずつに分け、重み側の unpack/decode を token ごとに繰り返さず、各 token の dot と出力を書きます。gate/up ではその後の SwiGLU も同じ関数内で計算します。通常 dot への fallback を含め、環境変数に関する専用ログや警告は実装にありません。

`docs/UNSLOTH_Q4.md` はこの設定を multi-token AVX2 kernels の opt-in と記し、ggml と bit-exact と説明しています。同じ表には「measured no faster」とありますが、この箇所に測定条件の詳細はないため、ここでは性能結果を評価・一般化しません。

## 根拠

- `src/program/generate.cpp:2714,2888-2893`: native pack の判定と native pack 起動条件。
- `src/kernels/cpu/pool.cpp:629-662`: native CPU pool から gate/up・down 行処理へ渡す箇所。
- `src/kernels/cpu/native_expert.cpp:45,134-165,199-211`: 対応 type、環境値の parse/cache、token 数・形式・CPU 条件、fallback。
- `src/kernels/cpu/expert_layout.cpp:106-136`: `cpu_avx2_ok()` が確認する CPU / OS / ISA 条件。
- `src/kernels/cpu/kq_avx2.cpp:28,237-260`: 最大8 token単位での multi-token 処理。
- `docs/UNSLOTH_Q4.md:228-234`: 文書上の opt-in 説明。
