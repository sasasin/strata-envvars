# `STRATA_WINDOW_SYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier が各推論 window の GPU graph を投入する直前に、デバイスの queue 群を待つかを切り替える。`1` は毎回待ち、`0` は待たず、`2` は初回または前の window 完了から一定時間空いた場合だけ待つ。待つと直前の GPU 作業との重なりがなくなる。window 内の処理や、投入後に行う window 完了待ちはこの変数では無効にならない（`engine/sycl/src/core/verify.cpp:2450-2474, 2749-2764`）。

読み取りは `Verifier::run` に一箇所あり、通常の CUDA/HIP 経路ではなく `engine/sycl/src/core/verify.cpp` の SYCL 実装に属する。SYCL backend は別の engine build として構成される（`engine/sycl/CMakeLists.txt:1-9, 21`、`engine/CMakeLists.txt:23-32`）。

## 値と判定

`std::getenv` の返す文字列を `std::atoi` に渡す。環境変数が未設定の場合だけ GPU 情報に基づく既定値を使う。設定値は `0` / `1` / `2` との文字列比較ではなく、`atoi` の整数変換結果で判定する（`engine/sycl/src/core/verify.cpp:2466-2474`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に同期しない値 |
|---|---:|---|---|
| SYCL verifier の GPU が i915、Alchemist 世代、または `host_unified_memory` 対応 | 1 | 変換結果が `1`（常時）または `2`（初回・gap 時） | `0` と上記以外 |
| 上記以外 | 0 | 変換結果が `1`（常時）または `2`（初回・gap 時） | `0` と上記以外 |

`atoi` は先頭の空白と符号を受け付け、数字の先頭部分だけを変換し、後続文字を検査しない。したがって `" 1tail"` は 1、`"2x"` は 2、`"-1"` は -1 となり、最後の値は同期しない。空文字、`true`、数字で始まらない文字列は 0 として同期しない。`"0anything"` も 0 となる。数値範囲の検証、clamp、無効値の警告や fallback はない。整数範囲外の文字列に対する `atoi` の結果は規定されないため、動作を断定できない（同上）。

## 有効になる条件

- `engine/sycl/src/core/verify.cpp` の `Verifier::run` が実行されること。SYCL backend が別 engine build であるため、この読み取りは CUDA/HIP engine の該当経路にはない（`engine/CMakeLists.txt:23-32`）。
- unset 時の既定値 1 は、現在の SYCL device が i915 driver を使う、Intel GPU generation が Alchemist である、または SYCL device が `host_unified_memory` を報告する場合に選ばれる。それ以外は 0。`host_unified_memory` の問い合わせが例外を投げた場合は `igpu=false` として扱う（`engine/sycl/src/core/verify.cpp:294-295, 2466-2472`）。
- 値 2 の待機条件は、プロセス内で最初の window、または現在の window の投入時刻と直前の window 完了時刻との差が 20 ms を**超える**場合。ちょうど 20 ms 以下なら待たない。各 window の完了時刻は関数内 static の `t_prev_end` に記録される（同 `2450-2451, 2473-2474, 2757-2764`）。
- 他の環境変数、CLI 引数、サーバーモード、モデル量子化による上書きや追加条件は、この読み取り箇所にはない。CLI とサーバーのどちらから verifier の window が実行される場合も、この分岐自体にモード別判定はない（同 `2384-2397, 2466-2474`）。

## 実行時の詳細

設定値と unset 時の既定値は関数内 `static` の `wmode` に保存される。`getenv` のポインタも static で、値への変換は `wmode` の初期化時に一度だけ行う。device の `host_unified_memory` 判定も static である。したがって最初の評価後に環境を変更しても反映されず、同一プロセス内で別の verifier/device が使われても `wmode` は再評価されない（`engine/sycl/src/core/verify.cpp:2466-2474`）。

各 window で `t_launch` を記録した後、現在の SYCL device の `queues_wait_and_throw()` を条件付きで呼ぶ。モード 1 は毎回、モード 2 は `first_or_gap` のときだけ呼び、モード 0 とその他の整数値では呼ばない。その後 graph を投入し、window 処理の後段では `queue_wait_diag(..., "window sync", ...)` による完了待ちを別途行うため、モード 0 も非同期のまま次へ進む設定ではない（同 `2450-2475, 2587-2610, 2749-2781`）。

事前待機の `queues_wait_and_throw()` が SYCL 例外を投げると、`Verifier::run` の例外処理が stderr に失敗内容を出し、window の失敗を返す。エラーが device lost と判定された場合は device lost 状態も記録する（`engine/sycl/src/core/verify.cpp:1990-2004, 3000-3003`）。

## ログと測定値

この変数の値や同期モードを表示する専用ログはない。事前待機で SYCL 例外が起きた場合は、stderr に `strata verify: window run failed on verifier device <device>: <exception>` を出力する。device lost の場合は続けて `strata verify: GPU device lost during window run. <hint>` を出す。window の後段の同期に失敗すると verifier は `verify: <wait error または error string>` を返す（`engine/sycl/src/core/verify.cpp:1990-2004, 2753-2780, 3000-3003`）。

ソースコメントには特定の Arc A750 / i915、A770 / xe、Arc 140T / xe の試行回数や token/s が記録されているが、これらはコード内コメントの測定メモであり、この調査では再測定していない。一般的な性能値としては扱わない（同 `2453-2465`）。

## 根拠

- `engine/sycl/src/core/verify.cpp:2384-2397` — window を処理する `Verifier::run` と前提検査。
- `engine/sycl/src/core/verify.cpp:2450-2475` — queue 同期の値、既定値、評価時期、20 ms 条件。
- `engine/sycl/src/core/verify.cpp:2749-2781` — 事前待機とは別の window 完了同期と失敗処理。
- `engine/sycl/src/core/verify.cpp:1990-2004, 3000-3003` — SYCL 例外時の stderr と失敗返却。
- `engine/CMakeLists.txt:23-32`、`engine/sycl/CMakeLists.txt:1-9, 21` — SYCL backend が独立した build であること。
