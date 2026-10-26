# `DS4_WARM`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 の chunked prompt path が使う BLAS GEMM の初回起動を、モデル読み込み後のバックグラウンド処理で先に行うかを制御します。これは prompt path のウォームアップであり、expert や OS page cache を事前に読む別の処理とは異なります。

## 値と判定

`start_warm()` が `getenv("DS4_WARM")` を調べ、設定値は `atoi()` で整数に変換し、その結果が `0` の場合にウォームアップを止めます。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（ただし `chunk > 0` の場合） |
| 空文字 | `atoi("") == 0` のため無効 |
| `0`、`00`、`-0`、`0.5` | 変換結果が 0 のため無効 |
| `1`、`-1`、`2` | 変換結果が非 0 のため有効 |
| 数字の後ろに文字が続く値（例: `1abc`） | `atoi()` が先頭の数値部分を変換するため有効。`0abc` は無効 |
| 数値に変換できない文字列（例: `true`） | `atoi()` の結果が 0 のため無効 |

空白は `atoi()` の整数変換規則に従います。文字列全体の妥当性検査、範囲制限、大文字小文字の判定はありません。環境変数の値が数値として 0 かどうかを判定しており、「設定されていれば有効」ではありません。

## 有効になる条件

- `chunk > 0` であること。これは prompt を chunk に分けて処理する設定・選択が有効な場合です。`chunk <= 0` の windowed prompt path では `DS4_WARM` が未設定でもウォームアップを開始しません。
- `start_warm()` 実行時点で chunked path がまだ使われておらず、モデル終了処理も始まっていないこと。すでに chunked path が始まっていればバックグラウンド側は何もせず終了します。
- CMake の `STRATA_BUILD_DSV41` を有効にして `strata-dsv41` をビルドすること。このターゲットは既定で無効で、`STRATA_HIP_GFX906` の場合は作成されません。

通常の prompt 処理は入力長などに応じて windowed path を選ぶことがあります。その場合も、環境変数が有効値であることだけでは `forward_chunks()` の利用は保証されません。

## 実行時の詳細

モデルの `load()` が初期化を終えると `start_warm()` を呼びます。この時点で環境変数を読み、条件を満たす場合は専用スレッドを開始します。値はモデル load 時にこの一度だけ評価されるため、ロード後にプロセス環境を変更しても、そのモデルの判定は変わりません。

バックグラウンド処理は `warm_mu` を取得し、chunked path が既に使用済みか、終了処理が始まったかを確認します。どちらでもなければ各 chunk/device の BLAS handle を使って小さい入力の GEMM を実行します。対象は mHC mix 用の FP32 GEMM と、projection/indexer 用の FP16 入力 GEMM です。出力先は chunk の scratch buffer (`c.mix`, `c.y`) で、実装コメントでは heat、profile、stats、positions、KV などの engine state は変更しないとしています。

最初の chunked prompt がウォームアップと競合した場合、`forward_chunks()` は `warm_mu` の解放を待ってから処理します。モデル破棄時も warm-up thread を join してから BLAS handle を破棄します。BLAS 呼び出し、stream 同期、`cudaGetLastError()` の戻り値はこの処理内で無視されます。`o.verbose` が有効で、バックグラウンド処理が実際に `warm_flow()` を呼んだ場合は stderr に `ds4: prompt path warmed up in %.0f ms` を出します。環境変数を理由とするログはありません。

## 根拠

- `src/dsv41/ds4_model.cu:2823-2827` — 初期化後に `start_warm()` を呼ぶ。
- `src/dsv41/ds4_model.cu:2843-2858` — ウォームアップで実行する GEMM、scratch 出力、stream 同期。
- `src/dsv41/ds4_model.cu:2860-2876` — 評価条件、`atoi()` 判定、mutex、開始済み判定、verbose ログ。
- `src/dsv41/ds4_model.cu:1243-1251` — 破棄時にスレッドを join してから BLAS handle を破棄。
- `src/dsv41/ds4_model.cu:1990-2004,9356-9367` — chunk の決定と、入力に応じた chunked/windowed path の選択。
- `src/dsv41/ds4_model.cu:8187-8193` — chunked path が使用済みであることを記録し、warm mutex を取得。
- `CMakeLists.txt:797-810` — `strata-dsv41` のオプションとターゲット作成条件。
