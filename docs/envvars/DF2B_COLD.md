# `DF2B_COLD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench gemm` で GEMM の重み行列を 1 組ではなく 8 組用意し、計測中に順番に切り替えて使います。実装コメントでは、8 組を回すことで行列群が L2 cache より大きくなる cold 計測を意図しています。通常の Strata 推論経路では参照されず、ベンチマーク実行ファイル `dflash2_bench` の `gemm` モード専用です。

## 値と判定

`envi("DF2B_COLD", 0)` が共通 helper を通じて値を整数に変換し、結果が 0 かどうかで組数を決めます。

| 環境値 | helper の結果 | 行列コピー数 |
|---|---:|---:|
| 未設定 | 既定値 `0` | 1 |
| 空文字 | 既定値 `0` | 1 |
| 整数として 0（例: `0`, `00`, `0xyz`） | `atoi` の結果 0 | 1 |
| 整数として非 0（例: `1`, `-1`, `2`, `1xyz`） | `atoi` の結果は非 0 | 8 |
| 数字で始まらない文字列（例: `true`, `xyz`） | `atoi` の結果 0 | 1 |

空文字でない値は `std::atoi` に渡されます。数値全体の検証や範囲チェックはなく、先頭の空白と符号に続く整数部分を変換し、整数の後ろにある文字は判定されません。したがって `0xyz` は 0、`1xyz` は 1 と扱われます。`atoi` の変換可能範囲外の値について、Strata 側に明示的な検査・fallback はありません。

## 有効になる条件

- `sycl/CMakeLists.txt` が定義する `dflash2_bench` を実行する必要があります。このターゲットは SYCL の独立した build に属します。
- プロセスの引数が `gemm` の場合だけ、この変数を読む `run_gemm_bench()` が呼ばれます。引数省略時は `bench` モードとなり、この変数は参照されません。`test` や他のモードでも参照されません。
- `gemm` モード内でも、値が 0 または helper の既定値に変換されると 1 組です。非 0 に変換された場合に 8 組です。
- `DF2B_COLD` より優先される CLI 引数、設定ファイル、別の環境変数はこの処理にはありません。

## 実行時の詳細

`main()` が引数からモードを選び、`gemm` のとき `run_gemm_bench()` に入ります。同関数が `DF2B_COLD` を一度読み、その整数値から `ncopy` を決めます。値を static cache には保存せず、このモードの実行中にプロセス環境を変更するための再評価箇所もありません。

各 GEMM shape について `ncopy` 個の重み行列群を device memory に作り、計測の 200 回の呼び出しでは `it++ % ncopy` で順に切り替えます。変数に応じて変わるのはこの行列コピー数と選択順です。出力は shape ごとの launch 時間と帯域表示で、`DF2B_COLD` 専用のログ表示はありません。device allocation helper は確保失敗時に stderr へ `out of device memory (<bytes> bytes)` を出して終了コード 2 で終了します。8 組で必要量が増えるため、この失敗経路に達する可能性があります。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56`: `envi` は環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi` を使う。
- `sycl/src/kernels/dflash2_bench.cpp:62`: device allocation 失敗時の stderr と終了コード 2。
- `sycl/src/kernels/dflash2_bench.cpp:614-641`: GEMM ベンチ本体と、変換結果に基づく 1/8 コピー選択。
- `sycl/src/kernels/dflash2_bench.cpp:643-645,658-662`: 選ばれたコピー数の重み確保と、計測時の順次切替。
- `sycl/src/kernels/dflash2_bench.cpp:894-901`: 引数で実行モードを選択し、`gemm` の場合だけ `run_gemm_bench()` を呼ぶ。
- `sycl/CMakeLists.txt:437-438`: `dflash2_bench` 実行ファイルの定義とリンク。
