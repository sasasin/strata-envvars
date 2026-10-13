# `STRATA_GROUP_COPY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt prefill の MoE expert grouping 用配列について、GPU から通常の host vector へ読み戻して処理後に GPU へ書き戻す経路を使うか、mapped/pinned host memory とその device alias を使うかを切り替える A/B 用の変数です。先頭文字が `1` のとき mapped buffer の確保を抑え、通常の host vector と明示的な転送を使わせます。ルーティング結果や grouping の計算内容を変更するものではありません。

## 値と判定

CUDA と SYCL の両実装で `getenv()` の結果の先頭文字だけを `gc[0] == '1'` と比較します。文字列全体の parse は行いません。

| 値 | buffer の確保判定 |
|---|---|
| unset、空文字、先頭が `1` 以外 | `grp_n < need` なら mapped/pinned buffer の確保を試みる（既定動作） |
| 先頭文字が `1` | `grp_n < need` でも新たな mapped/pinned buffer を確保しない |

したがって `1`, `10`, `1anything` は同じ分岐です。`true`, `0`, 空文字は mapped buffer を抑止しません。`need` 以上の buffer がすでにある場合は確保判定自体に入らず、その既存 buffer を引き続き使います。そのため、設定値は `Prefill::init()` の呼び出しごとに読み直されますが、既に確保された十分な buffer を `1` で解除する動作ではありません。

## 有効になる条件

- CUDA または SYCL の prompt prefill 実装で参照されます。確認した読み取り箇所は CUDA の `src/prefill/prefill.cpp` と SYCL の `sycl/src/prefill/prefill.cpp` です。
- mapped buffer が実際に使われるのは、確保に成功して `grp_host != nullptr` となった場合です。CUDA は `cudaHostAllocMapped` と `cudaHostGetDevicePointer`、SYCL は `sycl::malloc_host` を使います。
- `STRATA_TEST_PAGEABLE` の先頭文字が `1` なら `force_pageable()` が true となり、この buffer の確保を試みません。確保 API が失敗した場合も通常のコピー経路へ進みます。
- 環境変数を読むのは `Prefill::init()` 内の容量確認時です。値が先頭 `1` で、過去により小さい mapped buffer が確保済みの状態から、より大きな `need` で再初期化すると、コードは再確保を行わず既存 pointer を残します。この場合の容量不足を回避する分岐は見当たりません。通常は初期化前に設定する値として扱う必要があります。
- GPU 上で grouping を行う fused path では、同じ host grouping buffer の分岐を通りません。host で token/expert の組を group 化する分岐に入った場合に影響します。

## 実行時の詳細

`need` は `3 * T * K + 2 * (n_expert + n_expert / MMQ_GROUP + 2)` 個の `int32_t` で計算されます。mapped buffer が使える場合、`ids`, `slot`, `src` を mapped host memory 上で読み書きし、GPU routing 結果の読み戻しと slot/src の書き戻しには device alias を使います。MMQ を使うときは grouping bounds も同じ領域に置いて alias 側へ転送します。

mapped buffer がない場合、`ids` は device から通常の host vector に読み戻し、処理後の `slot` と `src`、MMQ の bounds は host から device buffer へコピーします。このため変数名の通り、先頭 `1` は mapped 経路の A/B 対照となるコピー経路を選びます。prefill の routing/grouping 手順自体は両経路で共通です。環境変数専用のログやエラー文は確認できません。

SYCL 実装は CUDA 実装と同じ先頭文字判定・容量条件を持ち、確保できなかった場合も通常の host vector と queue memcpy を使います。

## 根拠

- `src/prefill/prefill.cpp:1132-1152` — 値判定、必要容量、CUDA mapped/pinned buffer の確保と失敗時の fallback。
- `src/prefill/prefill.cpp:3045-3055, 3270-3276, 3345-3360` — host-grouped path での ids 読み戻し、slot/src/bounds の mapped 経路とコピー経路。
- `sycl/src/prefill/prefill.cpp:1018-1054` — SYCL の同じ値判定と host allocation。
- `sycl/src/prefill/prefill.cpp:3310-3328, 3411-3424, 3445-3467` — SYCL host-grouped path の mapped 経路と memcpy fallback。
- `src/prefill/prefill.cpp:3260-3261` — fused path では GPU 上で grouping し、host-grouped 分岐を通らないこと。
