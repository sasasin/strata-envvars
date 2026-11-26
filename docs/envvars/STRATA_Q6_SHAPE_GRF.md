# `STRATA_Q6_SHAPE_GRF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の Q6_K wide MMVQ で、Battlemage 上の限定した行列形状について 256 GRF の A2 kernel を選ぶための opt-in 変数です。条件を満たすときだけ `grf_size<256>` property を付けた kernel へ切り替わります。通常の 128 GRF kernel と計算コードは同じ `native_mmvq_q6k_wide_kernel` の A2 版です（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1648-1685`）。このソースは CUDA engine と分離された SYCL engine の移植コードです（`engine/sycl/CMakeLists.txt:1-7`）。

## 値と判定

読み取りは `strata::bm_default_on("STRATA_Q6_SHAPE_GRF", device, false)` です。helper は環境値が非空なら先頭文字だけを見て、`'0'` なら false、それ以外なら true を返します。文字列全体の parse、大文字小文字、空白、数値としての妥当性は検査しません。未設定または空文字では `bm_default=false` により GPU 世代にかかわらず false です（`engine/sycl/include/strata/sycl_queue.hpp:196-200`; 呼び出し箇所 `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1656`）。

| 条件 | 未設定 | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| SYCL Q6_K A2 wide、複数列の各 `NCOLS` specialization | false（空文字も同じ） | 空でなく先頭文字が `0` 以外。例: `1`, `true`, `false`, ` 1` | 先頭文字が `0`。例: `0`, `0anything` |

したがって文字列 `false` は有効、`0anything` は無効です。これは値判定の結果であり、後述の GPU・形状・他設定の条件を満たさない場合は kernel 切替に使われません。

## 有効になる条件

- Strata の SYCL backend で Q6_K の `native_q6_k_mmvq` 経路を通る必要があります。packed Q6_K 行列、または planar registry に登録済みの行列は先に処理されるため、この shape guard には進みません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2899,3007-3022,3935-3939`）。
- wide kernel が有効で、列数・行列寸法の wide gate を通る必要があります。`STRATA_MMVQ_WIDE` の `atoi` 結果が 0 なら `g_q6k_wide` が false、列数が `STRATA_MMVQ_WIDE_MAXC` を超える、`n_in` が 256 の倍数でない、または `n_out < wide_min` の場合は対象外です。wide の既定上限は A2 有効時 8 列、A2 無効時 4 列です（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1547,2185,3943-3955`）。
- `STRATA_MMVQ_WIDE_RPW` の値が 1 で、`STRATA_MMVQ_A2` が有効である必要があります。RPW の既定値は 1、A2 は未設定時に有効です。A2 を無効にするか RPW を 2/4 などにすると別の launch 分岐になり、この変数は判定されません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1547,1631-1633,1652-1653,1688-1707`）。
- 列数は 2 以上です。shape 条件は `n_in=6144, n_out=2560`、`n_in=2560, n_out=512 または 640`、`NCOLS>=3` かつ `n_in=2560, n_out=6144`、または `NCOLS>=4` かつ `n_in=2560, n_out=10240 または 12288` です（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1655-1660`）。
- GPU 世代判定が Battlemage である必要があります。`STRATA_INTEL_GEN` が `battlemage` / `alchemist` / `unknown` のいずれかなら検出結果をその値で置き換えます（未設定・空文字なら自動判定）。そのため実機が Battlemage でも `STRATA_INTEL_GEN=alchemist` または `unknown` なら guard は成立しません。Alchemist やその他の世代でも、明示値で helper の `shape_grf` が true になっただけでは成立しません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1661-1663`; override と世代判定 `engine/sycl/include/strata/sycl_queue.hpp:139-191`）。不正な `STRATA_INTEL_GEN` 値は override helper が警告を出して自動判定へ戻ります（同 `:141-150`）。
- `STRATA_MMVQ_LARGE_GRF` が未設定である必要があります。値が空文字でも `getenv` は非 null なので shape guard を抑止します。明示値があれば本変数の guard ではなく、`mmvq_large_grf` がその値を `atoi` で判定します（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1640-1646,1661-1663`）。

## 実行時の詳細

Q6_K MMVQ はまず packed、次に登録済み planar 行列を試し、いずれも処理しない場合に wide gate を評価します。wide launch の `rpw == 1 && q6k_a2()` 分岐に入り、列数が 2 以上なら `shape_grf` を評価します。`shape_grf` は関数 template `launch_q6k_wide<NCOLS>` 内の `static const bool` なので、各列数 specialization で初めてこの分岐に入った時の値と device 判定を cache します。その後の環境変数変更は、同じ specialization では反映されません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1648-1663,3935-3955`）。

`bounded_grf` が true なら 256 GRF property 付きの A2 wide kernel を起動し、それ以外では同じ A2 wide kernel の GRF property なし variant を起動します。明示された `STRATA_MMVQ_LARGE_GRF` が真なら、その変数自身の判定で 256 GRF kernel が選ばれ得ますが、その場合は本変数による bounded guard ではありません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1640-1646,1661-1685`）。

## ログと測定値

shape guard が成立した場合、該当 `launch_q6k_wide<NCOLS>` specialization で初めて分岐したとき stderr に `strata: shape-guarded Q6_K large-GRF dispatch enabled` を出します。これは kernel dispatch のログです。成立しない場合に、本変数専用の無効値警告・fallback 理由・エラーを出すコードはありません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1661-1678`）。

ソースコメントには large-GRF の A770 測定値がありますが、それは Alchemist の wide kernel 全般に関する記述で、本変数の Battlemage shape guard の測定値ではありません。ここでは本変数の性能値として扱いません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1635-1639`）。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:196-200` — helper の空文字・先頭文字・既定値判定。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1640-1685` — large-GRF helper、shape 条件、Battlemage 条件、ログ、256 GRF / 通常 kernel の選択。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3959` — packed / planar の先行処理、wide gate、Q6_K wide 呼び出し条件。
- `engine/sycl/CMakeLists.txt:1-7` — 対象ファイルが CUDA engine と分離された SYCL engine の移植ソースであること。
