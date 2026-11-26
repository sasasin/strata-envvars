# `STRATA_GROUP_COPY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

MoE prompt prefill の host grouping で使う routing table（`ids`、`slot`、`src`、group bounds）の置き方を選ぶ。mapped pinned host memory を作れた場合はそこで host が表を作り、device alias から読む経路を使う。copy 側では通常の host vector で表を作り、device へ転送する。対象は `Prefill::init` と `Prefill::run_impl` の CUDA/HIP 実装、および SYCL 実装である（`engine/src/prefill/prefill.cpp:2443-2456,2570-2593`、`engine/sycl/src/prefill/prefill.cpp:1389-1403,1507-1546`）。

CUDA/HIP と SYCL では既定値と値判定が異なる。Metal の `Prefill::init` は `STRATA_GPU_METAL` 分岐で早期 return し、この変数を読む箇所に進まない（`engine/src/prefill/prefill.cpp:2449-2454`）。

## 値と判定

どちらの実装も `std::getenv` の結果の先頭文字だけを見る。文字列全体の parse、空白除去、大文字小文字変換、数値範囲検査はしない（`engine/src/prefill/prefill.cpp:2576-2577`、`engine/sycl/src/prefill/prefill.cpp:1513-1515`）。

| 実装 | unset | mapped allocation を選ぶ値の例 | mapped allocation を選ばない値の例 |
| --- | --- | --- | --- |
| CUDA/HIP | mapped allocation を試みる | `0`、`0anything`、空文字、`true`、`2`、` 1` | 先頭が `1` の値（`1`、`10`、`1anything`） |
| SYCL | copy 側を選ぶ | 先頭が `0` の値（`0`、`0anything`） | 空文字、`1`、`true`、`2`、` 0` |

表は allocation を試みるかの判定であり、mapped memory の利用を保証しない。既存の `grp_n` が今回必要な大きさ以上なら allocation 判定部分を通らず、保持中の `grp_host` の有無で実行経路が決まる。そのため、より大きな mapped allocation がすでに保持されている場合、後の初期化で copy 側の値を指定しても mapped 経路が残り得る（CUDA/HIP: `engine/src/prefill/prefill.cpp:2577-2588`、SYCL: `engine/sycl/src/prefill/prefill.cpp:1515-1538`）。

## 有効になる条件

- MoE prompt prefill が `Prefill::run_impl` の host grouping 側に進むと、`m.grp_host != nullptr` で mapped 経路を選ぶ。fused expert path 側ではこの host grouping 分岐を通らない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5862-5875`、SYCL: `engine/sycl/src/prefill/prefill.cpp:4041-4050`）。
- mapped 経路には `STRATA_TEST_PAGEABLE` が無効であることと、backend の host allocation / device alias 作成の成功が必要。`force_pageable()` は同変数の先頭文字が `1` の場合に true となる static cache である（CUDA/HIP: `engine/src/prefill/prefill.cpp:361-364,2581-2592`、SYCL: `engine/sycl/src/prefill/prefill.cpp:206-209,1519-1545`）。
- allocation が禁止または失敗した場合、`grp_host` は設定されず copy 経路に進む。ここでは `STRATA_GROUP_COPY` による別の警告やエラーは出さない（同上）。
- CLI 引数や設定ファイルからこの変数を上書きする処理は、候補名の全参照と該当 helper の追跡範囲では見つからなかった。優先関係が確認できる別設定は `STRATA_TEST_PAGEABLE` のみ。

## 実行時の詳細

変数は `Prefill::init` が grouping table 用領域を準備するたびに読み取られる。`STRATA_GROUP_COPY` 自体の関数 static cache はない。必要サイズ `need` は chunk の `T*K`、expert 数、CUDA/HIP では `ws::mode()` による weight-stationary 領域を含み、SYCL では `MMQ_GROUP` に基づく bounds 領域を含む（CUDA/HIP: `engine/src/prefill/prefill.cpp:2570-2588`、SYCL: `engine/sycl/src/prefill/prefill.cpp:1507-1538`）。

mapped 経路では CUDA/HIP は `cudaHostAlloc` と `cudaHostGetDevicePointer`、SYCL は `sycl::malloc_host` を試みる。host grouping では routed ids を mapped 領域へ置き、`slot`、`src` と bounds も同じ領域に書いて device 側へ反映する。copy 経路では通常の host vectors を使い、CUDA/HIP は routed ids を同期 download してから routing tables / bounds を upload する。SYCL は `m.cs` から ids を host vector に移し、`slot`、`src`、bounds を device buffer に memcpy する（CUDA/HIP: `engine/src/prefill/prefill.cpp:5867-5874,6170-6177,6529-6536`、SYCL: `engine/sycl/src/prefill/prefill.cpp:4046-4059,4198-4221,4240-4254`）。

未設定・無効値時に CLI 優先順位や fallback 数値はなく、上記 backend ごとの先頭文字判定が直接使われる。copy 経路の CUDA/HIP download/upload 失敗は `err` に理由を設定して `run_impl` を失敗させる（`engine/src/prefill/prefill.cpp:5871-5874,6173-6177,6533-6536`）。SYCL の該当 memcpy 箇所にはこの変数専用のエラー処理はない。

## ログと測定値

この変数を読んだ結果を示す専用ログはない。CUDA/HIP 側の copy 失敗は上記のとおり `err` に記録される。ソースコメントには prefill 時間などの測定値があるが、同コメントだけでは測定環境や条件を十分に特定できないため、ここでは性能値として記載しない（`engine/src/prefill/prefill.cpp:1647-1653`、`engine/sycl/src/prefill/prefill.cpp:846-852,1509-1512`）。

## 根拠

- `engine/src/prefill/prefill.cpp:2443-2456,2570-2595` — CUDA/HIP `Prefill::init`、値判定、mapped allocation と fallback。
- `engine/src/prefill/prefill.cpp:361-364` — `STRATA_TEST_PAGEABLE` の読み取りと cache。
- `engine/src/prefill/prefill.cpp:5862-5875,6170-6177,6529-6536` — host grouping、ids download、routing table / bounds の転送とエラー。
- `engine/sycl/src/prefill/prefill.cpp:1389-1403,1507-1546` — SYCL `Prefill::init`、値判定、mapped allocation と fallback。
- `engine/sycl/src/prefill/prefill.cpp:206-209,4041-4065,4198-4221,4240-4254` — pageable 条件、host grouping と table 転送。
