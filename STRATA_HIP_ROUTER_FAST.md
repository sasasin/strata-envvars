# `STRATA_HIP_ROUTER_FAST`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバーの動作は対象外。

## 役割

MoE ルーター（`router_top10`）で、gfx906（wave64）ビルドに限り portable カーネルではなく fast kernel（`router_top10_fast_kernel`）を要求する opt-in。fast kernel は serial FP64 sum と block barrier を省いた形だが、ids/weights は portable カーネルと bitwise 一致（`hip_router_fast` が 65,536 行で ties・near-ties・NaN・forced serial を検査）。gfx906 では fast kernel が wave32 形状なので、このカードで測定されるまで既定ではなく「on request」で走る。

読み取りは `src/kernels/cuda/router_top10.cu` の `router_top10()` 1 箇所（SYCL に同一ロジックのミラー `sycl/src/kernels/cuda/router_top10.dp.cpp:692`）。

## 値と判定

判定は `std::getenv(...) == nullptr`（設定されているかどうか）だけで、値の内容は比較しない。

| 状態 | `old` | fast kernel を要求 |
|---|---|---|
| 未設定（`nullptr`） | true | 否（既定の portable / wave64 path） |
| 空文字 `""` | false | 是 |
| `1` | false | 是 |
| `0` | false | 是 |
| `true`, `false`, `2` など | false | 是 |

名前は `=1` を示唆するが、実装は「変数が設定されていれば」要求扱い。`STRATA_HIP_ROUTER_FAST=0` でも fast kernel を要求する。

根拠: `src/kernels/cuda/router_top10.cu:429`。

## 有効になる条件

要求が効くのは、次のすべてを満たすときだけ。

- ビルドが HIP（`#if defined(__HIPCC__)`）かつ **gfx906 用 macro**（`STRATA_HIP_GFX906`）。gfx906 以外の HIP ビルドではこの分岐ではなく `#else` の `STRATA_HIP_ROUTER_OLD`（別変数）が効く。
- 形状条件: `n_tokens > 0 && n_expert > 64 && n_expert <= 512 && k > 0 && k <= 32`（`router_top10.cu:433`）。条件外なら fast path を通らず、既定 path（gfx906 では `n_expert <= 64*RW_PER` かつ `STRATA_ROUTER_BLOCK` 未設定なら wave64 one-wavefront kernel、それ以外なら portable `router_top10_kernel`）へ falls through（`router_top10.cu:461-472,474-482`）。

## 実行時の詳細

`old` は `static const bool` で、プロセス内で最初に呼ばれたとき一度だけ環境を読む。その後の環境変更は再評価されない。

要求かつ条件一致のとき `launch_generic(..., mode 1)` を呼ぶ。mode 1 は `router_top10_fast_kernel<false>`（`router_top10.cu:391-394`）。launch 後 `cudaGetLastError()` を確認、`stream == nullptr` なら `cudaDeviceSynchronize()`。失敗は stderr に出して `exit(1)`（`router_top10.cu:435-446`）。

## 測定値（資料に記載）

`docs/AMD_HIP.md:323-327`（資料中の主張。本調査で計測器動作を独自確認した事実ではない）: fast kernel は portable と bitwise 同一で、call あたり 39 → 9-12 us、decode R9700 62.4 → 70.0 tok/s、9070 XT +4%（ROCm 10.2 nightly）。ユーザーの A/B/A/B（TheRock 7.10、i5-12600K）は +1-4%（12-20% の run-to-run 変動内）。これらは R9700 / 9070 XT の測定。gfx906 の fast path は「このカードで測定されるまで」on request とされ、gfx906 向けの向上数値は資料にない。

## 相互作用

- `STRATA_HIP_ROUTER_OLD`（別変数）: gfx906 以外の HIP ビルドで portable kernel を要求する。gfx906 ビルドでは `STRATA_HIP_ROUTER_FAST` の分岐が優先され、`STRATA_HIP_ROUTER_OLD` は読まれない（`router_top10.cu:426-432`）。
- `STRATA_ROUTER_BLOCK`: gfx906 の既定 path で wave64 kernel を使う条件に影響（設定すると portable kernel へ）。

## 根拠

- 読み取り・判定: `src/kernels/cuda/router_top10.cu:426-433`。
- fast kernel 定義と mode 対応: `src/kernels/cuda/router_top10.cu:282-289,385-403`。
- 既定 path（gfx906）: `src/kernels/cuda/router_top10.cu:461-482`。
- SYCL ミラー: `sycl/src/kernels/cuda/router_top10.dp.cpp:691-692`。
- docs 照合: `docs/AMD_HIP.md:323-328`、`src/kernels/cuda/router_top10.cu:279-281`。テスト（`CMakeLists.txt:935` の parity 言及）は実装根拠にしていない。
