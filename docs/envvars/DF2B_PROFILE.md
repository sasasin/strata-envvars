# `DF2B_PROFILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の開発・診断用実行ファイル `dflash2_bench` の既定ベンチ経路で、DFlash2 の各 kernel launch の後ろに SYCL event marker を挿入し、kernel ごとの経過時間を標準出力へ表示します。Strata エンジンの生成処理やサーバーの設定には使われません。対象コード内の説明も「direct launches only」としています（`sycl/src/kernels/dflash2_bench.cpp:1-9,573-600`）。

## 値と判定

`envi("DF2B_PROFILE", 1)` は共通 helper を通じて値を読み、未設定または空文字なら既定値 `1` を返します。非空値は `std::atoi` で整数に変換し、その結果が 0 以外ならプロファイル処理を有効にします（`sycl/src/kernels/dflash2_bench.cpp:56,574`）。

| 環境値 | 判定結果 | 動作 |
|---|---:|---|
| 未設定 | 既定値 `1` | 有効 |
| 空文字 | 既定値 `1` | 有効 |
| `0`、または `atoi` が 0 を返す非数値（例: `true`） | 0 | 無効 |
| `1`、負数、または整数として 0 以外に変換される文字列 | 0 以外 | 有効 |

`atoi` は文字列全体の厳密な検証ではありません。先頭の空白や符号を含む整数を変換し、数値の後ろの文字は検査しません（例: `1tail` は 1）。有効範囲チェックや無効値の警告・エラー処理はありません。整数型の範囲を超える入力について、コードは独自の扱いを定めていません（`sycl/src/kernels/dflash2_bench.cpp:56`）。

## 有効になる条件

- `dflash2_bench` がビルドされており、実行時に `run_bench()` 経路へ入る必要があります。CMake はこの実行ファイルを `STRATA_SYCL_PARITY` が有効な場合に追加します。同 option の既定値は `ON` です（`sycl/CMakeLists.txt:288-291,437-438`）。
- コマンドライン引数が `test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` のいずれかなら別の関数へ分岐し、`DF2B_PROFILE` の判定箇所には到達しません。引数なし、`bench`、または上記以外の値では `run_bench()` が選ばれます（`sycl/src/kernels/dflash2_bench.cpp:894-901`）。
- `main()` は SYCL GPU selector で queue を作成し、queue profiling を有効にしています。したがってこの設定は同ベンチの SYCL GPU 実行経路に限られ、CUDA/HIP のエンジン実行には適用されません（`sycl/src/kernels/dflash2_bench.cpp:894-899`）。
- `run_bench()` に入ったとき `DF2B_PROFILE` を一度評価します。プロセス内の static cache はなく、値が有効なら通常の直接 launch 計測を終えた後、20 回の追加 round のうち最初の 3 回を集計対象から外し、残り 17 回の event 時刻を集計します。別の `DF2B_GRAPH` 設定が graph replay を有効にしても、プロファイル対象は graph replay ではなく直接 launch の round です（`sycl/src/kernels/dflash2_bench.cpp:525-574,577-600`）。

## 実行時の詳細

有効時は `D.profile` を `true` にし、`D.stamp()` が launch ごとに空の `single_task` event を追加します。`DO` macro は各 kernel 呼び出しの後で stamp するため、連続する marker の `command_end` 時刻の差を各 kernel の値として集計します。コメントと出力文言どおり、この差には kernel launch 間の gap も含まれます（`sycl/src/kernels/dflash2_bench.cpp:101-104,209-219,573-600`）。

標準出力には合計の round あたり平均と対象 round 数を含む `PROFILE (marker after every launch, so each includes its launch gap; ms per round, sum ... over ... rounds):`、続けて kernel 名ごとの平均ミリ秒を大きい順に表示します。無効の場合、この追加 profile loop と `PROFILE` 出力をスキップします。環境値の parse 失敗を示すログはありません（`sycl/src/kernels/dflash2_bench.cpp:574-600`）。

event profiling の読み出しには明示的な例外捕捉がありません。このため、仮に SYCL profiling 情報取得が例外を投げる場合の個別ログや fallback は実装されていません。queue 自体は `enable_profiling()` 付きで構築されます（`sycl/src/kernels/dflash2_bench.cpp:587-590,894-899`）。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56,574-600` — 環境値の変換、profile loop、集計と標準出力。
- `sycl/src/kernels/dflash2_bench.cpp:101-104,209-219` — marker の追加位置と各 launch 後の stamp。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — GPU queue、profiling property、CLI mode の分岐。
- `sycl/CMakeLists.txt:288-291,437-438` — parity option の下での `dflash2_bench` target 定義。
