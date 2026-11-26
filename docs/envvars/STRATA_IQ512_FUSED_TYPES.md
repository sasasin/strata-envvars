# `STRATA_IQ512_FUSED_TYPES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert 経路で、IQ 形式の gate/up 行を AVX-512 の fused kernel に渡す型 ID を選ぶ。既定は `18,21,22`（IQ3_XXS、IQ3_S、IQ2_S）で、値を指定すれば `16` と `17` も候補にできる。ただし型 ID を選ぶだけでは有効にならず、`STRATA_IQ512_FUSED_MAX`、CPU 機能、型ごとの実行時照合も通る必要がある。対象は CPU の gate/up 計算であり、down 行や GPU backend の設定ではない。`native_gu_rows_impl` が環境変数を読み、条件成立時に `iq512_fused_gu_rows` を呼ぶ（`engine/src/kernels/cpu/native_expert.cpp:629-652, 898-901`）。

## 値と判定

環境変数はカンマで区切った10進整数の型 ID 群として読み取られ、各要素を `std::atoi` に渡す。未設定または空文字なら文字列 `18,21,22` が使われる。`atoi` の結果が `1..31` の場合に限り、その ID のビットを選択マスクへ追加する。空要素、0、負数、32 以上、数値に変換できない要素は追加されない。重複 ID は同じビットになる。

`atoi` は文字列全体の厳密な検証ではないため、先頭の空白や符号を許し、数値の後ろの文字列を無視する。たとえば `" 18,+21x"` は 18 と 21 を選び、`"18x,0,-1,32,word"` は 18 だけを選ぶ。大文字小文字の判定はなく、名前ではなく数値 ID を指定する。最終的に使えるのは `iq512f_supported` が列挙する 16、17、18、21、22 のみ（`engine/src/kernels/cpu/native_expert.cpp:635-648`; `engine/src/kernels/cpu/iq_avx512.cpp:759-769`）。

| 条件 | unset | 選択マスクに入る値 | 選択マスクに入らない値 |
|---|---|---|---|
| fused 分岐に到達したとき | `18,21,22` | 各カンマ要素の `atoi` 結果が `1..31`。実際に fused kernel が対応する ID は `16,17,18,21,22` | 空要素、`0`、負数、`32` 以上、数値変換できない要素 |
| 空文字 | `18,21,22` と同じ | 既定の 18、21、22 | — |

## 有効になる条件

- `native_gu_rows` / `native_gu_rows_invariant` を通る CPU native expert の gate/up 計算であること。通常の pool は gate/up 行の処理から `native_gu_rows` を呼ぶ（`engine/src/kernels/cpu/pool.cpp:1290-1296, 1423-1429`）。
- `STRATA_IQ512_FUSED_MAX` が `atoi` で 2 以上になり、トークン数 `nt` が `2..STRATA_IQ512_FUSED_MAX` に入ること。同変数は未設定時 0 で fused 分岐を無効にする。空文字は 0（`engine/src/kernels/cpu/native_expert.cpp:629-634`）。
- `cpu_vnni_ok()` が真で、`STRATA_NO_IQ512` が未設定であること。ここでいう未設定判定は値の内容ではなく `getenv(...) == nullptr` であり、`STRATA_NO_IQ512` が空文字でも AVX-512 経路を止める（`engine/src/kernels/cpu/native_expert.cpp:568`）。
- gate/up 型 ID が選択マスクに含まれ、`iq512f_supported` が要求する VPOPCNT 機能と型 ID（16、17、18、21、22）を満たすこと（`engine/src/kernels/cpu/native_expert.cpp:649`; `engine/src/kernels/cpu/iq_avx512.cpp:653-669, 759`）。
- `f.tail_off == 0` であること。また `iq512f_ok` がその型の fused 計算をこのビルドの dot と照合して一致と判定すること（`engine/src/kernels/cpu/native_expert.cpp:634, 649`; 照合処理と失敗時ログは `engine/src/kernels/cpu/native_expert.cpp:161-201`）。

どれかを満たさない場合、この設定による fused kernel 呼び出しは行われず、同関数の後続 CPU kernel / 通常 dot の dispatch に進む（`engine/src/kernels/cpu/native_expert.cpp:649-706, 710-735`）。

## 実行時の詳細

型リストは `native_gu_rows_impl` 内の関数ローカル `static const unsigned` で一度だけ解析される。初期化は、`STRATA_IQ512_FUSED_MAX` と CPU・トークン数・tail 条件を満たして fused 分岐に初めて入った時点まで遅延する。`fused_max` も関数ローカル static で、同関数がその宣言箇所に初めて到達した時に一度だけ `getenv` / `atoi` される。そのためプロセス起動後に環境を変更しても、すでに初期化済みの値は更新されない。`fused_max` が 2 未満のまま初期化された場合、型リストの static は初期化されない（`engine/src/kernels/cpu/native_expert.cpp:633-648`）。

選択された型かつ照合成功時は、gate と up の行を `iq512_fused_gu_rows` に渡して処理し、戻る。これは各トークンについて gate の sigmoid を up に掛けた gate/up 出力を作る経路である（`engine/src/kernels/cpu/native_expert.cpp:649-652`; `engine/src/kernels/cpu/iq_avx512.cpp:761-769`）。型リストはモデルの量子化形式を変えず、指定型の gate/up 計算がこの kernel を使えるかだけを絞る。

## ログと測定値

この環境変数を設定したことや型を選択したことを知らせるログはない。型ごとの実行時照合が失敗した場合は、stderr に `strata: the fused 512-bit gate/up rows of type %d differ from this ggml-cpu's dot: not used` を出し、その型では fused kernel を使わない（`engine/src/kernels/cpu/native_expert.cpp:197-201`）。

実装コメントは fused 行が既定の行より Zen 4 で 2〜3 tokens 時に 1.27〜1.34 倍、1 token 時には遅く、そのため 1 token は ggml の dot を使うと記している。これはコードコメントに記載された測定であり、機種の詳細、モデル、量子化、反復回数などの条件は同コメントにはない（`engine/src/kernels/cpu/native_expert.cpp:629-634`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:629-652` — 最大トークン数の条件、環境変数の既定値と解析、型マスク、実行条件と fused 呼び出し。
- `engine/src/kernels/cpu/native_expert.cpp:161-201` — fused kernel の型別照合と失敗ログ。
- `engine/src/kernels/cpu/native_expert.cpp:568, 898-910` — AVX-512 の環境条件と native gate/up dispatch の入口。
- `engine/src/kernels/cpu/iq_avx512.cpp:653-669, 759-769` — VPOPCNT 判定、サポート型、型別 fused kernel dispatch。
- `engine/src/kernels/cpu/pool.cpp:1290-1296, 1423-1429` — native expert pool から gate/up dispatch を呼ぶ箇所。
