# `STRATA_Q50_512_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native expert の down 行が Q5_0（ggml type 6）のとき、AVX-512 Q5_0 行カーネルへ切り替える最小 token 数を指定します。閾値以上なら重みを複数 token で共有して計算し、条件を満たさない場合は後続の通常 dot 経路を使います。gate/up 行、GPU 側の計算、他の down 量子化型には適用されません。設定値は `native_down_rows_impl` で読み、`native_down_rows` / `native_down_rows_invariant` の両経路から使われます（`engine/src/kernels/cpu/native_expert.cpp:792-825,903-915`）。

## 値と判定

`std::getenv` が null なら閾値は `2`、null でなければ `std::atoi` の結果です。空文字や数値として始まらない文字列は 0 になります。`atoi` は先頭の空白と符号を含む数値 prefix を変換し、数値の後ろの文字列を検査しません。したがって `2junk` は 2、`0anything` は 0、`-1` は -1 です。文字列全体の妥当性検査、clamp、無効値時の fallback はありません（`engine/src/kernels/cpu/native_expert.cpp:820-824`）。

| 条件 | unset | 設定時に Q5_0 カーネルの閾値を満たす値 | 閾値を満たさない例 |
|---|---:|---|---|
| Q5_0 CPU down 行で他の有効条件も満たす場合 | 2 token | `atoi` 結果 `N` に対して `nt >= N`。例: `2`, `2junk` は 2 token 以上、`0`, 空文字, `abc`, `-1` は通常の正の token 数すべて | `3` は 2 token では不成立。負数・0 は無効値として拒否されず、比較上は成立しやすくなる |

`nt` が閾値以上であっても、下記の CPU 機能・抑止変数・Q5_0 型・tail 条件・初回照合を通らなければこの閾値による切り替えは起きません。`atoi` の表現可能範囲を超える文字列に対する結果はこのコードで定義・検査されていません。

## 有効になる条件

- このコードを含むビルドで `STRATA_NATIVE_EXPERTS` が有効であり、CPU native expert の down 行経路を通る必要があります。CMake は同オプションが有効なときに `native_expert.cpp` を CPU kernels に追加します（`engine/CMakeLists.txt:725-735`; `engine/cmake/backends/cpu.cmake:303-318,370`）。
- 実行 CPU は AVX-512F/DQ/BW/VL と VNNI を備え、OS が AVX-512 状態を保存できる必要があります。さらに VBMI がない CPU では `STRATA_VNNI_TIER` の値が先頭文字 `'1'` であることが必要です。VBMI がある CPU ではこの追加 opt-in 条件は不要です。非 x86 実装では `cpu_vnni_ok()` は false です（`engine/src/kernels/cpu/expert_layout.cpp:42-51,188-203`）。
- `STRATA_NO_Q50_512` が**未設定**である必要があります。値の内容ではなく設定有無を判定するため、空文字を含め何か設定すると無効化します（`engine/src/kernels/cpu/native_expert.cpp:820-824`）。
- `f.d_type == 6`（Q5_0）、`nt >= STRATA_Q50_512_MIN` の変換結果、`f.tail_off == 0` が必要です。Q5_0 以外や tail 付きの場合はこのカーネルを使いません（同 `:824-827`）。
- 初回の照合で、Q5_0 の AVX-512 結果がリンクされた quant dot と bitwise 一致しなければ不使用になります。照合には Q5_0 dot と Q8_0 activation quantizer も必要です（同 `:204-239`）。

他の CLI 引数でこの閾値を上書きする処理は、この読み取り・dispatch 経路にはありません。`STRATA_VNNI_TIER` は Q5_0 以外も含む VNNI tier 判定に関わりますが、この変数自体が読むのは閾値だけです（`engine/src/kernels/cpu/expert_layout.cpp:188-203`; `engine/src/kernels/cpu/native_expert.cpp:822-824`）。

## 実行時の詳細

CPU pool は native expert の down 行を `native_down_rows` または `native_down_rows_invariant` に渡します。どちらも同じテンプレート実装を使い、Q5_0 AVX-512 条件が成立すると `q50_512_down_rows` を呼び出して戻ります。ここに到達しない場合は後段の `traits(f.d_type).dot` による各 token の dot 計算に進みます（`engine/src/kernels/cpu/pool.cpp:1274-1310,1420-1453`; `engine/src/kernels/cpu/native_expert.cpp:820-825,859-891,903-915`）。

`q50_min` と `q50_512` は関数内 `static` で、各 `NativeArithmetic` テンプレート特殊化がこの分岐に初めて到達したときにキャッシュされます。プロセス中に環境を変更しても、すでに初期化された特殊化には反映されません。CPU feature 判定も `cpu_vnni_ok()` 内で static cache されます（`engine/src/kernels/cpu/native_expert.cpp:792-824`; `engine/src/kernels/cpu/expert_layout.cpp:188-203`）。

Q5_0 カーネルの初回照合は各プロセス内で一度だけ行われます。照合が不一致なら stderr に `strata: the 512-bit Q5_0 down rows differ from this ggml-cpu's dot: not used` を出して false を返し、その呼び出しは通常 dot 経路に進みます。一致時や他の条件不足時に、この変数専用の有効ログ・警告・終了処理はありません（`engine/src/kernels/cpu/native_expert.cpp:204-239,824-827`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:820-827` — Q5_0 down の抑止、閾値、型・tail・照合条件とカーネル dispatch。
- `engine/src/kernels/cpu/native_expert.cpp:204-239` — Q5_0 カーネルの初回照合および不一致ログ。
- `engine/src/kernels/cpu/native_expert.cpp:859-891,903-915` — 通常 dot への fallback と default / invariant の公開関数。
- `engine/src/kernels/cpu/pool.cpp:1274-1310,1420-1453` — CPU pool から down 行関数への呼び出し。
- `engine/src/kernels/cpu/expert_layout.cpp:42-51,188-203` — 非 x86 の false と VNNI / `STRATA_VNNI_TIER` 判定。
- `engine/CMakeLists.txt:725-735`; `engine/cmake/backends/cpu.cmake:303-318,370` — native expert ソースを含める build 条件。
