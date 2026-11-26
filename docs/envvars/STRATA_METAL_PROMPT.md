# `STRATA_METAL_PROMPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の prompt prefill 経路を選ぶ開発・診断用スイッチ。値が完全一致で `window` の場合、通常の prompt GEMM 経路を避け、decode window を使って prompt を処理する。それ以外は通常経路の選択に進む。これは Metal engine の `prompt_run_rows` でのみ読まれる（`engine/metal/src/engine/window.cpp:3743-3776`）。

通常経路では、非 streaming の長い prompt は `Window::prompt`、streaming の長い prompt は prompt GEMM chunks を使う条件があり、短い prompt や GEMM を選ばない場合は decode window に戻る。`window` はこれらの通常経路選択を強制的に decode-window fallback にする。fallback は最大 8 行ずつ `run` と `commit` を行い、DFlash2 tap と `on_chunk` callback も各 chunk の後に呼ぶ（`engine/metal/src/engine/window.cpp:127,3748-3776`）。

## 値と判定

関数内 `static const bool` の初期化時に `std::getenv` で読み、値全体を大文字小文字を区別して文字列 `window` と比較する。未設定は false、空文字も false。`1`、`true`、`WINDOW`、前後に空白を含む値など、完全一致しない値はすべて false となり通常経路選択に進む。数値変換や無効値警告はない。候補索引の「on / off」分類ではなく、実装が判定する値は `window` である（`engine/metal/src/engine/window.cpp:3745-3748`）。

| 条件 | unset | fallback を強制する値 | fallback を強制しない値 |
|---|---|---|---|
| `prompt_run_rows` が呼ばれる Metal engine | 通常経路選択（短い prompt は decode-window fallback） | `window` | 空文字、`0`、`1`、`true`、`WINDOW`、`window ` など |

## 有効になる条件

- Metal engine を含む macOS build であること。Metal CMake project は Apple 以外で configure を拒否し、engine が `STRATA_GPU_METAL` 定義の下で Metal prompt 関数を呼ぶ（`engine/metal/CMakeLists.txt:1-2,18-20,103-109`; `engine/src/prefill/prefill.cpp:9633-9649`）。
- Metal prompt prefill または `engine/metal/probe/window_probe.cpp` の prompt 呼び出しが実行されること。候補値は decode/generation 全般の切替ではない（`engine/metal/probe/window_probe.cpp:109`; `engine/metal/src/engine/window.cpp:3733-3741`）。
- `g_window` が準備済みであること。未準備なら環境変数による分岐より先に `metal prompt: the decode window is not up yet` を返す（`engine/metal/src/engine/window.cpp:3743-3747`）。
- 他の prompt 閾値・切替との関係: `STRATA_METAL_PROMPT_MIN` は通常経路の非 streaming prompt 閾値（既定 32 行）、`STRATA_METAL_PROMPT_GEMM` と `STRATA_METAL_PROMPT_GEMM_MIN` は streaming GEMM の選択に使われるが、`window` が true の場合これらの通常経路選択ブロックを通らない（`engine/metal/src/engine/window.cpp:3746-3767`）。
- CLI 引数による `STRATA_METAL_PROMPT` の上書きは、確認した読取経路にはない。値はプロセス環境から取得する。

## 実行時の詳細

`prompt_run` は埋め込み行ポインタを一時的に保持して `prompt_run_rows` に委譲する。`prompt_run_rows` は decode window の存在を確認してから `windows` の static 初期化を行うため、環境値は最初の window-ready prompt 呼び出しで一度だけ読み取られ、同一プロセス内の後続呼び出しでは再読取されない。プロセス実行中に環境値を変えても、このキャッシュ済み判定には反映されない（`engine/metal/src/engine/window.cpp:3735-3748`）。

`window` が有効なら、prompt 全体を `MAXT`（8）行以下の範囲に分けて token ID を `int32_t` にし、各範囲で `g_window->run(..., false, ...)`、`commit`、tap 配信、任意の `on_chunk` callback を順に実行する。どれかが false を返せばそこで終了し、そのエラー文字列を呼び出し元へ返す。生成 token のサンプリングはこの fallback loop では行わない（head 引数は false、`engine/metal/src/engine/window.cpp:126-127,3768-3775`）。

通常経路では、`windows == false` かつ非 streaming で `n >= STRATA_METAL_PROMPT_MIN`（未設定時 32）なら `g_window->prompt` を使う。streaming では `STRATA_METAL_PROMPT_GEMM` が未設定または文字列 `0` 以外、かつ `n >= STRATA_METAL_PROMPT_GEMM_MIN`（既定 64）の場合に prompt GEMM chunks を選び、そうでなければ同じ decode-window loop に進む（`engine/metal/src/engine/window.cpp:3747-3776`）。

## ログと測定値

この環境変数の判定自体はログを出さず、無効値も警告しない。Metal 側の prompt 実行が失敗すると `prompt_run` の false と `err` が `Prefill::run` へ返る（`engine/metal/src/engine/window.cpp:3745,3772-3775`; `engine/src/prefill/prefill.cpp:9637-9649`）。decode window 未準備時のエラー文字列は `metal prompt: the decode window is not up yet`。

## 根拠

- `engine/metal/src/engine/window.cpp:3733-3776` — prompt wrapper、環境値の cache、通常経路と fallback の分岐、fallback の処理順。
- `engine/metal/src/engine/window.cpp:126-127` — window の最大行数 `MAXT=8`。
- `engine/src/prefill/prefill.cpp:280-288,9633-9649` — Metal build 側の宣言と `Prefill::run` からの呼び出し・戻り値。
- `engine/metal/CMakeLists.txt:1-2,18-20,103-109` — Metal project の macOS 条件と engine build option。
- `engine/metal/probe/window_probe.cpp:109` — 同梱 probe の prompt 呼び出し。
