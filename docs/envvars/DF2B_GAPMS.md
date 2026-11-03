# `DF2B_GAPMS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の独立した `dflash2_bench` の `bench` 経路で、計測周回に入る前にホスト側の待ち時間を挿入します。通常の Strata エンジンやサーバーの推論経路では読み取られません。実装はベンチ周回ごとに SYCL queue の処理完了を待ってから、指定ミリ秒だけホストスレッドを sleep させます。

## 値と判定

`run_bench()` の開始時に `envd("DF2B_GAPMS", 0.0)` で読みます。helper は未設定または空文字なら既定値 `0.0` を返し、それ以外は `std::atof` に渡します。文字列全体の妥当性検査や範囲制限はありません。`atof` が変換できない値は通常 `0.0` となり、数値の後ろに続く文字列も変換時に検査されません。

| 環境値 | 読み取り結果と適用 |
|---|---|
| 未設定、空文字 | `0.0`。待ち時間なし |
| 変換結果が 0 以下 | 待ち時間なし（適用条件 `gap > 0` を満たさない） |
| 変換結果が正 | queue 完了を待ち、指定されたミリ秒を sleep |

CLI 引数による上書きはありません。ベンチの `POS`、`ITERS`、`NNEW`、stand-in 設定は別の環境変数で決まり、`DF2B_GAPMS` の値を上書きしません。

## 有効になる条件

- SYCL ビルドで `STRATA_SYCL_PARITY` が有効なときに `dflash2_bench` ターゲットが定義されます（既定値は ON）。
- `dflash2_bench` は位置引数が省略された場合に `bench` 相当の `run_bench()` に入ります。明示的な `bench` も同じ経路です。`test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` などの別モードはこの読み取り箇所を通りません。
- `run_bench()` 内の direct launch と、`DF2B_GRAPH` が有効な場合の graph replay の計測ループで待ち時間を使います。graph は `DF2B_GRAPH` の既定値が 1 なので、通常は両方の計測ループが対象です。warm-up と per-kernel profile のループにはこの待ち処理がありません。

リポジトリ内の別の直接参照は `metal/tests/df2_bench.cpp` にもありますが、テスト専用コードとして本調査手順の実装根拠から除外しています。ここで説明する挙動は SYCL の `dflash2_bench` のものです。

## 実行時の詳細

値は `run_bench()` に入るたびにローカル変数 `gap` に一度読み込まれます。direct launch ループでは stand-in 処理の後、`gap > 0` の場合に `Q->wait()` を呼び、続けて `std::this_thread::sleep_for()` を実行します。その後に計測開始時刻を取り、round を投入して再度 queue 完了を待ちます。graph replay ループも同じ順序で待ち時間を挿入してから graph の計測を始めます。したがって、指定値は計測対象ラウンドの処理時間に加算する sleep ではなく、round の計測開始前の間隔です。

ベンチは設定行 `config: ... gap %.2f ms` に変換後の `gap` を表示します。専用の警告、無効値エラー、終了分岐はありません。起動後に環境値を変更しても、すでに読み込んだ `gap` は更新されません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56-57` — `envd()` の未設定・空文字時 fallback と、その他の値に対する `std::atof`。
- `sycl/src/kernels/dflash2_bench.cpp:486-490,508` — `run_bench()` 内での値の読み取りと設定表示。
- `sycl/src/kernels/dflash2_bench.cpp:525-538,546-567` — direct launch / graph replay の計測ループと、正の値の場合の queue wait・sleep。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — 既定モードと `run_bench()` に到達するモード分岐。
- `sycl/CMakeLists.txt:289-290,437-438` — `STRATA_SYCL_PARITY` の既定値と、その条件内にある `dflash2_bench` ターゲット定義。
- `metal/tests/df2_bench.cpp:76,426-441` — テスト専用コードにある別の直接読み取りと使用箇所。調査範囲の規則により、上記の Strata 実行時挙動の根拠には含めていません。
