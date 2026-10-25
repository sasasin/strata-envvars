# `STRATA_MMVQ_WIDE_K_RPW`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 native MMVQ の wide Q4_K / Q5_K / IQ4_XS kernel で、sub-group が同時に処理する出力行数（rows per sub-group、RPW）を選びます。RPW 2 または 4 では、1列分の Q8_1 activation を複数行の計算で共有する kernel を使います。既定値および未対応値では従来の1行 kernel を使います。これはソース内にある SYCL 実装の設定で、CUDA/HIP の同名設定としては確認できませんでした。

## 値と判定

`std::atoi` で変換した整数を使い、結果がちょうど `2` または `4` の場合に限り対応する RPW kernel を選びます。それ以外の値では RPW 1 の kernel にフォールバックします。

| 環境変数 | `atoi` の結果 | 選択 |
|---|---:|---|
| 未設定 | 既定値 `1` | RPW 1 |
| 空文字 | `0` | RPW 1 |
| `2`、`2xyz`、先頭空白付きの ` 2` | `2` | RPW 2 |
| `4`、`4xyz` | `4` | RPW 4 |
| `1`、`0`、負値、`3`、数値で始まらない文字列 | `2` と `4` 以外 | RPW 1 |

文字列全体の妥当性検査はなく、`atoi` が先頭から変換できる数値部分だけを使います。したがって `2xyz` は RPW 2 になります。大きすぎて `atoi` で表現できない入力の結果は C/C++ の `atoi` の範囲外入力に依存するため、ここでは特定の値を保証できません。

## 有効になる条件

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にある SYCL 実装がビルドされ、Q4_K、Q5_K、または IQ4_XS の native MMVQ 経路が呼ばれること。
- 親設定 `STRATA_MMVQ_WIDE_K` が有効であること。これは未設定なら有効、設定時は `atoi` の結果が 0 以外なら有効です。無効なら `try_wide()` が wide kernel を使わず、この変数は参照されません。
- `try_wide()` が受け付ける形状であること: `ncols` は 1〜8、`n_in` は QK の倍数である必要があります。ソースのこれらの関数では QK は 256 です。条件外なら既存の別 kernel 経路に進みます。

RPW 2/4 を選んでも、異なる GPU/backend における性能や出力差の測定結果はこの調査対象のソースや関連資料では確認できませんでした。実装コメントは出力が1行 kernel と同じ bit pattern になる設計意図を述べていますが、環境変数の説明として性能や正確性を独立に保証する測定資料は見つかりませんでした。

## 実行時の詳細

`wide_k_rpw()` は `std::getenv("STRATA_MMVQ_WIDE_K_RPW")` が null なら 1、設定されていれば `std::atoi` の値を返します。結果は関数内の `static const int` に保存されるため、`launch_wide()` が最初に呼ばれた時点で一度だけ読み取られます。その後プロセス内で環境を変更しても、この選択は再評価されません。

`launch_wide()` は値が 2 または 4 ならテンプレート化された `native_mmvq_wide_rpw_kernel<F, NCOLS, RP>` を起動し、必要な出力行数に応じて grid を計算します。それ以外は `native_mmvq_wide_kernel<F, NCOLS>` を起動します。RPW kernel は各列の activation を一度ロードして RPW 行で共有し、各行の出力を所定位置へ書き込みます。環境変数によるログ出力やエラー処理はありません。

適用先は `native_q4_k_mmvq`、`native_q5_k_mmvq`、`native_iq4_xs_mmvq` からの `try_wide()` 呼び出しです。他の GGML type にはこの設定が適用されません。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1920-1923` — 環境変数の読み取り、既定値 1、static cache。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1881-1918` — RPW kernel と activation を行間で共有する処理。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1950-1965` — 2/4 の選択と、それ以外の RPW 1 fallback。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1966-1984` — 親の wide 経路の既定有効判定、形状条件、1〜8列の dispatch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3132-3145,3355-3367,3446-3459,3781-3798` — Q5_K、IQ4_XS、Q4_K の呼び出しと GGML type dispatch。
- `docs/INTEL.md:481` — `STRATA_MMVQ_WIDE_K=0` で旧 multi path にする説明。`STRATA_MMVQ_WIDE_K_RPW` 固有の説明や測定値は確認できませんでした。
