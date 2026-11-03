# `FNX_MAX_CTX`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`sFNX` のテスト・比較用実行ファイル `fnx_run` が Engine に渡す最大コンテキスト長を指定します。Engine はこの値から K/V cache 用ページ数を決めます。通常の `strata` CLI や `sfnx` サーバーが読む環境変数ではありません。`fnx_run` は `STRATA_BUILD_SPLIT` で opt-in する strata-split のビルドに含まれるテストドライバーです（ビルド範囲は `src/split/CMakeLists.txt:1-7,153-165`）。

## 値と判定

| 実行経路 | 未設定 | 設定値の変換と下限 |
|---|---|---|
| `fnx_run` の通常モード | `4096` | `fnx::env_int` が符号付き十進整数を文字列全体から読み取る。明示値に下限 clamp はない |
| `fnx_run` の lab モード | `0` と必要長 `need` の大きい方 | `std::atoi` の結果と `need` の大きい方。変換エラーの検査はない |

通常モードの `env_int` は、空文字、数字でない文字列、数字の後ろに余分な文字がある値、`long long` の範囲外を不正値として例外にします。先頭・末尾の空白も全体 parse の条件を満たしません。値はその後 `int` に cast されますが、その cast 前の `int` 範囲検査や clamp はありません（`src/split/src/env.hpp:15-21,33-40`; 呼び出しは `src/split/tools/fnx_run.cpp:984-988`）。

lab モードの `atoi` 経路では、空文字や数値として読めない文字列は `0` になり、`need` より小さい値（負値を含む）は `need` まで引き上げられます。変換の妥当性を報告する分岐はありません（`src/split/tools/fnx_run.cpp:433-435`）。

## 有効になる条件

この変数を読むのは `src/split/tools/fnx_run.cpp` を含む `split_fnx_run` だけです。sFNX の本体は `STRATA_BUILD_SPLIT` が opt-in の strata-split 機能で、CMake 文書上の対応は Linux + CUDA または Linux + HIP です。変数名の参照はソース全体でこのファイルの読み取り 2 箇所だけでした。Engine 共通 helper に動的な環境変数名を渡して `FNX_MAX_CTX` を読む別経路もありません。

lab モードでは CLI の引数や各検査の入力長が必要コンテキスト `need` を決めます。実際の必要長は次の通りです。

- `read N`: `N + 1024`。
- `decode`: `262144`。
- `cache2`: `65536`。
- `batch`: `100000`。
- `exact`: 各プロンプトの token 数 `+ 1024`。
- `bdecode`: `262144`。

したがって lab モードでは、環境値が必要長より小さくてもその必要長を下回りません。通常モードでは positional CLI 引数が `FNX_MAX_CTX` を直接上書きする処理はありません。たとえば `bench_step` の `C` は prefill する長さであり、Engine の生成時の最大コンテキスト値とは別です（各モードの Engine 作成箇所は `src/split/tools/fnx_run.cpp:447,481,564,656,742,879`; `bench_step` は `1243-1255`）。

## 実行時の詳細

値は Engine を作るたびに読み取られ、値を static cache する実装ではありません。通常モードでは `fnx_run_cmd` がモードを処理する前に `FNX_MAX_CTX` を既定値 4096 で読み、`fnx::Engine` に渡します。lab モードでは `lab_check` 内で Engine ごとに `env_ctx(need)` が呼ばれます（`src/split/tools/fnx_run.cpp:433-435,978-988`）。プロセス起動後の環境変更は、後続の Engine 作成には反映され得ますが、既に作成した Engine の容量は変えません。

Engine は受け取った最大長から `ctx_pages = max_ctx / KVP_POS + 2` を計算し、必要に応じて K/V の int8 ページ比率を適用してページ数を定めます。さらに Engine の RoPE がカバーする上限を超える `max_ctx` は `context ... is past the ... the rotary covers (...)` の例外で拒否されます（`src/split/src/engine.cu:31,37-53,70-80`）。通常の `fnx_run` 実行ファイルでは `main` が例外を `fnx_run: <例外文>` として stderr に出し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。lab モードから同じ Engine を作る経路にも RoPE 上限判定が適用されます。

この値は子プロセスへ転送・上書きされません。調査した `fnx_run.cpp` 内では環境値を Engine の容量に渡すだけで、`FNX_MAX_CTX` 自体を書き換える処理はありません。

## 根拠

- `src/split/tools/fnx_run.cpp:433-435` — lab 用 `atoi` 読み取りと必要長の下限。
- `src/split/tools/fnx_run.cpp:447,481,564,656,742,879` — lab mode の Engine 作成箇所と各 `need`。
- `src/split/tools/fnx_run.cpp:978-988` — 通常経路の既定値 4096 と Engine への引き渡し。
- `src/split/src/env.hpp:15-21,33-40` — `env_int` の全体整数 parse と無効値時の例外。
- `src/split/src/engine.cu:31,37-53,70-80` — Engine が最大長を受け、RoPE 上限を判定し、K/V ページ数を算出。
- `src/split/tools/fnx_run.cpp:1364-1373` — 例外ログと `fnx_run` の終了コード。
- `src/split/CMakeLists.txt:1-7,153-165` — strata-split のビルド条件と `fnx_run` テストドライバーの定義。
