# `CUDA_LAUNCH_BLOCKING`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata の engine が、この環境変数を CUDA の verify window に関する診断用スイッチとして読みます。CUDA 系ビルドでは有効値を検出すると起動時に警告し、リクエストが停止したときの watchdog ログにも設定状態を付記します。Strata はこの値を CUDA runtime に設定したり、環境変数自体を書き換えたりしません。

## 値と判定

値全体の比較ではなく `std::atoi()` の結果が 0 かどうかで判定します。未設定の場合は無効です。設定されていても空文字、数値に変換できない文字列、先頭の整数部分が 0 の文字列は無効になります。先頭の整数部分が 0 以外なら有効です。

| 値の例 | 判定 | 理由 |
|---|---|---|
| 未設定 | 無効 | `getenv()` が null |
| 空文字、`abc`、`0`、`0suffix` | 無効 | `atoi()` が 0 を返す |
| `1`、`2`、`-1`、`1suffix`、` 1` | 有効 | `atoi()` が 0 以外を返す |

`atoi()` による変換結果だけを見ており、文字列全体の数値妥当性は検査しません。数値範囲外入力の変換結果はこの文書では規定しません。

## 有効になる条件

`STRATA_USE_HIP` または `STRATA_HIP_GFX906` が定義されたビルドでは、`launch_blocking()` は環境変数を読まず常に無効を返します。その他のビルドでは上記の値判定を行います。したがって、値が有効でも HIP ビルドでは警告や watchdog の追加文言は出ません。

この値は CUDA の verify window がある実行経路で問題を診断するためのものです。ソースの警告は、blocking launch では prompt 後の最初の verify window が完了せず、watchdog が engine を終了させると説明しています。一方、batched prompt path は同じ待ちを持たず実行できるとも記されています。これは Strata のソースコメントおよび警告文にある説明です。

## 実行時の詳細

`launch_blocking()` は起動時の警告判定と watchdog の停止ログ生成時に呼ばれます。値は static cache されていません。起動時に有効と判定されると stderr に次の警告を出します: `warning: CUDA_LAUNCH_BLOCKING=1: the verify windows cannot run with blocking launches, so the first one after a prompt hangs until the watchdog ends the engine (#1341). Unset it; STRATA_PF_STEP_SYNC=1 narrows down a failing prompt step without it`。表示上は値が `1` と固定されていますが、実際の判定は `atoi(value) != 0` です。

watchdog は `STRATA_WATCHDOG_S` を秒数として読み（未設定時 60、0 以下なら watchdog thread を起動しない）、停止を検出したとき、`CUDA_LAUNCH_BLOCKING` が有効なら `no verify window can finish with it (#1341)` を stderr の停止メッセージに付けます。watchdog は停止レポートを出した後 engine を abort します。したがって、実際に engine を終了させるタイミングは watchdog の設定にも依存します。

## 根拠

- `src/program/generate.cpp:1430-1439` — CUDA/HIP ビルド差、`getenv()` と `atoi()` による判定、verify window に関する設計コメント。
- `src/program/generate.cpp:2361-2374` — 起動時の判定と stderr 警告文。
- `src/program/generate.cpp:11142-11154,11188-11198` — watchdog の既定秒数、無効化条件、停止時の環境変数表示と engine abort。
- `src/program/generate.cpp:13094-13106` — prompt を batched path で処理する経路の記述。
- `src/core/verify.cpp:2857,2946` — CUDA verify graph の launch 箇所。blocking launch と host flag 待ちの問題については `src/program/generate.cpp:1430-1432` の Strata 側コメントを根拠とし、CUDA runtime の一般的な挙動までは説明していません。
