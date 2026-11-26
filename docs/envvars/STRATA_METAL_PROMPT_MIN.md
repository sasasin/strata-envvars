# `STRATA_METAL_PROMPT_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend の非 streaming prefill で、prompt-chain 経路へ切り替える最小 token 行数を決める。prompt の長さ `n` がこの値以上なら `Window::prompt` を呼び、未満なら decode window で通常の prompt 処理を行う。これは経路選択の閾値であり、token 数自体や生成設定は変更しない。実装は `prompt_run_rows` にある（`engine/metal/src/engine/window.cpp:3743-3776`）。

## 値と判定

環境変数が未設定なら閾値は `32`。設定されていれば `std::atoll` で符号付き整数へ変換し、値の検証や範囲制限はしない。空文字や数字で始まらない文字列は `0` になり、数値の後ろに文字があっても数値部分を使う。したがって `32tail` は `32`、`0anything`・`true` は `0`。先頭の空白と符号も `atoll` の変換規則に従う。比較は `n >= min_rows` なので、境界値ちょうどで prompt-chain 経路を選び、`0` または負値なら通常の非負 prompt 長はすべて条件を満たす。`1` は長さ 1 以上で条件を満たす（`engine/metal/src/engine/window.cpp:3747-3748`）。

| 条件 | unset | 設定時に prompt-chain へ進む値の例 | 別経路になる値の例 |
|---|---:|---|---|
| Metal、非 streaming、`STRATA_METAL_PROMPT` が `window` でない | `32` | 長さ 32 の prompt に対する `32`、`32tail`。`0`、空文字、`true`、`-1` なら通常の非負長で条件を満たす | 閾値が `32` のとき長さ 31 の prompt |
| streaming、または `STRATA_METAL_PROMPT=window` | 値は読み取られるがこの分岐では使わない | この変数による選択はない | この変数による選択はない |

## 有効になる条件

- `STRATA_GPU_METAL` 付きの Metal build で動く prefill に限られる。Metal CMake project は Apple 専用で、共有 `Prefill::run` は Metal build で `prompt_run` に渡す（`engine/metal/CMakeLists.txt:1-2,18-20`; `engine/src/prefill/prefill.cpp:9633-9649`）。
- Metal decode window が登録済みであることが必要。未登録なら閾値を読む前に `metal prompt: the decode window is not up yet` をエラーにして失敗する（`engine/metal/src/engine/window.cpp:3743-3747`）。
- `STRATA_METAL_PROMPT=window`（完全一致、小文字）なら prompt-chain と streaming 用 GEMM 分岐を抑止し、閾値に関係なく decode-window 経路へ進む。この判定も `prompt_run_rows` 初回呼び出し時に cache される（`engine/metal/src/engine/window.cpp:3746-3748`）。
- window が streaming 状態なら、この閾値では経路を選ばない。代わりに `STRATA_METAL_PROMPT_GEMM` が文字列 `0` かどうかと `STRATA_METAL_PROMPT_GEMM_MIN`（未設定時 64）で GEMM 経路を選び、それに該当しない場合は decode-window 経路へ進む（`engine/metal/src/engine/window.cpp:3749-3775`）。
- CLI 引数や設定ファイルによる閾値上書きはこの読み取り箇所にはない。環境変数の値を直接変換している（`engine/metal/src/engine/window.cpp:3747`）。

## 実行時の詳細

`Prefill::run` は Metal build で `strata::metal_engine::prompt_run` を呼び、そこから `prompt_run_rows` に到達する。関数は decode window の存在を確認した後、`STRATA_METAL_PROMPT_MIN` を関数内 `static const int64_t` に一度だけ読み込む。実行中に環境を変更しても、そのプロセスの後続 prompt には反映されない（`engine/src/prefill/prefill.cpp:9629-9649`; `engine/metal/src/engine/window.cpp:3735-3748`）。

非 streaming で閾値以上なら `Window::prompt` が prompt-chain を初期化し、chunk ごとに処理する。setup 失敗時は `metal prompt: setup failed`、prompt が context 範囲を超えた場合は `metal prompt: the prompt runs past the context` を返す。いずれも `prompt_run_rows` から呼び出し元へ失敗として伝播する（`engine/metal/src/engine/prompt_chain.inc:583-612`; `engine/metal/src/engine/window.cpp:3748`; `engine/src/prefill/prefill.cpp:9641-9649`）。閾値未満や明示的 window 経路では `MAXT` 行ずつ `run` と `commit` を行い、失敗は同じく呼び出し元へ伝播する（`engine/metal/src/engine/window.cpp:3768-3776`）。

## ログと測定値

この変数自体を報告するログはない。prompt-chain 経路では `STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定されている場合に、prompt の token 数・所要時間・GPU/host 時間・token/s を stderr に出す。既定ではこの行は出ない（`engine/metal/src/engine/prompt_chain.inc:608-611`）。この環境変数の閾値に関する測定値は、調査対象のソース資料では確認できなかった。

## 根拠

- 直接の読み取り、値の既定値、比較、および streaming/window の分岐: `engine/metal/src/engine/window.cpp:3743-3776`
- prompt-chain 経路の初期化、失敗条件、trace/profile ログ: `engine/metal/src/engine/prompt_chain.inc:583-612`
- Metal build の platform 条件: `engine/metal/CMakeLists.txt:1-2,18-20`
- Metal prefill からの呼び出し: `engine/src/prefill/prefill.cpp:9629-9649`
