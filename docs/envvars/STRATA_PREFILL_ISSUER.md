# `STRATA_PREFILL_ISSUER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

大きな batched prefill chunk の expert 転送を発行する処理を、専用 host thread で行うか、層を計算する側の thread から逐次発行するかを選ぶ。未設定時は専用 thread を使い、`atoi` の結果が 0 の場合は inline 発行にする。CUDA/HIP 共用実装と SYCL 実装の両方に読み取りがある。いずれも expert の列挙順や ring slot の選び方を変えるスイッチではなく、threaded 経路は `seq` を順に処理し、inline 経路も同じ sequence を `issue_until` で処理する（CUDA/HIP: `engine/src/prefill/prefill.cpp:4730-4750, 4830-4918`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3196-3233, 3260-3313`）。

## 値と判定

両実装とも `std::getenv` の結果を関数内 `static const bool` に一度だけ保存し、未設定なら `true`、設定時は `std::atoi(v) != 0` とする（CUDA/HIP: `engine/src/prefill/prefill.cpp:4757-4760`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3245-3248`）。

| 実装 | unset | 専用 issuer thread を使う値 | inline 発行になる値 |
|---|---|---|---|
| CUDA/HIP 共用 | ON | `1`, `2`, `-1`, `+1`, `1tail` など、`atoi` が 0 以外を返す文字列 | 空文字、`0`, `0tail`, `true`, `false`, `tail` など、`atoi` が 0 を返す文字列 |
| SYCL | ON | 同上 | 同上 |

`atoi` は文字列全体の厳密な数値検証ではない。先頭の空白と符号の後にある数値部分を変換し、後続の文字は判定に使わないため、`  +2x` は ON、`0x1` は 0 として OFF になる。大文字小文字の比較はない。設定された空文字は `getenv` が null ではないものの `atoi("") == 0` のため OFF。境界値として、数値 0 は OFF、負の非ゼロ値は ON である。範囲外の数値文字列についてはコードに独自の検査や fallback がない。

## 有効になる条件

- この読み取りを含む CUDA/HIP または SYCL の engine build であること。CUDA/HIP では `strata_prefill` に `src/prefill/prefill.cpp` が含まれ、HIP build でも同じ target を使う（`engine/cmake/strata_gpu_engine.cmake:478-488`）。SYCL は `src/prefill/prefill.cpp` を別途 build する（`engine/sycl/CMakeLists.txt:304-308`）。
- 対象 chunk が `stream_all` であること。両実装とも `m.ring > STAGE`、`T >= stream_all_min()`、`m.src != nullptr` のすべてを要求する（CUDA/HIP: `engine/src/prefill/prefill.cpp:4625-4629`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3086-3091`）。`STAGE` は両ファイルで 8（CUDA/HIP: `engine/src/prefill/prefill.cpp:321`; SYCL: `engine/sycl/src/prefill/prefill.cpp:199`）。
- 上記を満たさない chunk では、この値が ON でも `threaded_issue` は false となり、当該専用 issuer thread は開始されない（CUDA/HIP: `engine/src/prefill/prefill.cpp:4807,4830,4917-4918`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3259-3260,3303-3304`）。
- この変数を読む箇所に CLI 引数や別の環境変数による上書きはない。実際に有効になるかは、他の設定が間接的に決める ring サイズや chunk サイズにも依存する。

## 実行時の詳細

値は最初に該当箇所へ到達したときに評価され、関数内 static に保存される。従って同一プロセスでその後に環境を変更しても再評価されない。CUDA/HIP build と SYCL build では別の実装を使う。

ON かつ `stream_all` の場合、CUDA/HIP は `strata-issue` thread を作り、thread を pin して device context を設定した上で sequence の expert を ring slot に転送する。SYCL も専用 thread から sequence を転送する。OFF、または `stream_all` でない場合、専用 thread は作られず、streaming 対象なら最初の ring 分を inline で発行し、その後も consumer が返却した範囲に合わせて inline で追加発行する（CUDA/HIP: `engine/src/prefill/prefill.cpp:4830-4834, 4917-4918, 4941-4945`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3260-3304, 3306-3313`）。

## ログと測定値

この変数の読み取りや ON/OFF だけを知らせるログは見つからなかった。CUDA/HIP では `STRATA_PREFILL_ROUTED_STREAM` が有効で、streaming chunk が routed walk の条件を満たさない場合に理由を一度 stderr に出す。その理由の一つが、この変数を 0 にして inline issuer を使う場合で、出力は `strata: STRATA_PREFILL_ROUTED_STREAM=1 is not used: the inline issuer (STRATA_PREFILL_ISSUER=0) copies every expert`（改行付き）。このログは routed-stream 側の条件付き診断であり、issuer の切替自体を示すログではない（`engine/src/prefill/prefill.cpp:4779-4795`; 理由文字列 `engine/include/strata/prefill/routed_stream.hpp:48-54`）。

## 根拠

- CUDA/HIP と SYCL の値判定・cache: `engine/src/prefill/prefill.cpp:4757-4760`; `engine/sycl/src/prefill/prefill.cpp:3245-3248`。
- streaming の条件と inline/threaded 分岐: `engine/src/prefill/prefill.cpp:4625-4629, 4807-4808, 4830-4834, 4917-4918`; `engine/sycl/src/prefill/prefill.cpp:3086-3091, 3259-3263, 3303-3313`。
- build target: `engine/cmake/strata_gpu_engine.cmake:478-488`; `engine/sycl/CMakeLists.txt:304-308`。
- 条件付き routed-stream ログ: `engine/src/prefill/prefill.cpp:4779-4795`; `engine/include/strata/prefill/routed_stream.hpp:48-54`。
