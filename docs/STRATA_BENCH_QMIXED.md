# `STRATA_BENCH_QMIXED`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`fused_gr_bench` の cold-set 計測で、各 `mixed` 出力に Q8_1 形式の画像も書き込む計測を有効にします。環境変数を読むのは同梱ベンチマークだけで、`strata` エンジンの動作を切り替える設定ではありません。CMake では `STRATA_BUILD_TESTS` のブロック内にこのベンチマークターゲットがあります。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `with_q` は `false`。Q8_1 画像用ポインターを引数に設定しない |
| 設定あり | `with_q` は `true`。値の内容にかかわらず Q8_1 画像とカウンターのポインターを設定する |

実装は `std::getenv(...) != nullptr` だけで判定し、文字列を parse しません。したがって空文字、`0`、`false` を含め、環境に変数が存在すれば有効です。判定結果は `cold_sets > 1` の分岐内でベンチマーク実行時に一度ローカル変数へ読み込みます。プロセス起動後に環境を書き換える経路はありません。

## 有効になる条件

- `fused_gr_bench` がビルドされていること。CMake では `STRATA_BUILD_TESTS` が有効なときにターゲットを追加します。
- cold-set 部分を実行するため、コマンドライン第4引数の `cold sets` が 1 より大きいこと。未指定時は 0 です。これ以外の実行経路では環境変数を読みません。
- `fused_gr_bench` は CUDA runtime を使うソースです。HIP/SYCL 向けの本番設定として扱う根拠はありません。

## 実行時の詳細

cold-set 部分では、環境変数が設定されている場合、各 token の `FusedGrArgs` に `q8_mixed` と `q8_cnt` を設定してから `fused_gr_read_multi()` を呼びます。未設定ならこれらのポインターは初期化状態の null のままです。API は全 token の出力先と token 0 のカウンターがそろった場合にのみ Q8_1 出力を有効にします。対応する CUDA kernel は `mixed` の 32 要素グループから scale / sum と int8 値を Q8_1 画像へ書き込みます。

この差は cold-set 時間と stage stamp の計測対象にも含まれます。つまり変数を設定した計測値は、Q8_1 画像生成を含む cold read の値です。通常の「画像なし」計測値と同じ処理量として比較することはできません。ベンチマークは結果を `COLD(...)` の行に出力します。この環境変数自体について `docs/DETAILS.md` に説明や測定値は見つかりませんでした。

## 根拠

- `CMakeLists.txt:256,1013-1015` — テストビルド内で `fused_gr_bench` を定義。
- `src/kernels/fused_gr_bench.cpp:4-6,57-62` — 引数と `cold sets` の既定値。
- `src/kernels/fused_gr_bench.cpp:208-225,229-267` — cold-set 分岐、環境変数の存在判定、引数設定、計測。
- `include/strata/kernels/fused_gr.hpp:44-47,64-71` — Q8_1 出力ポインターと複数 token API。
- `src/kernels/cuda/fused_gr.cu:218-251,2210-2215` — Q8_1 画像の書き込みと、ポインターの成立条件。
