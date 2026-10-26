# `GPU_MAX_HW_QUEUES`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata がこの変数を読む処理であり、ROCm runtime 自身による解釈・設定効果は対象外。

## 役割

Strata の HIP engine は、特定環境で起動時に GPU hardware queue を先に開く queue priming を行う。priming で2 queueを使い切って draft stream 用の queue が残らなくなるのを避けるため、既定の priming 経路では `GPU_MAX_HW_QUEUES` の数値変換結果が1または2なら priming を見送る。Strata はこの環境変数を設定せず、その runtime 上の効果も制御しない。

## 値と判定

`prime_hw_queues()` は `STRATA_HIP_QUEUE_PRIME` が未設定または空文字の場合にだけ、この変数を参照する。`GPU_MAX_HW_QUEUES` が未設定なら抑止しない。設定されていれば `std::atoi()` の結果が1以上2以下のときに priming を止める。文字列全体の検証はなく、`atoi` の整数変換規則に従う。したがって `1` / `2` は抑止し、`0` / `3` や整数に変換できない文字列はこの条件に当たらない。たとえば `1x` は `atoi` で1となるため抑止する。空文字は `atoi` で0となり抑止しない。

このチェックは `STRATA_HIP_QUEUE_PRIME` の明示指定で回避できる。値が空でなく、文字列全体がちょうど `0` でない場合は priming の spec として扱われ、queue 数チェックへ進まない。したがって `STRATA_HIP_QUEUE_PRIME=nn` は `GPU_MAX_HW_QUEUES=1` または `2` でも priming を試みる。`STRATA_HIP_QUEUE_PRIME=0` は priming 自体を無効にする。

根拠: `src/program/generate.cpp:2262-2290`。

## 有効になる条件

抑止判定が実行されるのは、`STRATA_USE_HIP` が定義され、`STRATA_HIP_GFX906` が未定義のビルドで `strata generate` の通常起動経路に入った場合。`--version` / `-V` と `--families` は先に終了するため priming 関数を呼ばない。`prime_hw_queues()` の呼び出しは option loop より前にある。

さらに、この変数による抑止が起きるのは `STRATA_HIP_QUEUE_PRIME` が未設定または空文字の経路に限られる。Windows ではその既定経路は GPU 世代判定より前に終了するため、`GPU_MAX_HW_QUEUES` の1/2チェックは行われない。Linux の既定経路は primary device が `gfx_arch_is_gfx12()` と判定された場合に限って queue 数を確認する。明示 spec は既定のOS・GPU世代条件を迂回するが、HIP/GFX906 のビルド条件は迂回しない。

根拠: `src/program/generate.cpp:2249-2262,2269-2290,2336-2351,2415-2417`。

## 実行時の詳細

値を読むのは `strata generate` 起動時に呼ばれる `prime_hw_queues()` 内で、static cache は使わない。読み取り後にプロセス環境が変更されるケースを Strata が扱うコードはない。条件に当たると stderr に `strata generate: GPU queues not primed: GPU_MAX_HW_QUEUES=%s leaves none for the draft stream (STRATA_HIP_QUEUE_PRIME=nn primes them anyway)` を出して関数を終了し、Strata は priming 用 stream の作成を行わない。このログは ROCm runtime の実際の queue 上限を検証した結果ではなく、環境変数の `atoi` 値に基づく判断である。

`STRATA_VERIFY_TRACE` による verify trace が有効な場合、CUDA/HIP 共通の `src/core/verify.cpp` と SYCL 側の `sycl/src/core/verify.cpp` では、同名の環境変数を診断行にそのまま表示する（未設定時は `-`）。この読み取りは処理を分岐させず、ログ用である。

根拠: `src/program/generate.cpp:2283-2287,2415-2417`; `src/core/verify.cpp:925-930`; `sycl/src/core/verify.cpp:621-632`。

## 文書との照合

`docs/release-notes-0.2.2.md:23,61` は、値が1または2のとき priming を見送る変更と、`STRATA_HIP_QUEUE_PRIME=nn` による明示指定を記載している。そこでは gfx1201 向けに compile したが gfx12 実機では測定していないとも明記されている。ソース上も同じ抑止条件と明示指定の優先関係を確認した。性能上の効果をこの調査で再測定していない。
