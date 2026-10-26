# `QSA_BENCH_DECODE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`qsa_select_bench` を通常の scorer 比較・top-k 比較から、decode window 相当の QSA block-score 計測へ切り替えます。Strata の生成エンジンやサーバーの挙動を変える変数ではありません。CUDA/HIP 向けベンチマーク実行ファイル専用です。

## 値と判定

値の parse はなく、`std::getenv("QSA_BENCH_DECODE")` の結果が null かどうかだけを検査します。

| 状態 | 動作 |
|---|---|
| unset | 通常の比較経路を実行 |
| 任意の値を設定 | decode 用の block-score 計測経路を実行 |

したがって `1` 以外に `0`、`false`、空文字も設定されていれば decode 経路を選びます。大文字小文字、数値変換、値域の検証はありません。判定は `main()` 内で一度行われます。

## 有効になる条件

CUDA では `STRATA_BUILD_TESTS` が有効な場合、HIP では `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が有効な場合に `qsa_select_bench` が CMake のビルド対象として定義されます（`CMakeLists.txt` の CUDA/HIP 条件）。変数を読むのは `src/kernels/qsa_select_bench.cpp` のみで、同ファイルの SYCL コピーにはこの参照がありません。通常の `strata` 実行ファイル、生成処理、サーバーからこの変数を読む参照は確認できません。

## 実行時の詳細

ベンチマークは、コマンドライン引数から context、query 数、反復数、capacity を設定し、合成データを作成した後に変数を判定します。設定時は `qsa_block_scores(..., -1)` を反復実行し、CUDA event の経過時間とスコア配列のハッシュを出力して終了します。この枝では top-k の実行、warp scorer と別 scorer の比較、FP64 参照との精度 gate は行いません。`-1` は `qsa_block_scores` の既定値と同様に active block 数の上限を指定しない値です。

出力形式は `decode scores ctx <context>, <queries> queries: <us> us (<GB/s> GB/s of pooled keys), hash <16桁hex>` です。未設定なら通常経路へ進み、warp scorer と利用可能な別 scorer、および top-k の比較・精度検査を行います。設定後にベンチマークプロセス内で環境変数を変更する処理はありません。

## 根拠

- `src/kernels/qsa_select_bench.cpp:35-42,73-95` — 入力と合成データの準備、設定有無による分岐、decode 用計測、出力、早期終了。
- `src/kernels/qsa_select_bench.cpp:96-119` — unset 時の通常比較経路。
- `include/strata/kernels/qsa_select.hpp:37-40` — `qsa_block_scores` の `active_blocks` 契約。正数の場合だけ起動 block 数を制限する。
- `CMakeLists.txt:501-521` — CUDA/HIP の `qsa_select_bench` ターゲットと有効化条件。
- `sycl/src/kernels/qsa_select_bench.cpp:99-105` — SYCL コピーにある block-score 呼び出し。`QSA_BENCH_DECODE` の読み取りはない。
