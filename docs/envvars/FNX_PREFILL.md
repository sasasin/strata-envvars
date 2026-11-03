# `FNX_PREFILL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の専用実行ファイル `split_fnx_run` にある `logits` と `mtp` モードで、プロンプトをバッチ prefill 経路へ送るか、通常の window 経路で処理するかを選びます。通常利用者向け Strata CLI や sFNX サーバーの設定ではありません。CMake では同梱テスト／検査 driver として別 executable に組み込まれます（`src/split/CMakeLists.txt:153-165`）。

## 値と判定

helper は環境変数を符号付き base-10 `long long` の整数全体として parse します。先頭の `+` / `-` は許可されますが、少なくとも数字が一つ必要で、値の後ろに空白や他の文字を含められません。`long long` の範囲外も無効です。未設定の場合だけ呼び出し側の既定値を使います。空文字、不正な文字列、範囲外の値では `FNX_PREFILL: '<値>' is not a whole number` の例外になります（`src/split/src/env.hpp:15-22,33-40`）。

有効な整数は `0` なら無効、それ以外（負数を含む）なら有効です。clamp や `0` / `1` 以外の値の拒否はありません。未設定時の既定値はモードごとに異なります。

| モード | 未設定 | `0` | 0 以外の整数 | 空文字・不正値 |
|---|---|---|---|---|
| `logits` | 無効 | 無効 | 有効 | 例外 |
| `mtp` | 有効 | 無効 | 有効 | 例外 |

## 有効になる条件

- `split_fnx_run` の `logits` または `mtp` モードでのみ読み取られます。ほかの `fnx_run` モードではこの変数を参照しません（`src/split/tools/fnx_run.cpp:958-969,989-1008`）。
- `logits` では有効時でも、プロンプト全体を一度に prefill するのではなく、最後の token より前を `e.prefill()` に渡し、最後の token は `e.window()` で処理します。無効時は入力を `fnx::MAXT` 件ずつ window に渡します（`src/split/tools/fnx_run.cpp:155-168`）。
- `mtp` では prompt path を選ぶ条件が `FNX_PREFILL != 0` かつ prompt が 2 token 以上です。条件を満たす場合は最後以外を `e.prefill(..., prompt.back())` に渡し、最後の token を window と draft layer で処理します。それ以外は prompt を `fnx::MAXT` 件ずつ処理し、各 window の後に draft layer を実行します（`src/split/tools/fnx_run.cpp:1008-1025`）。
- CLI 引数による上書きや、別環境変数との優先順位はありません。判定は GPU/backend 分岐やモデル形式ではなく、上記モードと prompt 長で決まります。

## 実行時の詳細

`logits` では `fnx::env_flag("FNX_PREFILL")` が使われ、これは既定値 `0` の `env_int` を呼びます。`mtp` では `fnx::env_int("FNX_PREFILL", 1)` を直接呼びます（`src/split/tools/fnx_run.cpp:989-1008`; `src/split/src/env.hpp:33-52`）。値は `static` に cache されず、各 mode の処理開始時に読み取られます。その後プロセス環境を変更する経路はこの driver にありません。

有効な値なら、`logits` は prefill の処理時間と速度を stderr に `prefill: ...` と出します。`mtp` は prompt 処理時間と経路名を stderr に `prompt: ... prompt path` または `prompt: ... windows` と出します。なお、MTP の prompt が 1 token 以下だと既定値または設定値が有効でも window 経路になります（`src/split/tools/fnx_run.cpp:156-168,1010-1029`）。

不正値の例外は `main` の catch 節で `fnx_run: ...` と stderr に出され、終了コード `1` になります。環境値の評価は model と Engine の構築後に行われるため、不正値でもそれらの初期化を経てから失敗します（`src/split/tools/fnx_run.cpp:982-992,1364-1373`）。

## 根拠

- 全参照とモード分岐: `src/split/tools/fnx_run.cpp:155,992,1005,1008`。
- 整数 parse、既定値、不正値の例外、および `env_flag` の定義: `src/split/src/env.hpp:15-22,33-52`。
- 実行ファイルの用途と build 定義: `src/split/CMakeLists.txt:153-165`。
- 不正値の stderr 出力と終了コード: `src/split/tools/fnx_run.cpp:1364-1373`。
