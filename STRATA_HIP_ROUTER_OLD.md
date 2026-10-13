# `STRATA_HIP_ROUTER_OLD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバーの動作は対象外。

## 役割

MoE ルーター（`router_top10`）で、gfx906 以外の HIP ビルドに限り fast kernel ではなく portable kernel（`router_top10_kernel`、serial FP64 sum と block barrier を持つ形）を走らせる opt-in。fast kernel は ids/weights が portable と bitwise 一致で、測定済みカード（R9700 / 9070 XT）では既定で fast が走る。この変数を設定すると portable kernel に戻す。

読み取りは `src/kernels/cuda/router_top10.cu` の `router_top10()` 1 箇所（SYCL に同一ロジックのミラー `sycl/src/kernels/cuda/router_top10.dp.cpp:694`）。

## 値と判定

判定は `std::getenv(...) != nullptr`（設定されているかどうか）だけで、値の内容は比較しない。

| 状態 | `old` | 走る kernel |
|---|---|---|
| 未設定（`nullptr`） | false | fast kernel（形状条件が揃うとき。既定） |
| 空文字 `""` | true | portable kernel |
| `1` | true | portable kernel |
| `0` | true | portable kernel |
| `true`, `false`, `2` など | true | portable kernel |

docs の「`STRATA_HIP_ROUTER_OLD=1` runs the portable kernel」は、値が `1` であることではなく「設定されていること」で portable に戻る。`STRATA_HIP_ROUTER_OLD=0` でも portable kernel。未設定だけが fast。

根拠: `src/kernels/cuda/router_top10.cu:431`。

## 有効になる条件

- ビルドが HIP（`#if defined(__HIPCC__)`）かつ **gfx906 用 macro が無い**（`#else` 分岐）。gfx906 ビルドでは同じ `old` 変数が `STRATA_HIP_ROUTER_FAST`（別変数）から決まり、`STRATA_HIP_ROUTER_OLD` は読まれない（`router_top10.cu:426-432`）。
- fast path を通らない条件（`old` が true）なら、形状によらず portable kernel path へ falls through。fast path が選ばれるのは `n_tokens > 0 && n_expert > 64 && n_expert <= 512 && k > 0 && k <= 32` のとき（`router_top10.cu:433`）。この外では `old` の値にかかわらず portable path（`router_top10.cu:474-482`）。

## 実行時の詳細

`old` は `static const bool` で、プロセス内で最初に呼ばれたとき一度だけ環境を読む。その後の環境変更は再評価されない。

portable path は `router_top10_kernel`（`router_top10.cu:481`）。fast path は `launch_generic(..., mode 1)` の `router_top10_fast_kernel<false>`（`router_top10.cu:391-394`）。両者は同じ ids/weights を返す（fast kernel の注釈 `router_top10.cu:279-281`）。launch 失敗は stderr に出して `exit(1)`。

## 測定値（資料に記載）

`docs/AMD_HIP.md:323-327`（資料中の主張。本調査で計測器動作を独自確認した事実ではない）: fast kernel（portable と bitwise 同一）は call あたり 39 → 9-12 us、decode R9700 62.4 → 70.0 tok/s、9070 XT +4%。`STRATA_HIP_ROUTER_OLD=1` は portable kernel を走らせる、とある。portable path 側の数値は資料に单独記載がなく、fast と結果（ids/weights）は一致する。

## 相互作用

- `STRATA_HIP_ROUTER_FAST`（別変数）: gfx906 ビルドではこちらが `old` を決める。両変数は同じ `old` 変数に割り当てられるが、ビルド macro（`STRATA_HIP_GFX906`）でどちらを読むかが分かれる。
- `STRATA_ROUTER_BLOCK`: gfx906 の既定 path（wave64 kernel）の選択に影響。

## 根拠

- 読み取り・判定: `src/kernels/cuda/router_top10.cu:426-433`（`#else` の `!= nullptr`）。
- fast / portable kernel 定義と mode 対応: `src/kernels/cuda/router_top10.cu:279-281,385-403,481`。
- SYCL ミラー: `sycl/src/kernels/cuda/router_top10.dp.cpp:691-694`。
- docs 照合: `docs/AMD_HIP.md:323-328`。テスト（`CMakeLists.txt:935` の parity 言及）は実装根拠にしていない。
