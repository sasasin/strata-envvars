# `STRATA_NO_Q50_512`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert down projection が Q5_0（type 6）で、token 数が `STRATA_Q50_512_MIN`（未設定時 2）以上の場合に使う 512-bit Q5_0 カーネルを無効にする。未設定なら条件付きで `q50_512_down_rows` を選び、設定されていれば通常の `traits(...).dot` による token ごとの処理へ進む。閾値を 1 以下に設定すれば 1 token でも対象になる。対象は CPU native expert pool の down rows であり、GPU の Q5_0 カーネルを切り替える変数ではない（`engine/src/kernels/cpu/native_expert.cpp:820-826, 859-891`、呼び出し元 `engine/src/kernels/cpu/pool.cpp:1303-1309, 1445-1453`）。

## 値と判定

`std::getenv("STRATA_NO_Q50_512") == nullptr` かだけを判定する。文字列を parse しないため、unset のときだけ無効化されず、空文字を含む何らかの値が設定されていればカーネルを無効にする。大文字小文字、空白、数値としての妥当性は関係しない（`engine/src/kernels/cpu/native_expert.cpp:822`）。

| 条件 | unset | 設定時に機能が無効になる例 |
|---|---|---|
| native expert CPU down rows | Q5_0 512-bit カーネルの候補になる | `1`、`0`、`true`、`false`、空文字、`0anything` など、値の内容を問わず無効 |

## 有効になる条件

- `STRATA_NO_Q50_512` が未設定で、`cpu_vnni_ok()` が true であること。これは x86 の CPU 機能と OS の AVX-512 状態を調べる。CPU が VNNI を持たない、または OS が AVX-512 状態を保存しない場合は候補にならない（`engine/src/kernels/cpu/expert_layout.cpp:80-110, 188-204`）。非 x86 では `cpu_vnni_ok()` は常に false（同 `:42-51`）。
- `STRATA_FORCE_AVX2` の値が `1` で始まる場合、または `STRATA_FORCE_ISA` が `avx2` / `avx` / `sse` / `sse4.2` / `none` の場合、ISA 判定が抑えられ `cpu_vnni_ok()` は false になる。`STRATA_VNNI_TIER` の値が `1` で始まることは、VNNI はあるが `cpu_avx512_ok()` が false の CPU で VNNI tier を許可する条件に関係する（`engine/src/kernels/cpu/expert_layout.cpp:26-39, 75-78, 188-202`）。
- ビルドに native expert CPU 実装が含まれ、その pool がこの処理を呼ぶこと。標準 engine は `STRATA_NATIVE_EXPERTS` が有効なとき native expert 実装を組み込み、CPU pool から down rows を呼ぶ。CUDA / HIP / SYCL / Metal を使うプロセスでも、ここで対象にするのは CPU native expert pool の経路であり、GPU kernel の選択には作用しない（`engine/CMakeLists.txt:725-736`、`engine/cmake/backends/cpu.cmake:303-317, 370`、`engine/sycl/CMakeLists.txt:220-236`、`engine/metal/CMakeLists.txt:138-146`、`engine/src/kernels/cpu/pool.cpp:1303-1309, 1445-1453`）。
- 下 row の型が Q5_0 (`f.d_type == 6`)、`f.tail_off == 0` であり、token 数 `nt` が `STRATA_Q50_512_MIN` 以上であること。`STRATA_Q50_512_MIN` は未設定なら 2、設定時は `atoi` の結果を使う。空文字や数字で始まらない文字列は 0、`2x` は 2、負値もそのまま比較に使われるため、通常の「N 以上」という範囲検証はない（`engine/src/kernels/cpu/native_expert.cpp:823-825`）。
- 初回の適合性確認 `q50_512_ok()` が true であること。確認は現在のビルドの Q5_0 dot と 512-bit kernel を、合成データ（幅 96 / 640、16 rows、3 tokens）で比較し、全 float の bit 列が一致するかを見る。どれかが不一致なら専用 kernel を選ばない（`engine/src/kernels/cpu/native_expert.cpp:204-239`）。
- CLI 引数、サーバーモード、モデル設定ファイルによるこの変数の上書き・優先順位はコード上にない。対象の down row が CPU pool で処理されなければ、この変数の分岐にも到達しない（読み取りと dispatch: `engine/src/kernels/cpu/native_expert.cpp:820-826`）。

## 実行時の詳細

`native_down_rows_impl` は通常経路と `WindowInvariant` 経路から呼ばれる。各 template specialization で `q50_512` と `q50_min` を初めて実行したときに `static` 値として読み取るため、その specialization の最初の呼び出し後にプロセス環境を変更しても再評価されない。CPU ISA 判定と適合性確認にも `static` cache がある（`engine/src/kernels/cpu/native_expert.cpp:792-825, 903-915`; `engine/src/kernels/cpu/expert_layout.cpp:80-111, 188-204`）。

専用 kernel が選ばれると、Q5_0 の down rows を `q50_512_down_rows` に渡し、重み block pair の decode を token 間で共有する。適合性確認に失敗した場合、または環境変数・CPU・型・tail・token 数などの条件が満たされない場合は、後続の一般処理で `traits(f.d_type).dot` を token ごとに実行して出力 row を計算する（`engine/src/kernels/cpu/iq_avx512.cpp:773-855`、fallback `engine/src/kernels/cpu/native_expert.cpp:859-891`）。子プロセスへの転送や環境変数の書き換えはこの箇所では行わない。

## ログと測定値

適合性確認で不一致が出た場合、stderr に `strata: the 512-bit Q5_0 down rows differ from this ggml-cpu's dot: not used` を出して専用 kernel を使わない（`engine/src/kernels/cpu/native_expert.cpp:229-239`）。環境変数で無効化した場合や、CPU / 型 / token 数などの条件を満たさず fallback した場合に、この変数専用のログはない。ここでは性能測定値を記載しない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:820-826` — 環境変数、token 数、型、tail、適合性確認による分岐。
- `engine/src/kernels/cpu/native_expert.cpp:204-239` — Q5_0 512-bit kernel の一度限りの比較と不一致ログ。
- `engine/src/kernels/cpu/native_expert.cpp:859-891` — fallback の dot と出力計算。
- `engine/src/kernels/cpu/iq_avx512.cpp:773-855` — Q5_0 down row kernel。
- `engine/src/kernels/cpu/expert_layout.cpp:26-39, 42-51, 75-110, 188-204` — ISA cap、非 x86 stub、VNNI tier 判定。
- `engine/src/kernels/cpu/pool.cpp:1303-1309, 1445-1453` — CPU pool から down rows への呼び出し。
