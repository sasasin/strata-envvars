# `STRATA_MMVQ_WIDE_RPW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の Q6_K wide MMVQ kernel で、sub-group が一度に担当する出力行数（RPW: rows per warp）を選ぶ。`2` または `4` を指定するとその行数の kernel を選択し、それ以外は `1` 行の kernel になる。値を設定しても wide kernel 自体を有効化するスイッチではなく、Q6_K の出力値を別の形式に変換する処理でもない。読み取りは `q6k_wide_rpw()`、kernel 選択は `launch_q6k_wide()` が行う（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1631-1634,1648-1707`）。

## 値と判定

関数内 `static const int` の初期化で `std::getenv` の有無を見て、設定されていれば `std::atoi` で整数化する。未設定だけが既定値 `1`。空文字は設定ありとして `atoi("")` の結果 `0` になり、未設定時の既定値とは別経路で後段の RPW=1 fallback に入る。文字列全体の妥当性検査、範囲制限、警告はない。`atoi` は先頭の空白と符号を許し、数字列の後ろは変換に使わないため、`2x` は `2`、`0anything` は `0`、`true` は `0` になる。大文字小文字は数値変換に関係しない。`atoi` で `int` に表現できない値の結果は規定されない。

| 条件 | unset | 設定時に有効になる値 | 設定時に RPW=1 へ fallback する値 |
|---|---|---|---|
| SYCL の Q6_K wide kernel に到達 | `1` | 整数化結果 `2` または `4` | `1`、`0`、負値、その他（例: `3`, `5`, `true`, 空文字） |

dispatcher は `rpw == 1`、`rpw == 2`、`rpw == 4` の場合だけ各専用分岐を持ち、いずれにも一致しない値は RPW=1 kernel を起動する。したがって `0` は wide kernel を無効化せず、`2` と `4` 以外の値に比例する行数や clamp はありません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1631-1634,1652-1653,1688-1707`）。

## 有効になる条件

- SYCL build の Q6_K 型（`ggml_type == 14`）が `native_mmvq()` から `native_q6_k_mmvq()` に dispatch されること。CUDA/HIP build はこの SYCL 実装を通らない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4223`、`engine/CMakeLists.txt:23-32`）。
- packed Q6_K または planar 化済み Q6_K の registry hit が先行して返らず、通常の Q6_K dispatch に進むこと（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2899,3007-3035,3935-3939`）。
- wide dispatch が有効であること。`g_q6k_wide` は `STRATA_MMVQ_WIDE` 未設定、または `atoi` 結果が非 0 のとき有効。さらに `1 <= ncols <= wide_maxc`、`n_in % 256 == 0`、`n_out >= wide_min` が必要（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185,3943-3956`）。
- `wide_min` / `wide_maxc` の既定値は `STRATA_MMVQ_A2` の状態で変わる。A2 が未設定または `atoi` 結果が非 0 なら `wide_min=0`, `wide_maxc=8`、A2 が 0 なら `wide_min=4096`, `wide_maxc=4`。この条件を満たさない場合、この変数を読み取る wide kernel には到達しない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548,3943-3945`）。
- `STRATA_MMVQ_WIDE_RPW` 自体に CLI 引数や設定ファイルとの優先順位はない。調査した Strata checkout 内の完全一致参照はこの読み取りと `terminal/data/settings-register.json` の UI 登録だけで、別の値の受け渡しは確認できなかった。

## 実行時の詳細

値は `q6k_wide_rpw()` が最初に呼ばれたときに関数内 `static` として初期化され、以後そのプロセスでは再読み取りされない。通常は Q6_K wide dispatch の初回起動時に読む。実行中に環境を変更しても cached 値には反映されない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1631-1634,1648-1653`）。

値 `2` / `4` は wide kernel のテンプレート行数 `RP` と grid の行分割に渡される。値 `1` または fallback では RPW=1 を選ぶ。RPW=1 かつ A2 が有効な場合は専用の A2 分岐に入り、複数列では `STRATA_Q6_SHAPE_GRF`、`STRATA_MMVQ_LARGE_GRF`、GPU 世代と shape がさらに GRF variant を選ぶ。これらは RPW 値を変更しない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1652-1686,1688-1707`）。

この変数固有のログ出力や無効値エラーはない。kernel 起動時の一般的な SYCL エラー経路はあり得るが、ここではこの変数に応じたメッセージや終了処理は実装されていない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1671-1707`）。

## 根拠

- 値の読み取りと既定値: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1631-1634`
- Q6_K 型への dispatch: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4223`
- packed/planar 先行経路と wide の条件: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2899,3007-3035,3935-3956`
- A2 と RPW ごとの kernel 起動: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548,1652-1707`
- SYCL backend の build 条件: `engine/CMakeLists.txt:23-32`
