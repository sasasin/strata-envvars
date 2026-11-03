# `STRATA_INJECT_FATAL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

GPU fatal error の処理を試すための注入フックです。正の整数 `N` を指定すると、エンジンの `exit_if_gpu_fatal()` が通常の decode window の前に呼ばれた回数を数え、`N` 回目に実際の CUDA/HIP エラーがなくても illegal memory access を模した fatal 終了を起こします。通常利用向けの GPU 設定ではなく、ソースコメントでも test hook とされています。対象名を読む実装は `src/program/generate.cpp` のこの箇所だけで、共通 helper や Python 側の読み取りはありません（`src/program/generate.cpp:3145-3165`）。

## 値と判定

値は `std::atol()` で `long` に変換し、変換結果が正のときだけ注入を有効にします。文字列全体の厳密な数値検証はしません。

| 環境値 | 判定と結果 |
|---|---|
| 未設定 | `0`。注入しない。 |
| 空文字 | `atol("")` は `0`。注入しない。 |
| 正の整数（例 `1`, `3`） | 変換結果 `N > 0`。通常の decode window 前の `N` 回目の判定で注入する。 |
| `0` または負数 | `N > 0` でないため注入しない。 |
| 数字に変換できない文字列 | `atol` の変換結果は `0` となり、注入しない。 |
| 数字の前後に空白、符号、または数字の後ろに文字がある文字列 | `atol` が読む先頭の数値部分を使う。例: `+2`, ` 2`, `2x` は `2` として扱われる。 |

`long` の表現範囲を超える値に対する `atol` の結果はこのコードで検査・制限されません。値を読み取った最初の `exit_if_gpu_fatal()` 呼び出しで `static const long` に保存されるため、その後の環境変更は反映されません（`src/program/generate.cpp:3153-3156`）。

## 有効になる条件

- エンジンが `src/program/generate.cpp` の decode loop に入り、`exit_if_gpu_fatal("")` が呼ばれることが必要です。これは `ver.run()` の直前にあります。したがって、モデル・GPU の初期化前や decode window に到達しない起動では発火しません（`src/program/generate.cpp:18464-18471`）。
- 正の設定値でも、発火対象の回に `STRATA_INJECT_FATAL_ONCE` が空でないパスを指定し、そのファイルが既に存在すると注入を抑止します。ファイルがなければ作成を試みてから注入します。作成に失敗しても `fire` は true のままなので注入します。該当する `N` 回目に既存ファイルで抑止されても、カウンターはその回で `N` を通過するため後の window では発火しません（`src/program/generate.cpp:3156-3164`）。
- `STRATA_INJECT_FATAL_ONCE` は `STRATA_INJECT_FATAL` の値を上書きせず、注入の該当回だけをファイルの存在で抑止します。別の CLI 引数や環境変数による優先順位・上書きはありません。
- 読み取りと判定に OS/backend の条件分岐はありません。確認したのはこの共有 decode engine のソース経路であり、個別のビルド構成すべてでの実行確認はしていません。

## 実行時の詳細

通常経路では各 decode window の `ver.run()` 前に `exit_if_gpu_fatal("")` を呼びます。注入カウンターはこの関数の呼び出し時に増え、設定値との一致時に `exit_gpu_fatal()` を実行します。window の実行失敗後、commit 失敗時、最終 commit 待ち失敗時にも同じ判定関数が呼ばれます。そのため、GPU エラーのある経路では一つの window に対して複数回呼ばれ得ます（`src/program/generate.cpp:18467-18471,18512-18516,18678-18681`）。

注入時のエラー文字列は `injected (STRATA_INJECT_FATAL): an illegal memory access was encountered` です。fatal 終了関数は stderr に `strata serve: fatal GPU error (...)`、stdout に `ERR fatal GPU error: ...` を出し、それぞれ flush して終了コード `3` で `_Exit` します。通常の GPU fatal error と同じ終了経路です（`src/program/generate.cpp:3146-3151,3157-3165`）。

Python サーバーはこの `ERR fatal GPU error` をエンジン終了として扱い、実行中の要求を失敗（503）にし、次の要求でエンジンを起動し直します。同一エンジンの fatal 終了が 10 分以内に 3 回に達すると再起動を止めます（`serve/server.py:1782-1791,4965-4991`）。このサーバー側の挙動は fatal 終了一般の処理であり、環境変数の値を読む処理ではありません。

## 根拠

- `src/program/generate.cpp:3141-3151` — fatal GPU error の説明、stderr/stdout の出力、flush、終了コード 3。
- `src/program/generate.cpp:3153-3165` — `STRATA_INJECT_FATAL` の `getenv`、`atol`、static cache、呼び出しカウンター、`STRATA_INJECT_FATAL_ONCE` による抑止、注入するエラー文字列。
- `src/program/generate.cpp:18464-18471,18512-18516,18677-18681` — decode window 前と失敗経路での判定呼び出し。
- `serve/server.py:1782-1791,4965-4991` — fatal ERR による要求失敗とエンジン再起動の扱い。
