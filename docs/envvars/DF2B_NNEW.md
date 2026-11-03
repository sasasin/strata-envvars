# `DF2B_NNEW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench` が測定する 1 ラウンドの「context update」で処理する行数を指定します。Strata の通常の生成・推論処理が読む設定ではなく、SYCL カーネルのベンチマーク／検証用実行ファイルだけで使われます。ソース先頭の説明では context rows の既定値を 3 としています。

## 値と判定

`envi()` は `std::getenv()` で取得した値が null または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を返します。文字列全体の検証、範囲チェック、clamp はありません。

| 環境値 | `NNEW` |
|---|---:|
| 未設定 | 3 |
| 空文字 (`DF2B_NNEW=`) | 3 |
| 数字として解釈できる文字列 | `atoi` の整数変換結果。先頭の空白や符号は `atoi` に従い、数字の後ろに文字があっても数字部分を変換する（例: `3x` は 3） |
| 空白または数字で始まらない非空文字列 | 0 |
| `0`、負数、8 を超える正数 | その整数をそのまま使用。拒否・補正する処理はない |

`atoi` で表現できない範囲の入力に対する結果は、このコードから保証できません。

## 有効になる条件

- `sycl/CMakeLists.txt` の `STRATA_SYCL_PARITY` ブロック内で `dflash2_bench` が定義されています。同オプションの既定値は ON です。
- `dflash2_bench` を `bench` モード（引数なしの既定モードを含む）で実行した場合に読み取られます。`test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` の各モードでは `run_bench()` が呼ばれず、この変数は使われません。既知のモード名以外は `run_bench()` に進みます。
- ベンチのモード引数はモードを選ぶだけで、`DF2B_NNEW` を上書きする CLI 引数はありません。他の環境変数との優先順位もありません。

## 実行時の詳細

`run_bench()` の開始時に一度読み、ローカル定数 `NNEW` に保持します。プロセス内キャッシュではありませんが、同じ `run_bench()` 実行中に環境値を読み直す箇所はありません。

`NNEW` はまず設定表示の `n_new` に出力されます。その後 `set_meta()` に渡され、メタデータの位置を作る際に `n_new - 1` と比較して使われます。さらに `record_round()` から `record_context()` へ行数として渡り、context 入力の行量子化、全レイヤーの K/V 射影、K/V ring 更新に渡されます。既定値 3 ではこれらの処理対象は 3 行です。値が 0 以下、または実装が想定する範囲外でも専用の検査・警告はなく、そのままメタデータ作成とカーネル呼び出しへ進みます。範囲外入力時の安全性や実行結果は、このコードでは保証していません。

ベンチは `config: ring pos ..., n_new ..., drafts ..., iters ...` を stdout に出します。`DF2B_NNEW` 固有のエラー・警告・終了分岐はありません。デバイス確保失敗時の一般経路では `out of device memory (...)` を stderr に出して終了コード 2 となりますが、これはこの環境変数の値判定ではなく、後続の確保処理に対する経路です。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:3`: ベンチ用環境変数として列挙し、既定値 3 を記載。
- `sycl/src/kernels/dflash2_bench.cpp:56`: unset／空文字の既定値処理と `atoi` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:180-185`: `n_new` をメタデータの位置計算に使用。
- `sycl/src/kernels/dflash2_bench.cpp:210-218,259-271`: context 行数を量子化・K/V 処理に渡す流れ。
- `sycl/src/kernels/dflash2_bench.cpp:486-512`: `DF2B_NNEW` の読み取り時点、既定値、表示、および初回 context 更新。
- `sycl/src/kernels/dflash2_bench.cpp:525-583`: 同じ行数を測定ラウンド、graph、profile 経路で再利用。
- `sycl/src/kernels/dflash2_bench.cpp:62`: デバイス確保失敗時の stderr と終了コード。
- `sycl/src/kernels/dflash2_bench.cpp:894-902`: モード選択と `run_bench()` への既定・fallback 経路。
- `sycl/CMakeLists.txt:288-291,437-438`: `STRATA_SYCL_PARITY` の既定値と `dflash2_bench` の定義位置。
