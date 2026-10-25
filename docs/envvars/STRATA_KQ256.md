# `STRATA_KQ256`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

CPU 上で native expert を計算するとき、Q4_K / Q5_1 / Q8_0 の複数 token 分の行内積をまとめて処理する AVX2 カーネルを選びます。対象形式の通常経路では ggml-cpu の `vec_dot` を token ごとに呼びますが、この設定が有効で AVX2 と複数 token の条件を満たすと Strata の `kq256` 行カーネルへ分岐します。GPU backend のカーネル選択を制御する変数ではありません。

## 値と判定

両方の読み取り箇所で `std::atoi(value) != 0` を使います。文字列全体の厳密な数値検証ではなく、`atoi` が先頭から読み取った整数が 0 かどうかで判定します。

| 設定値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字、`0`、`true`、数字で始まらない文字列 | 無効（`atoi` の結果が 0） |
| `1`、`2`、`-1`、`1tail`、` 1` | 有効（読み取られた整数が非 0） |

`atoi` は先頭の空白と符号を許し、整数の後ろに続く文字列を検査しません。したがって `1tail` は有効、`true` は無効です。数値変換エラーの個別処理や fallback 値はありません。未設定時の既定は無効です。

## 有効になる条件

- Strata の CPU native-expert pool 経路で gate/up（pool mode 5）または down（mode 6）行が実行されること（`src/kernels/cpu/pool.cpp:684-719`）。
- AVX2 が利用可能であること。gate/up 側は環境値の判定と一緒に `cpu_avx2_ok()` を確認します。down 側は分岐時に `cpu_avx2_ok()` を確認します。AVX2 が使えない場合は、この設定値が非 0 でも ggml-cpu の `vec_dot` 経路に進みます（`src/kernels/cpu/native_expert.cpp:171-174,218-229,239-245,270-278`）。
- 1回の行計算に2 token以上あること（`nt >= 2`）。1 token では ggml-cpu の `vec_dot` に残ります（同 `:172-174,243-245`）。
- gate/up は形式型 `12`（Q4_K）の場合に限ります。down は型 `7`（Q5_1）または `8`（Q8_0）の場合に限ります。ほかの量子化形式にはこの分岐を適用しません（同 `:48,172-174,243-245`）。

## 実行時の詳細

読み取りは gate/up と down の関数内に各1か所あり、それぞれ独立した関数ローカル `static const bool` にキャッシュされます。gate/up の値は `native_gu_rows()` が最初にこの初期化式を通った時点で、AVX2 判定とともに固定されます。down の値は `native_down_rows()` が最初に初期化式を通った時点で固定され、AVX2 判定自体は該当する各分岐で行われます。そのため、起動後に環境を変更しても、既に評価された側の判定は再読込されません。2関数の初回呼び出し時刻が異なる場合、各キャッシュの評価時点も異なります（`src/kernels/cpu/native_expert.cpp:171,239-245`）。

gate/up では Q4_K の各行について gate と up の dot を複数 token 分まとめ、SwiGLU の値を出力します。down では Q5_1 / Q8_0 の各行の dot をまとめます（`src/kernels/cpu/kq_avx2.cpp:237-260`）。CPU worker pool から対象関数が呼ばれます（`src/kernels/cpu/pool.cpp:705-719`）。この分岐自体に専用ログやエラー出力はありません。

## 文書との照合

`docs/UNSLOTH_Q4.md:235` は、Q4_K / Q5_1 / Q8_0 向けの multi-token AVX2 カーネルとして説明し、対象環境の engine 測定では速くならなかったため既定 OFF としています。`docs/QUANTS.md:37,40-41,126-128` には、3～4 token の expert group では Q4_K が改善した測定の記載もあります。測定条件が異なる記述があるため、速度差を一般化しません。実装の既定値は unset 時に無効です。

## 根拠

- `src/kernels/cpu/native_expert.cpp:48` — KQ カーネルが対応する型。
- `src/kernels/cpu/native_expert.cpp:168-174,218-229` — gate/up の設定読み取り、AVX2 と token 数、Q4_K 条件、無効時の dot 経路。
- `src/kernels/cpu/native_expert.cpp:233-278` — down 側の設定読み取り、Q5_1 / Q8_0 条件と fallback。
- `src/kernels/cpu/kq_avx2.cpp:237-260` — 複数 token の gate/up および down 行カーネル。
- `src/kernels/cpu/pool.cpp:684-719` — worker pool から native 行計算関数への呼び出し。
- `docs/UNSLOTH_Q4.md:235`, `docs/QUANTS.md:37,40-41,126-128` — 説明と測定記述。
