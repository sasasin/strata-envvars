# `STRATA_BENCH_PLANAR`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `mmvq_bench` に、Q6_K 行列の planar layout と row gather の追加比較・bitwise 検査を実行させます。Strata エンジンの動作を切り替える環境変数ではなく、このベンチマーク実行ファイルだけが読み取ります。通常の GGUF layout の測定と checksum 出力の後に判定されます。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 追加処理をしない。通常の `mmvq_bench` を実行して終了コード 0。 |
| 空文字、数値に変換できない文字列、`0`、`0` で始まる数値（例: `0abc`） | `std::atoi()` が 0 を返すため追加処理をしない。 |
| `1`、`2`、`-1`、`1suffix` など、`std::atoi()` の結果が 0 以外になる文字列 | planar layout と gather の比較を実行する。 |

値は文字列全体として比較されず、`std::atoi()` で整数に変換した結果が 0 かどうかだけを見ます。したがって、先頭空白や符号の後の数字が変換対象になり、数字以降の文字は無視されます。数字を含まない文字列は 0 です。数値としての境界外入力についてコードは検証していません。

## 有効になる条件

- `mmvq_bench` は SYCL サブプロジェクトの実行ファイルです。`sycl/CMakeLists.txt` では `STRATA_SYCL_PARITY` が有効なブロック内で定義され、同オプションの既定値は `ON` です。SYCL ベンチマークをビルドして実行できる環境が必要です。
- 追加処理は `STRATA_BENCH_PLANAR` の変換結果が 0 以外の場合だけ行います。`STRATA_Q6_PLANAR` も別途参照され、値がちょうど文字列 `0` のときは planar 化を無効にします。この組み合わせでは benchmark 側の `adopt` が元の行列を返し、ベンチマークは `planar: adopt declined` を出して終了コード 1 になります。
- `n_in` が正で 256 の倍数、`n_out` が正であることも planar 化の条件です。既定の `n_in=2560`, `n_out=2560` は条件を満たします。引数はコマンドラインから与えられ、環境変数ではありません。
- planar copy の確保や変換、row gather が失敗した場合も、通常の比較完了とは異なる出力または終了コード 1 になります。

## 実行時の詳細

ベンチマークはまずランダムな Q6_K データと入力を作り、GGUF layout の kernel を測定して checksum を表示します。その後 `STRATA_BENCH_PLANAR` を読みます。有効なら重複行列をデバイスにコピーし、`native_q6_k_planar_adopt()` で planar layout に変換して kernel を実行します。最初の結果を通常 layout の結果と `memcmp()` で比較し、`bitwise EQUAL` または `bitwise DIFFERENT` を出力します。続いて出力行の約 3 分の 1（最低 1 行）を gather し、全列の出力を元の行列の対応行と比較して差分数を表示します。

planar の結果に差がある場合、または gather 結果に差がある場合は終了コード 1 です。両方一致すれば 0 です。環境変数はベンチマークの `main()` 内で一度読み、static cache はありません。実行中に環境を変更して再評価する処理もありません。

## 根拠

- `sycl/src/kernels/mmvq_bench.cpp:1-2,13-27`: 対象実行ファイル、既定引数、合成入力および Q6_K 行列の準備。
- `sycl/src/kernels/mmvq_bench.cpp:29-55`: 通常 layout の比較、測定、checksum 出力。
- `sycl/src/kernels/mmvq_bench.cpp:56-97`: 変数の唯一の読み取り箇所、`atoi` 判定、planar adopt、bitwise 比較、gather 比較、戻り値。
- `sycl/CMakeLists.txt:278-281,387-390`: `STRATA_SYCL_PARITY` の既定値と `mmvq_bench` の定義位置。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3062-3068,3072-3114,3117-3151`: `STRATA_Q6_PLANAR` の判定、planar adopt/gather の適格条件と失敗時の挙動。
- `docs/INTEL.md:393,480-482`: `STRATA_Q6_PLANAR` の概要と Q6_K decode kernel の測定記録。これらは `STRATA_BENCH_PLANAR` 自体の効果測定ではなく、ベンチマーク環境での性能を保証するものではありません。
