# `STRATA_MMVQ_A2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンの Q6_K wide matvec kernel で、Q6_K の量子化データと Q8_1 activation を読む aligned-load variant（A2）を選ぶ。未設定時は A2 が有効。`0` 相当なら同じ wide kernel の従来の load variant を選び、wide kernel 自体を直接無効にはしない。通常の選択経路は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` の `native_q6_k_mmvq` → `launch_q6k_wide` → `native_mmvq_q6k_wide_kernel`（同 3935-3956、1649-1707）。

## 値と判定

`q6k_a2()` は `std::getenv` の未設定判定と `std::atoi(...) != 0` で bool 化し、関数内 `static const` に保存する（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548`）。設定値を文字列全体として検証しない。`atoi` が数値変換できない文字列は 0 となるため A2 は無効になり、数値の後ろの文字は判定に使われない。

| ビルド・条件 | unset | 設定時に A2 が有効 | 設定時に A2 が無効 |
|---|---|---|---|
| SYCL 実装の Q6_K wide kernel | 有効 | `atoi` の結果が非 0（例: `1`, `-1`, `1abc`） | `atoi` の結果が 0（例: `0`, 空文字, `true`, `false`, `abc`, `0anything`） |

`atoi` は先頭空白と符号を許し、数値部分以降を読み飛ばす。値域・文字列全体・大文字小文字の検証や clamp はない。したがって `  +2tail` も有効扱いとなる。数値として表現できない範囲の入力に対する結果は、このコードで定義していない。

## 有効になる条件

- `engine/sycl/CMakeLists.txt:43-46` が含める SYCL kernel 実装でのみ読み取る。CUDA/HIP 実装にはこの変数の参照がなく、対象は SYCL backend の経路。
- `native_mmvq` が GGML type 14（Q6_K）を受け、`native_q6_k_mmvq` に到達する必要がある（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4217`）。
- `native_q6_k_mmvq` は最初に Q6 packed、次に planar の経路を試す。そこで処理が完了すれば A2 の判定には進まない（同 3935-3938）。
- wide kernel の選択には `STRATA_MMVQ_WIDE` が有効であること（unset なら有効、設定時は `atoi != 0`）、`ncols >= 1` かつ `ncols <= wide_maxc`、`n_in % 256 == 0`、`n_out >= wide_min` が必要（同 2185、3943-3956）。`STRATA_MMVQ_WIDE_MIN` / `STRATA_MMVQ_WIDE_MAXC` を設定するとそれぞれの `atoi` 値が既定境界を置き換える。
- wide 境界の既定値は A2 有効時 `wide_min=0`, `wide_maxc=8`、無効時 `wide_min=4096`, `wide_maxc=4`（同 3943-3944）。従って A2 を無効にすると、既定では `n_out < 4096` または 4 列超で wide route に入らない。境界変数で条件を変えて wide route に入れた場合でも、A2 無効なら旧 load variant が選ばれる。
- Q6 packed / planar の分岐が処理しない場合でも、wide 条件に入らなければ後続の rowwarp または通常 kernel に進む。rowwarp は `ncols` 1-4、`rowwarp_rpw() > 0`、`n_in % 256 == 0` の場合に wide 分岐の後で試される（同 3958-3967）。

## 実行時の詳細

`native_q6_k_mmvq` の wide 分岐が呼び出されると、`launch_q6k_wide` は `rpw == 1 && q6k_a2()` の場合に A2 kernel を起動する（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1652-1687`）。他の `rpw` では macro 展開された分岐も `q6k_a2()` を確認し、真なら A2、偽なら旧 variant を起動する（同 1688-1702）。

A2 kernel は `load16_a2` で Q6_K の `ql` / `qh` から 16-byte 境界に整列したチャンクを読み、必要なシフトを組み立てる。Q8_1 側は A2 時 `ld_i4_a4`、旧経路では `sycl::int4` の reinterpret load を使う（同 1526-1543、1571-1595）。この環境変数が変えるのはこの load variant と、上記の既定 wide shape 境界であり、別の Q6_K kernel が選ばれた場合には A2 load は使われない。

値の最初の評価は `q6k_a2()` の初回呼び出しで、その結果はプロセス内 static にキャッシュされる。以後の環境変更は反映されない。CLI 引数や設定ファイルからこの変数を読む処理、子プロセスへの転送処理はこの参照箇所群にはない。

## ログと測定値

この分岐に `STRATA_MMVQ_A2` の値や A2 選択を出力するログはない。wide kernel 起動後の SYCL 実行エラーは利用環境の SYCL 例外経路に委ねられ、この変数固有の警告・終了処理は実装されていない（起動箇所: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1653-1707`）。

同ファイルのコメントは A2 の性能比較を記載するが、測定環境等の条件をこの記述だけから揃えて確認できないため、性能値はここでは一般化しない（同 3940-3942）。

## 根拠

- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548` — 値の判定と static cache。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1526-1543,1571-1595` — A2 / 旧 load の違い。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1649-1707` — A2 kernel 選択と起動。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185,3935-3978,4204-4217` — wide kernel の既定有効、優先順、shape gate、Q6_K dispatch。
- `engine/sycl/CMakeLists.txt:43-46` — この実装ファイルを含む SYCL kernel source。
- `docs/INTEL.md:437-460` — SYCL/Intel 用スイッチ一覧にある説明との照合。測定値の根拠には使用していない。
