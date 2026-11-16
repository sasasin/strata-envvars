# `STRATA_PRIVATE_GU_GRID64`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の Battlemage 向け grouped expert gate/up（GU）計算で、IQ2_S (`L.gu_type == 22`) の専用 Grid64 カーネルを選ぶ private opt-in です。有効条件を満たすと `launch_grid64<false, GuGrid64Kernel>` を呼び、条件を満たさない場合や値が無効な場合は通常の `launch_gu` 分岐へ進みます。down projection をこの変数で切り替える分岐はありません。読み取りは `grid64_enabled()` のみです（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4816, 7408-7415`）。

## 値と判定

`std::getenv` で値を取得し、先頭 1 文字が `'1'` かだけを判定します。文字列全体の解析、数値変換、空白除去、大文字小文字変換はありません。未設定・空文字は無効です。`1`、`10`、`1anything` は有効で、`0`、`true`、` 1`、`01` は無効です。数値範囲や負値の境界はありません。関数内 `static const bool` に保存され、初回評価後に環境を変更しても同じプロセスでは再評価されません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4816`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL 実装で `grid64_enabled()` を評価 | `false` | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `01` |

## 有効になる条件

- SYCL の `native_expert_grouped` 経路であること。この分岐は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にある SYCL 実装です。
- `L.gu_type == 22`、`L.n_embd == 2560`、`L.n_ff == 640` であること。
- `v1`、`g_old_kernels`、`g_split_multi` がすべて false、`gu_lanes() == 8`、`grid_groups == 0`、`cap_groups == cap_entries` であること。
- `ps_enabled(device)` が true であること。これは `STRATA_PRIVATE_PACKED_REGISTER` の先頭文字が `'1'` であり、現在の呼び出しが B60 main actor で、重みが packed 状態、かつ GPU 世代判定が Battlemage の場合に true です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`）。
- 同じ GU 型に対する先行分岐が先に成立しないこと。特に `STRATA_PRIVATE_GU_GRID_S4` が有効でその分岐条件を満たす場合は Grid S4 が選ばれます。また `STRATA_PRIVATE_B60_NEXT_POOL` の分岐が成立する場合も Grid64 分岐より先に処理されます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7393-7411, 4913`）。
- `g_old_kernels` または `g_split_multi` が true の経路では、この専用分岐は通りません。各値は `STRATA_OLD_IQ_MMVQ` / `STRATA_EXPERT_SPLIT` が未設定・空文字でなく、先頭文字が `'0'` 以外なら true です。したがって `1` だけでなく `true` や `01` も true になり、`0...` は false です（同ファイル `3689-3699, 7408-7411`）。

これらの条件を満たさない場合、変数が有効値でもこの分岐は選ばれず、同じ GU 処理の通常形式・他の該当専用分岐へ進みます。値や条件不足を知らせる変数固有の警告はありません。

## 実行時の詳細

`native_expert_grouped` が GU カーネルを選択するときに条件を評価します。`grid64_enabled()` の `static` 初期化は、実際に同関数が呼ばれ、先行する GU 分岐を通過して条件式の評価に到達した時点で一度だけ行われます。その初回評価後の環境変更は反映されません。条件がすべて成立すると `launch_grid64<false, GuGrid64Kernel>` が `queue->parallel_for` を実行します。それ以外では後続の `switch (L.gu_type)` から `launch_gu` が呼ばれます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4816, 4890-4911, 7388-7417`）。

この変数による CLI 引数との優先順位、プロセス間の転送、待ち時間や timeout は実装にありません。SYCL 用のこの分岐に CUDA/HIP 向けの別の読み取り箇所もありません。

## ログと測定値

この変数の値、選択された Grid64 カーネル、条件不足を報告する専用ログはありません。GU 分岐の後には一般的な `check("native_expert_grouped/gu")` が実行されますが、変数固有の出力ではありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7417-7422`）。対象変数について性能測定値を示す記述は確認できませんでした。`docs/DETAILS.md` に本変数の説明はありません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4816` — 環境変数の唯一の読み取り、先頭文字判定、関数内 static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469` — packed-register opt-in、B60 main actor、packed weights、Battlemage の条件。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7308-7337` — grouped expert 処理の入口と `grid_groups` の扱い。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7417` — 専用 GU 分岐の前提・先行分岐・Grid64 呼び出し・fallback。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4890-4911` — Grid64 launch が実行する処理。
