# `STRATA_Q36_BLAS_F32`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 (`qwen35moe`) エンジンで、8 行を超えるバッチの F32 行列積を計算するとき、入力幅 `n_in` が 4 の倍数でも、Strata の分割 K GPU kernel ではなく `cublasSgemm` を選ばせる設定です。対象は GDN の alpha / beta、expert router、shared-expert gate の F32 積です。未設定時も `n_in` が 4 の倍数でなければ同じ SGEMM 経路を使います。短いバッチ (`T <= 8`) の計算方法は変わりません。`engine/src/qwen35/q36_engine.cu:2361-2394, 2726-2732, 2895-2901, 3013-3018`

このエンジンは CUDA / HIP 用にビルドされ、`strata` が `qwen35moe` モデルを選んだ経路と、同じエンジンを包む `strata-q36` で使われます。HIP gfx906 では Qwen3.6 エンジン自体をビルドしません。SYCL の経路にはこの実装がありません。`engine/cmake/strata_gpu_engine.cmake:565-583`, `engine/src/program/generate.cpp:3804-3818`

## 値と判定

値の内容は parse されません。`std::getenv(...) != nullptr` の有無だけを一度判定し、設定されていれば有効です。したがって空文字、`0`、`false`、大文字小文字違い、空白や任意の文字列もすべて「設定あり」です。未設定だけが「設定なし」です。`engine/src/qwen35/q36_engine.cu:2368-2369`

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Qwen3.6 CUDA / HIP エンジンで `T > 8` | `n_in % 4 == 0` なら分割 K kernel、それ以外は SGEMM | 空文字、`0`、`false`、`1`、その他の任意の値 | なし（値の妥当性検査なし） |
| 同エンジンで `T <= 8` | `k_gemv_f32` | なし。この条件では環境変数を読む分岐に入らない | なし |

`T > 8` で変数が未設定かつ `n_in % 4 == 0` の場合、`n_out` と `T` から分割数を決め、`k_sgemm_nt` と必要に応じ `k_sum_splits` を使います。変数が設定されている場合、または `n_in` が 4 の倍数でない場合は `cublasSgemm` に進みます。`engine/src/qwen35/q36_engine.cu:2368-2389`

## 有効になる条件

- `qwen35moe` 用エンジンがビルドされていること。`strata` では `STRATA_HAVE_QWEN35` が定義されたビルドでモデルの architecture によりエンジンへ分岐し、`strata-q36` は同じエンジンライブラリをリンクします。`engine/cmake/strata_gpu_engine.cmake:570-583`, `engine/src/program/generate.cpp:3804-3818`
- HIP gfx906 は対象外です。CMake がそのビルドでは `strata_qwen35` を追加しません。`engine/cmake/strata_gpu_engine.cmake:567-571`
- 実際の `f32mm` 呼び出しで `T > 8` であること。8 以下の行数では `k_gemv_f32` で戻るため、変数の値は使いません。プロンプトは `process` が `tmax` ごとのチャンクに分けて `forward` を呼びます。`--chunk` / `--prefill` と `STRATA_Q36_CHUNK` はチャンク幅を決める別設定であり、このフラグを直接上書きしません。`engine/src/qwen35/q36_engine.cu:2363-2369, 2392-2397, 5363, 5517-5522, 3720-3728`
- CLI 引数による `STRATA_Q36_BLAS_F32` の上書きや、子プロセスへの転送処理はこのエンジンの参照箇所にはありません。`rg` による名前の全参照では、実行時の読み取りは `engine/src/qwen35/q36_engine.cu:2368` のみです。

## 実行時の詳細

`f32mm` は `T <= 8` なら即座に `k_gemv_f32` を投入します。`T > 8` になった呼び出しで初めて関数内 `static const` が評価され、環境変数の設定有無をキャッシュします。そのためプロセス起動後に環境を変更しても、最初の該当呼び出し後は反映されません。該当呼び出しが一度もなければ、この変数は読まれません。`engine/src/qwen35/q36_engine.cu:2363-2369`

SGEMM 経路は `cublasSgemm` を呼び、戻り値が `CUBLAS_STATUS_SUCCESS` 以外なら stderr に `strata-q36: cublasSgemm failed` を出して `exit(1)` します。`engine/src/qwen35/q36_engine.cu:2384-2389`。分割 K 経路では `k_sgemm_nt` を起動し、複数 split の場合は部分結果を `k_sum_splits` で合算します。`engine/src/qwen35/q36_engine.cu:2369-2382`

コードから確認できるのはこの計算経路の切り替えまでです。経路ごとの性能差や出力の一致性を示す測定値は、対象変数について `docs/DETAILS.md` および `docs/QWEN36.md` に見つかりませんでした。

## ログと測定値

成功時にこの環境変数専用のログはありません。SGEMM が失敗した場合は `strata-q36: cublasSgemm failed` を stderr に出し、終了コード 1 で終了します。上記の通り、対象変数について記載可能な Strata の測定値は確認できませんでした。`engine/src/qwen35/q36_engine.cu:2384-2389`

## 根拠

- `engine/src/qwen35/q36_engine.cu:2361-2394` — F32 行列積の分岐、設定有無判定、分割 K kernel、SGEMM と失敗経路、8 行の境界。
- `engine/src/qwen35/q36_engine.cu:2726-2732, 2895-2901, 3013-3018` — この関数を呼ぶ GDN alpha / beta、router、shared-expert gate。
- `engine/src/qwen35/q36_engine.cu:3720-3728, 5363, 5517-5522` — prompt chunk 処理と別の chunk 設定。
- `engine/cmake/strata_gpu_engine.cmake:565-583`, `engine/src/program/generate.cpp:3804-3818` — CUDA / HIP エンジンの組み込み、gfx906 除外、Qwen3.6 family switch。
