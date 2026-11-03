# `STRATA_IQ3XXS_GU_ROW_REUSE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の IQ3_XXS grouped expert gate/up 計算で、連続する 2 行をまとめて計算する row-reuse kernel を選びます。この kernel は各行の重みを別々に処理しつつ、同じ入力 activation の読み込み・展開を 2 行で共有します。設定が無効、または適用条件を満たさない場合は通常の lane kernel へ進みます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4720-4765,4768-4819,4873-4896,5014-5026`）。

## 値と判定

判定は `strata::bm_default_on()` が行います。値が未設定または空文字なら、既定値引数 `true` と GPU 世代判定の結果を使い、Battlemage では有効、それ以外では無効です。空でない値は文字列全体を parse せず、先頭文字だけを見ます。先頭文字が `0` なら無効、それ以外なら有効です（`sycl/include/strata/sycl_queue.hpp:159-166`）。

| 環境変数の値 | helper の判定 | 呼び出し側での結果 |
|---|---|---|
| 未設定 | Battlemage なら有効、それ以外は無効 | Battlemage の条件を満たす場合だけ row-reuse 候補 |
| 空文字 | 未設定と同じ。Battlemage なら有効 | 同上 |
| `0` または `0` で始まる文字列 | 無効 | 通常の lane kernel |
| `1`、`true`、空白で始まる文字列など、`0` 以外で始まる非空文字列 | 有効 | ただし呼び出し側の Battlemage 等の条件も必要 |

数値変換、空白除去、大文字小文字変換、文字列全体の妥当性検査はありません。したがって `false` も helper 上は有効判定です。明示値がある場合も、実際の row-reuse 選択は後述の条件で絞られます。

## 有効になる条件

次の条件をすべて満たす経路で使われます。

- SYCL CUDA-port kernel の `STRATA_GRID_SLM` が 0。1 の場合は `#if !STRATA_GRID_SLM` 節ごとコンパイル対象外となり、この環境変数を読むコードもありません。ソース内の既定値は 0 です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:452-456,4873-4888`）。
- grouped expert の gate/up 型が `18`（IQ3_XXS）で、8 lanes の `launch_gu_port` specialization に入ること。既定 lane 数 `STRATA_EXPERT_LANES` は 8 で、lane 数は `STRATA_GU_LANES` で実行時に選べます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:957-961,4855-4864,4873-4896`）。
- helper の結果が有効で、デバイス世代が Battlemage、旧 kernel (`g_old_kernels`) が無効、multi-entry split (`g_split_multi`) が無効であること（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4873-4888`）。

Battlemage 以外では、環境変数を `1` や別の非ゼロ先頭文字にしても呼び出し側の世代条件を通らず、row-reuse は選択されません。lane 数が 4/16/32 の場合も対象 specialization には入らないため、この変数はそこでは評価されません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4917-4927,4873-4888`）。

関連する `STRATA_EXPERT_ROW_E3` は row-reuse kernel 内の 3-entry tail 処理を制御します。既定では無効で、明示的な非空値が `0` 以外で始まると有効になります。IQ3_XXS ではこの設定が有効だと 3-entry tail 用 kernel variant を使い、その旨を stderr に記録します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4822-4853`）。

## 実行時の詳細

`launch_gu_port<TG, LN>` の `TG=18, LN=8` specialization で helper を最初に評価した結果は `static const bool` に保存されます。同一プロセスで以後環境を書き換えても再評価されません。選択されると stderr に `strata: IQ3_XXS raw two-row GU reuse enabled (8 lanes, SIMD16)` を一度出し、`launch_gu_row_reuse<18>()` を起動して通常の `native_gu_kernel` を迂回します。条件が成立しない場合は通常の `native_gu_kernel<TG,LN,KM>` が起動されます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4873-4896`）。

row-reuse kernel は 64 個の出力 row slot を扱う work-group 内で、各 lane group が `row0` と `row0+32` の 2 行を用意します。各 expert group・各 sub-block について入力 activation の整数表現と scale を一度作り、それぞれの重み行との積を計算して gate または up の出力に書きます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4774-4819,4720-4765`）。

ここに示した有効ログ以外に、この環境変数が無効・条件不成立のとき専用の警告やエラーを出す処理はありません。その場合のコード経路は通常 lane kernel です。カーネル起動後のエラー確認は共通の `check("native_expert_grouped/gu")` を通りますが、この環境変数固有の失敗メッセージや終了動作は確認できません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4876-4896,6126-6135`）。

## 根拠

- 候補一覧には名前があります（`docs/envvars/000_envvers.md:1329`）。実装上の環境読み取りは `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4875` の 1 箇所で、値判定 helper は `sycl/include/strata/sycl_queue.hpp:159-166` です。
- grouped expert dispatch と IQ3_XXS 型の分岐は `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6048-6075,6126-6135` にあります。
- `docs/INTEL.md:518-540` は Battlemage での既定有効と row reuse の対象を説明しています。ここでは速度値を挙げず、実行条件と挙動は対象 commit のコードを根拠にしています。
