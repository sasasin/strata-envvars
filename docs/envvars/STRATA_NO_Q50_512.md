# `STRATA_NO_Q50_512`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CPU の native expert 経路で、Q5_0 down projection に使う 512-bit Q5_0 カーネルを無効にします。設定すると Strata はそのカーネルを選ばず、各 token の行をリンク済み ggml-cpu の `vec_dot` で計算します。値が `1` かどうかは判定せず、環境変数の有無だけを判定します。

## 値と判定

| 環境の状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | `getenv()` が null | 512-bit カーネルを選択可能 |
| 空文字を設定 | `getenv()` が non-null | カーネルを無効化 |
| 任意の非空文字列（`0`, `1`, `false` など） | `getenv()` が non-null | カーネルを無効化 |

文字列変換、数値判定、大小文字判定、clamp はありません。無効値という別の扱いもなく、設定されていれば常に無効化です。C++ の `&&` の短絡評価により、`cpu_vnni_ok()` が false の場合は対象変数の `getenv()` 自体が呼ばれません。変数自体に CLI 引数や設定ファイルとの優先順位はありません。

## 有効になる条件

未設定の場合でも、次の条件がそろったときだけ 512-bit カーネルが実行されます。

- Strata の native expert CPU 経路が使われ、down projection の型が Q5_0（ggml type `6`）である。
- CPU probe が VNNI 対応を返す。x86 では CPU の機能に加え OS が AVX-512 状態を保存できることなどを確認します。VBMI のない VNNI 世代では `STRATA_VNNI_TIER` の opt-in も条件になります。
- `STRATA_Q50_512_MIN` で決まる token 数以上である（既定値 2）。
- native expert に scale tail がない。
- 初回の合成データ照合で、このビルドの ggml-cpu `vec_dot` と 512-bit カーネルの出力 bit 列が一致する。

条件に合わない場合は同じ関数内の ggml-cpu `vec_dot` ループに進みます。Q5_0 が down projection でない場合や native expert CPU 関数に到達しない経路には、この設定は作用しません。

## 実行時の詳細

読み取りは `native_down_rows_impl` 内の `static const bool` 初期化で行われ、各テンプレート実体の最初の呼び出し時に一度だけ評価されます。その実体では以後の環境変更は再評価されません。CPU probe が false の場合はその値を false としてキャッシュし、対象変数は読みません。`STRATA_Q50_512_MIN` も同関数内の別の `static const int` で初回評価され、未設定なら `2`、設定時は `std::atoi` の結果です。

選択時は down projection の各行について、複数 token の結果を `q50_512_down_rows` が計算します。選択されない場合は各行・各 token ごとに ggml-cpu の `vec_dot` を呼びます。512-bit カーネルは合成ブロックで `vec_dot` と一致するか初回に検査され、不一致なら stderr に `strata: the 512-bit Q5_0 down rows differ from this ggml-cpu's dot: not used` と出して ggml-cpu 経路を使います。終了や例外にはせず、環境変数を設定したこと自体によるログもありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:655-661` — 環境変数の存在判定、CPU・型・token 数・tail・照合の条件、および専用カーネルへの分岐。
- `src/kernels/cpu/native_expert.cpp:196-231` — Q5_0 512-bit 結果を Q8_0 活性とリンク済み ggml-cpu の `vec_dot` に照合し、不一致を stderr に出す処理。
- `src/kernels/cpu/native_expert.cpp:694-701` — 専用カーネルを使わない場合の ggml-cpu dot fallback。
- `src/kernels/cpu/pool.cpp:1238-1250` — CPU expert pool が対象 down projection を `native_down_rows` または window-invariant 版へ渡す箇所。
- `src/kernels/cpu/expert_layout.cpp:188-203` — VNNI probe と、VBMI を備えない CPU で `STRATA_VNNI_TIER` を要求する条件。
- `CMakeLists.txt:2059-2066,2182-2194` — x86 と portable の CPU kernel 構成。非 x86 構成では `native_expert.cpp` と併せて portable kernel を使い、`cpu_vnni_ok()` は常に false（`src/kernels/cpu/expert_layout.cpp:40-52`）。

`docs/DETAILS.md` にこの環境変数または当該 dispatch の説明・測定値は見当たりません。性能差や出力同一性はここでは測定していません。
