# `FNX_HC1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Flash-Next の split engine が生成中に行う hyper-connection read について、最大何行の window まで `k_hc` の one-barrier 形式を使うかを指定する。既定値は 3 行で、`0` は無効化、`1`～`8` はその行数以下で one-barrier 形式を選ぶ上限になる。値が選ぶのは kernel 内の同期・計算経路であり、別のモデル処理や prompt 読み込みを有効にする設定ではない。実装は `engine/src/split/src/kernels.cu` の `hc1_rows()` と `hc_read()` にある（`engine/src/split/src/kernels.cu:1142-1151,1193-1207`）。

## 値と判定

`env_int` は `std::getenv` で値を取得し、未設定の場合だけ既定値を返す。設定値は符号付き base-10 `long long` として文字列全体を読む。先頭の `+` / `-` と数字列だけが受理され、空文字、空白、末尾の文字、オーバーフローを含む値は整数として受理されない。さらに `hc1_rows()` が範囲を `0`～`8` に制限する（`engine/src/split/src/env.hpp:15-21,33-40`; `engine/src/split/src/kernels.cu:1144-1149`）。

| split engine の経路 | unset | 設定時に有効になる値 | 無効・失敗になる値 |
|---|---:|---|---|
| CUDA / HIP split の `hc_read` | `3` | `0`（one-barrier 形式を選ばない）、`1`～`8`（`T <= 値` で選ぶ） | `-1`、`9` などは範囲外として例外。`""`、`true`、`0anything`、` 3`、`3 ` は整数全体として parse できず例外 |

たとえば `+3`、`03`、`-0` は整数として受理され、結果の数値で範囲判定される。`1.0` や `1e0` は整数形式ではない。大文字小文字の規則は該当せず、真偽値語は受理されない。値の clamp や無効値時の fallback はなく、変換または範囲検査に失敗すると `std::runtime_error` になる（`engine/src/split/src/env.hpp:15-21,33-40`; `engine/src/split/src/kernels.cu:1146-1148`）。

## 有効になる条件

- split engine の CUDA または HIP ビルドで `FNX_KPART == 3` の hyper-connection kernel 実装が使われること。split の CMake は `kernels.cu` を `FNX_KPART` 0～8 の別々の部分として生成し、CUDA/HIP のどちらかでコンパイルする（`engine/src/split/CMakeLists.txt:76-102`; `engine/src/split/src/kernels.cu:22-25,1139-1140`）。
- `Engine` が構築され、window の `hc_read()` に到達すること。`hc_read()` は `one = (T <= hc1_rows())` を作り、`T` ごとの `hc_launch<T>` に渡す（`engine/src/split/src/engine.cu:34-35,65-67`; `engine/src/split/src/kernels.cu:1193-1213`）。
- `FNX_HC1=0` では `T` は正の行数なので one-barrier 形式にはならない。1～8では条件を満たす window のみ対象となり、それより大きい `T` は通常の形式を使う（`engine/src/split/src/kernels.cu:1205-1225`）。
- `engine/src/split/src/prefill.cu` の prompt hyper-connection read は `pf_hc_read()` で別の kernel / GEMM 列を実行し、`hc_read()` や `hc1_rows()` を呼ばない。そのため、この変数の分岐対象は確認できた範囲では split engine の window read（生成経路）であり、prompt read ではない（`engine/src/split/src/prefill.cu:623-645`; `engine/src/split/src/kernels.cu:1193-1207`）。
- CLI 引数、設定ファイル、別の環境変数による上書きはこの読み取り経路にない。既定値は unset のときの `3` のみ。

## 実行時の詳細

`fnx::Engine` のコンストラクターが `hc1_rows()` を明示的に呼び、最初の `hc_read()`（場合によっては CUDA graph capture 内）より前に検証する。関数内 `static const int` に保存されるため、プロセス内では初回評価後に再読込しない。通常の環境変数はプロセス起動前に設定する必要がある（`engine/src/split/src/engine.cu:34-35,65-67`; `engine/src/split/src/kernels.cu:1144-1151`）。

window 読み込みでは `T <= hc1_rows()` のとき `hc_launch<T>(..., true, ...)` が選ばれる。`k_hc<T, ONE, WALK>` の `ONE` 形式は down 側の reduction を各 block で行い、通常形式が使う reduction 後の grid barrier を通らない。コメントでは小さい window 向けとされ、コード上も `ONE` 分岐の有無がこの kernel 処理を変える（`engine/src/split/src/kernels.cu:1205-1213`; `engine/src/split/src/hc.cuh:110-117,239-245,276-308`; dispatch は `engine/src/split/src/hc.cuh:383-395`）。

## ログと測定値

値が範囲外の場合は `FNX_HC1: 0 (off) .. 8 rows, got <値>`、整数として解釈できない場合は `FNX_HC1: '<値>' is not a whole number` が例外理由になる（`engine/src/split/src/kernels.cu:1146-1148`; `engine/src/split/src/env.hpp:34-39`）。sFNX は Engine 構築中の例外について stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1097-1103,1122-1135`）。`fnx_run` 経由では stderr に `fnx_run: <理由>` を出して終了コード 1 になる（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。通常値を選んだことを知らせるログはこの実装にない。

`kbench 1-2 us faster` などの性能説明は `kernels.cu` のコメントにあるが、当該コメントに機種・OS・backend・モデル・量子化・測定回数などの条件は記されていない。`docs/DETAILS.md` および他の Markdown に `FNX_HC1` の記載は見つからないため、測定値としては記載しない。

## 根拠

- 読み取り helper と数値文字列の全体 parse: `engine/src/split/src/env.hpp:15-21,33-40`
- 既定値・範囲・static cache: `engine/src/split/src/kernels.cu:1142-1151`
- Engine 起動時の先行検証: `engine/src/split/src/engine.cu:34-35,65-67`
- window 行数による分岐と dispatch: `engine/src/split/src/kernels.cu:1193-1225`; `engine/src/split/src/hc.cuh:110-117,239-245,276-308,383-395`
- prompt read の別経路: `engine/src/split/src/prefill.cu:623-645`
- 起動エラーの観測: `engine/src/split/tools/sfnx.cpp:1097-1103,1122-1135`; `engine/src/split/tools/fnx_run.cpp:1364-1373`
