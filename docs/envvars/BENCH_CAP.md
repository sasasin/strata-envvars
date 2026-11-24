# `BENCH_CAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA/HIP ビルドに含まれる診断用 `native_expert_bench` の通常実行経路で、grouped expert kernel に渡すグループ上限 `CAP` を指定する。実在するグループ数 `G` は CLI の第 3 引数で決まり、環境変数で `G` を減らすことはできない。`BENCH_CAP` を `G` より大きくすると、存在しないグループ行も含む launch 上限と、それに合わせた scratch 領域が大きくなる。通常の `strata` エンジン、サーバー、他の実行モードの設定ではない。通常経路の `main` は `--nibble` を先に別関数へ振り分け、通常 bench の CMake target は CUDA または HIP が有効で `ggml-cpu` target がある場合にのみ作られる（`engine/src/kernels/native_expert_bench.cpp:45-50,101-116,139-142`; `engine/CMakeLists.txt:771-780`）。

## 値と判定

通常 bench は各 layer の tensor と形式を確認した後、`getenv("BENCH_CAP")` の null 判定を行い、設定されていれば `std::atoi` の結果を使う。変数が未設定なら `CAP=G`、設定されていれば `CAP=max(G, atoi(value))`。したがって空文字も設定済みとして `atoi("") == 0` になり、正の `G` により `CAP=G` となる。`atoi` は数値全体の厳密な検証ではなく、先頭の空白と符号を許し、先頭の整数部分を読む。数字に続く文字は無視され、先頭から数値に変換できない文字列は 0 になる。追加の空白・文字検査やエラー報告はない。`G` は先に `G >= 1` と検証されるため、0、負数、および `G` より小さい値は上限を下げない。`int` の表現範囲を超える入力について、このコードに明示的な処理はない（`engine/src/kernels/native_expert_bench.cpp:59-62,101-103`）。

| 条件 | unset | 有効になる値（例） | 無効・上限に影響しない値（例） |
|---|---|---|---|
| 通常 bench 経路 | `CAP=G` | `G` より大きい整数。例: `G=18`, `BENCH_CAP=28` なら `CAP=28` | 空文字、`0`、`-1`、`17`、`0anything`、`true` はいずれも変換値が 0 または `G` 以下なので `CAP=G`。`18tail` は `atoi` が 18 を読むため `CAP=G`。 |

`CAP` と別に、scratch と kernel の entry 上限 `CAPE=max(NE,CAP)` が計算される。ここで `NE=G*T`（`T` は CLI の token 数）なので、`BENCH_CAP` が `NE` 未満でも scratch 上限は少なくとも `NE` となる（`engine/src/kernels/native_expert_bench.cpp:59-62,101-115`）。

## 有効になる条件

- `native_expert_bench` を CUDA または HIP backend でビルドし、`ggml-cpu` target があること。通常のアプリケーション用実行ファイルを起動しても、この環境変数を読む箇所は確認できない（`engine/CMakeLists.txt:771-780`）。
- CLI の通常形式で起動すること。`--nibble` は `main` 冒頭で `nibble_main` に分岐するため、この変数を読む通常経路に入らない（`engine/src/kernels/native_expert_bench.cpp:45-50,101-103`）。
- 引数数、`T`（1〜8）、`G`（1 以上）が検証を通り、対象 layer に expert tensor があり、native format 判定が成功して、該当 layer の上限計算まで到達すること。失敗・対象外の layer は先に処理を抜ける（`engine/src/kernels/native_expert_bench.cpp:48-62,70-85,101-103`）。
- 同名の SYCL bench は別ソースで、`native_expert_grouped` に CLI 由来の `G` と `NE` を渡し、`BENCH_CAP` を読まない。この設定値は SYCL 版には適用されない（`engine/sycl/src/kernels/native_expert_bench.cpp:106-116,140-143`）。

## 実行時の詳細

`G` 個の実データと `NE=G*T` 個の entry 配列は CLI から作られる。`CAP` は `native_expert_grouped` の `cap_groups`、`CAPE` は `cap_entries` と scratch 確保量に使われる。scratch サイズは `native_expert_scratch_bytes(CAPE, FF)` で計算され、kernel は `cap_groups` に基づく grid を構成する。API コメントは `grid_groups` の範囲が `1..cap_groups` であること、グループ数は device 上の count から読むこと、結果は `grid_groups` に依存しないことを記している。したがってこの値は計測時に可能グループ数を大きく見積もるためのもので、実グループ数、token 数、入力データを増やす指定ではない（`engine/src/kernels/native_expert_bench.cpp:101-141`; `engine/include/strata/kernels/iq_kernels.hpp:79-88`; `engine/src/kernels/cuda/iq_kernels.cu:5877-5879,7085-7102,7184-7195`）。

環境値は関数内 static cache ではなく、layer ごとの計算時に参照される。同じ計算式内で `getenv` を2回呼び、1回目は設定有無、2回目は `atoi` の入力取得に使う。bench が実行中に環境を書き換える処理はありません。CLI の `G` は下限として優先され、`BENCH_CAP` は上限を引き上げる場合にだけ効く。より大きな値に対する clamp はなく、`CAP` に応じて scratch 確保も増える（`engine/src/kernels/native_expert_bench.cpp:101-116,139-142`）。

## ログと測定値

`BENCH_CAP` 固有の有効・無効ログ、警告、エラー文言はありません。通常 bench の起動引数不足や `G`/`T` の範囲外は stderr に usage または `tokens 1..8, groups >= 1` を出して終了コード 2 となるが、これは環境変数の値検査ではなく CLI 検証です（`engine/src/kernels/native_expert_bench.cpp:48-62`）。CUDA stream 同期失敗時は `layer %d: CUDA error` を stdout に出して終了コード 1。なお、この通常経路の `cudaMalloc` 戻り値は個別に検査していないため、`BENCH_CAP` を過大にした場合の確定した診断文言や終了経路はこの箇所からは保証できない（`engine/src/kernels/native_expert_bench.cpp:107-121,143-150`）。

## 根拠

- `engine/src/kernels/native_expert_bench.cpp:45-62` — `--nibble` 分岐、CLI 引数、`G`/`T` の検証。
- `engine/src/kernels/native_expert_bench.cpp:70-115` — layer 前処理、`BENCH_CAP` の読み取り・変換、`CAP`/`CAPE` と scratch 確保。
- `engine/src/kernels/native_expert_bench.cpp:139-150` — 計算した上限の kernel 呼び出し、同期エラー。
- `engine/CMakeLists.txt:771-780` — CUDA/HIP と `ggml-cpu` 条件での bench target。
- `engine/sycl/src/kernels/native_expert_bench.cpp:106-116,140-143` — SYCL 実装に環境変数読み取りがないこと。
- `engine/include/strata/kernels/iq_kernels.hpp:79-88`; `engine/src/kernels/cuda/iq_kernels.cu:5877-5879,7085-7102,7184-7195` — kernel API の上限・scratch と launch の扱い。
