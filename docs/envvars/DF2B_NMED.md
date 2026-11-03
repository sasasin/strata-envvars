# `DF2B_NMED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の補助ベンチマーク `dflash2_bench gemm` が、GEMM ベンチマークを始める前に追加する中サイズの device allocation 数を指定します。1 件ごとに 8 MiB を確保し、その領域を `1` で埋める memset をコマンドキューに入れます。通常の Strata エンジンや一般のモデル実行が読む設定ではありません。

この実行ファイルは `sycl/CMakeLists.txt` の `dflash2_bench` target として定義されています（`sycl/CMakeLists.txt:437-438`）。環境変数の読み取り箇所は `sycl/src/kernels/dflash2_bench.cpp:619` の 1 箇所です。

## 値と判定

共通 helper `envi(k, d)` は `std::getenv(k)` を呼び、未設定または空文字なら既定値 `d`、それ以外なら `std::atoi` の結果を返します（`sycl/src/kernels/dflash2_bench.cpp:56`）。この変数では既定値は `0` です。

| 設定 | helper の結果 | 動作 |
| --- | ---: | --- |
| 未設定 | 0 | allocation しない |
| 空文字 | 0 | allocation しない |
| `0`、数値変換結果が 0 の文字列 | 0 | allocation しない |
| 正の整数 `N` | `N` | 8 MiB allocation と memset を `N` 回投入 |
| 負の整数 | 負値 | `i = 0; i < N` の条件が成立せず、allocation しない |

文字列全体の検証や範囲チェックはありません。`atoi` が先頭から変換できる整数部分を使うため、例えば `3tail` は 3、先頭に空白と符号がある ` +3` も 3 になります。先頭が整数として変換できない文字列は 0 になります。整数型の範囲外の入力について、コードはエラー処理を定義していません。

## 有効になる条件

- `dflash2_bench` を `gemm` 引数で起動した場合だけ読み取られます。引数なし、または `gemm` 以外の未認識引数は `run_bench()` 等へ進み、この変数を読みません（`sycl/src/kernels/dflash2_bench.cpp:894-901`）。
- `test`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` の各モードでは、この変数による allocation はありません（同 `:900-901`）。
- 対象は SYCL 側の補助ベンチマークです。CMake では `dflash2_bench` が別 executable として定義されており、環境変数を Strata の通常の CLI やサーバー設定へ転送する処理は確認できません（`sycl/CMakeLists.txt:437-438`）。

## 実行時の詳細

`main()` は SYCL GPU queue を作成した後に引数から実行モードを選びます。`gemm` の場合、`run_gemm_bench()` は準備処理として `DF2B_HOSTALLOC`、`DF2B_BIGALLOC_MB`、`DF2B_NALLOC` に続き `DF2B_NMED` を評価します（`sycl/src/kernels/dflash2_bench.cpp:894-901,614-620`）。

ループの各判定で helper が呼ばれるため、値は static cache されません。各 helper 呼び出しで `getenv` と `atoi` が行われます。正値 `N` なら各回で `sycl::malloc_device(8 << 20, *Q)` を呼び、返された pointer を `Q->memset(mp, 1, 8 << 20)` に渡します。個別 memset の完了待ちはせず、ループ終了後の `Q->wait()` でキューを待ちます（同 `:619-620`）。この変数専用のログはありません。処理が進めば device 名と GEMM の timing 表を出力します（同 `:631-639`）。

この箇所では allocation pointer の null 検査や専用のエラーメッセージはありません。明示的なメモリ不足メッセージと終了コード 2 は同ファイルの `dev()` helper にありますが、このループは `dev()` を通らず直接 `sycl::malloc_device` を呼ぶため、その経路は適用されません（同 `:62,619`）。それ以上の allocation / queue 失敗時の結果は、このコードだけからは特定できません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — 未設定・空文字の既定値処理と `atoi` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:614-620,631-639` — `gemm` ベンチ準備中の反復 allocation、memset、queue wait と、その後の device / timing 出力。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — queue 初期化と CLI モードの振り分け。
- `sycl/src/kernels/dflash2_bench.cpp:62` — `dev()` にある別経路の明示的 OOM 処理との違い。
- `sycl/CMakeLists.txt:437-438` — `dflash2_bench` executable の定義。
