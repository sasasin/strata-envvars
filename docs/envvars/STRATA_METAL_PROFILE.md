# `STRATA_METAL_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend の診断用タイミング集計を stderr に出す。decode window の処理時間を window サイズ・head 有無ごとに集計し、加えて MTP の draft と commit 時間を集計する。モデル計算、window 選択、生成 token はこの変数によって切り替わらない。window の計測・出力は `engine/metal/src/engine/window.cpp` の `Window::finish` と `Window::print_prof` が行う。`engine/metal/src/engine/prompt_chain.inc` では、この変数が設定されていると prompt 処理完了時の概要行も出す。Metal は Apple/macOS 専用 CMake project で、CUDA/HIP/SYCL build には含まれない（`engine/metal/CMakeLists.txt:1-2,18-20`）。

## 値と判定

数値や文字列として値を parse せず、`std::getenv` が null かどうかだけを見る。したがって未設定なら計測・出力は無効、空文字を含む設定済みの値なら有効である。`0`、`false`、`anything` も設定済みとして扱う。大文字小文字、空白、数値としての妥当性、境界値は検査しない。`Window::finish` の計測有効状態は初回呼び出しで function-local `static const bool` に cache される一方、出力時の `print_prof` と prompt 概要の条件は呼び出しごとに `getenv` を行う（`engine/metal/src/engine/window.cpp:2049-2051,2070-2078`; `engine/metal/src/engine/prompt_chain.inc:608-611`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Metal backend の `Window::finish` 計測 | 初回 `finish()` で計測 off | 空文字、`0`、`1`、`false`、その他すべての設定値 | なし（設定済みの値に無効値はない） |
| `Window::print_prof` の出力判定 | 出力しない | 空文字を含むすべての設定値 | なし（設定済みの値に無効値はない） |
| prompt 概要行（`STRATA_METAL_TRACE` が未設定の場合） | 出力しない | 空文字を含むすべての設定値 | なし（設定済みの値に無効値はない） |

CLI 引数や別の設定値による上書き・優先順位はない。prompt 概要行については `STRATA_METAL_TRACE` も同じ条件の別トリガーである（`engine/metal/src/engine/prompt_chain.inc:608-611`）。

## 有効になる条件

- Metal backend を含む macOS build であること。その他の backend にはこの実装は組み込まれない（`engine/metal/CMakeLists.txt:1-2,18-20`）。
- window 集計には `Window::finish` が少なくとも一度呼ばれる decode window の処理が必要。各 window のサイズ・head 有無別行は該当する処理があった場合だけ出力される（集計 `engine/metal/src/engine/window.cpp:2070-2078`、0 件を省く `2048-2064`）。
- MTP の draft / commit 行は、それぞれ対応する `prof_add` が呼ばれた場合だけ出る（`engine/metal/src/engine/window.cpp:588-590,3682-3694,3784-3788`）。
- prompt 概要行は prompt 処理が完了してその出力箇所に到達した場合に出る。`STRATA_METAL_TRACE` が設定済みなら `STRATA_METAL_PROFILE` が未設定でも同じ概要行が出る（`engine/metal/src/engine/prompt_chain.inc:608-612`）。
- `window_create` 時点で設定済みなら `atexit` に終了時出力 callback を登録する。登録されない起動経路では、通常の window 破棄時の `print_prof` が主な出力機会となる（`engine/metal/src/engine/window.cpp:2041-2045,3609-3614`）。

## 実行時の詳細

`Window::finish` は初回に `STRATA_METAL_PROFILE` の有無を cache し、以後その process 内では同じ判定を使う。有効なら window ごとに件数と累積時間（host before、`run_graph`、GPU、`patch+finish`、合計）を集計し、100 回ごとに累積値を `print_prof(true)` で出す。MTP draft / commit は `prof_add` が別集計へ時間と件数を追加する。window・commit・draft の時間分割は診断表示であり、decode や MTP の処理分岐には使われない（`engine/metal/src/engine/window.cpp:585-590,1515,1556,1639,2049-2064,2066-2078,3682-3694,3784-3788`）。

`print_prof` は出力のたびに環境変数を再確認する。非 periodic 呼び出しでは一度出力済みなら再出力せず、periodic 呼び出しは累積値を再出力する。window destructor は `print_prof()` を呼ぶ。serve loop が `exit()` で抜けて window destructor が走らない経路向けに、`window_create` は作成時に変数が設定済みなら `atexit` callback を登録し、終了時にも出力を試みる。環境変数をプロセス内で変更した場合、初回 `finish` 後の集計有効判定は変わらないが、出力時判定と prompt 行の判定にはその時点の設定有無が反映される。起動 wrapper による値の転送や CLI からの変更処理はこの実装箇所にはない（`engine/metal/src/engine/window.cpp:2041-2051,2070-2078,3609-3614`）。

## ログと測定値

集計行は stderr に `strata metal profile:` で始まり、各 window 行には回数・平均総 ms・平均 host before / run_graph / GPU / encode-submit-wait 差分 / patch+finish ms を表示する。続いて該当データがある場合 `commit` と `draft` の行を表示する。出力文字列は `engine/metal/src/engine/window.cpp:2052-2064` にある。

prompt 処理完了時には stderr に `strata metal: prompt ...` の行を出し、token 数、総時間、GPU/host/drafter 時間、tok/s を表示する。これは `STRATA_METAL_PROFILE` または `STRATA_METAL_TRACE` のいずれかが設定されている場合の出力で、profile 集計とは別の概要行である（`engine/metal/src/engine/prompt_chain.inc:608-611`）。この変数に関する性能測定値は対象資料にない。

## 根拠

- `engine/metal/CMakeLists.txt:1-2,18-20` — Metal project と macOS 条件。
- `engine/metal/src/engine/window.cpp:2041-2064` — destructor、設定有無の出力判定、stderr の書式と集計行。
- `engine/metal/src/engine/window.cpp:2066-2078` — 初回判定の cache、時間集計、100 回ごとの periodic 出力。
- `engine/metal/src/engine/window.cpp:1515,1556,1639,3682-3694,3784-3788` — 計測区間の開始・`run_graph` 時間・MTP 集計への追加。
- `engine/metal/src/engine/window.cpp:3609-3614` — window 作成時の `atexit` 登録。
- `engine/metal/src/engine/prompt_chain.inc:608-612` — prompt 概要行の条件と出力。
- `docs/MAC.md:261-282` — Metal の診断用 switch としての記載。
