# `STRATA_HCD_EXACT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP prefill の hyper-connection down projection（入力幅 `K=10240`、出力幅 `N=320`）に、WMMA kernel `strata_pf_hcdown_exact_bf16` を使う opt-in スイッチです。この kernel は、HIPBLASLt tuning table が選ぶ solution 1176 または 1177 と同じ加算順を再現するよう実装されています。適用できない場合は通常の `bf16_proj` 経路へ戻ります。

CUDA/SYCL の同名ソースにも分岐はありますが、専用 GEMM method が `__HIPCC__` と `STRATA_HIPBLASLT_AVAILABLE` の両方が定義された場合にだけ実装されます。それ以外では method は `false` を返し、呼び出し元が通常 GEMM に fallback します。

## 値と判定

環境変数は `getenv()` の結果の先頭文字だけで判定されます。文字列全体の parse はありません。

| 値 | `hcd_exact()` の結果 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

判定結果は `static const bool` に初回評価時に保存されます。したがって、その後にプロセス環境を変更してもこの判定は更新されません。なお `STRATA_PF_HCDOWN` も別途同じ先頭文字 `1` 判定で読まれ、両方が有効なら通常の分岐では `STRATA_PF_HCDOWN` 側が専用 down+inject kernel を選び、`STRATA_HCD_EXACT` の専用 kernel は選ばれません。

## 有効になる条件

環境変数が有効でも、次の条件を通る必要があります。

- prefill chunk の token 数 `T` が `max(STRATA_PF_SWITCH_MIN_T, 64)` 以上。`STRATA_PF_SWITCH_MIN_T` は未設定なら `0`、設定されていれば `atoll()` の結果で、こちらも初回評価後は固定されます。
- fused recurrent (`gr_unfused()`) ではなく、`m.xn16_lo` が存在しない。この条件を満たさないと入力 stride `ldx` は padded stride にならず、専用 kernel 分岐に入りません。
- `STRATA_PF_HCDOWN` が有効でない。
- down weight が `Bf16InF32` で data があり、shape が `D x LR` と一致する。
- GEMM method が有効な HIPBLASLt 対応ビルドであり、tuning table がロード済みで、対象 shape が `N=320, K=10240, T>=1`。
- tuning table から `hipblaslt_solution_for()` が solution `1176` または `1177` を返す。

最後の二条件を満たさない場合は専用 kernel を使わず、通常の hipBLAS/GEMM に fallback します。tuning table がない場合は対象 shape で最初の一度だけ stderr に `strata: STRATA_HCD_EXACT: no hipBLASLt tuning table is loaded, so the exact kernel has nothing to match: the hyper-connection down projection stays on hipBLAS` と出します。table が別 solution を返す場合は、`T>=4096` のとき最初の一度だけ solution と `T` を含む警告を出します（短い chunk ではこの警告を出しません）。

## 実行時の詳細

`hc_pad()` がこの変数または `STRATA_PF_HCDOWN` を有効と判断し、chunk 条件を満たすと、prefill の正規化結果 `xn16` の token stride を `D + 64` にします。down projection の後段で inject projection は従来の GEMM 経路を使い、同じ padded stride を読みます。`STRATA_HCD_EXACT` 側の専用 kernel が成功した場合は `hdown` が true になり、通常 down projection の呼び出しが省かれます。失敗時には `hdown` が false のままなので `bf16_proj()` が通常経路を実行します。

リポジトリには gfx1151 向けの `arch_default_env()` 表に `STRATA_HCD_EXACT=1` が含まれ、gfx12 向け表には含まれません。ただし、この commit の `src` / `include` / `sycl` で `apply_arch_defaults()` を呼ぶ本番コード箇所は見つからず、同関数は定義とテスト以外から参照されていません。このため、この調査では実行時に gfx1151 で自動設定されるとは断定しません。仮に呼び出される場合の helper の実装は、未設定変数だけに値 `1` を設定し、利用者が何らかの値を設定済みなら保持する仕様です。

## 根拠

- 値判定、cache、`hc_pad()` との関係: `src/prefill/prefill.cpp:337-344`。SYCL 側も同じ判定: `sycl/src/prefill/prefill.cpp:272-279`。
- chunk threshold、stride、down projection の選択と fallback: `src/prefill/prefill.cpp:317-320,2543-2564`。SYCL 側: `sycl/src/prefill/prefill.cpp:252-255,2812-2833`。
- tuning table の有無・shape・solution ID 判定、stderr、fallback: `src/prefill/gemm.cu:544-568`; SYCL 側: `sycl/src/prefill/gemm.dp.cpp:662-686`。
- kernel の HIP/HIPBLASLT compile guard: `src/prefill/gemm.cu:545-546,565-568`。kernel 実装: `src/prefill/wmma_gemm.cu:576-590`。
- gfx1151 / gfx12 の既定値表: `src/core/arch_defaults.cpp:12-34,35-44`。適用 helper と未設定値だけを設定する処理: `src/core/arch_defaults.cpp:61-81`。呼び出し API の記述: `include/strata/core/arch_defaults.hpp:23-26`。
- 設計資料も、対象 projection、solution 1176/1177、tuning table 条件、bitwise parity harness を説明: `docs/STRIX_HALO.md:90-94`。これは資料の説明であり、この調査中に測定やテストを実行したものではありません。
