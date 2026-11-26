# `STRATA_METAL_PROMPT_GEMM_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の prompt 処理で、prompt 全体の token 数がこの数以上なら、SSD streaming 時に matrix-unit を使う prompt GEMM 経路を選ぶ下限を指定する。未設定時は 64。これは bool フラグではなく、`std::atoll` で読んだ符号付き整数と prompt token 数 `n` の比較に使われる。実際に経路を選ぶのは `prompt_run_rows` で、`stream_` が真かつ `STRATA_METAL_PROMPT=window` でない場合に限られる（`engine/metal/src/engine/window.cpp:3743-3766`）。

値が下限以上なら prompt を `prompt_chunk` に分割して処理し、下限未満なら decode window の `MAXT` 行単位の処理へ進む。matrix-unit 経路では chunk の計算が decode window の fp16 operands の経路と異なることがソースコメントに記されているが、ここでは性能や出力差を実測していない（`engine/metal/src/engine/window.cpp:2994-3001, 3753-3775`）。

## 値と判定

有効な `prompt_run_rows` 経路では、各呼び出し時に `std::getenv` の結果を `std::atoll` に渡し、未設定なら 64 とする。文字列全体の妥当性検査、範囲 clamp、空文字の特別扱いはない。`atoll` は数値として読める先頭部分を変換するため、空文字や数字で始まらない値は 0 になり、数字の後ろの文字は判定に使われない。符号付き値も受け取り、負値は `n >= mn` を満たしやすくする。比較は `n >= mn` である（`engine/metal/src/engine/window.cpp:3750-3753`）。

| 条件 | 未設定 | 判定が閾値以上になる例 | 判定が閾値未満になる例 |
|---|---:|---|---|
| `prompt_run_rows` の streaming 経路 | `mn = 64` | `64`、`64junk`（`n >= 64` のとき） | `65`（`n = 64` のとき）、`0`、空文字、`junk` |
| `Window::prompt_gemm_on` 内の読み取り | `mn = 64` | `64`、`64junk`（`n >= 64` のとき） | `0`、空文字、`junk`（`n > 0` のとき） |

`Window::prompt_gemm_on` も同じ変数を関数内 `static` に保存して読み取る一方、リポジトリ内の呼び出し箇所は宣言と定義以外に見つからない。この helper の読み取りは初回呼び出し時に固定される実装だが、現行 checkout では到達する経路ではない。下の streaming 経路は `prompt_run_rows` を呼ぶたびに読み直す（`engine/metal/src/engine/window.cpp:542, 3025-3035, 3750-3753`）。

## 有効になる条件

- Metal backend の `window.cpp` が実行され、Metal decode window が利用されていること（`engine/metal/src/engine/window.cpp:1-9`）。
- `prompt_run_rows` に到達し、`g_window` が存在すること。存在しない場合は `false` を返し、`err` に `metal prompt: the decode window is not up yet` を設定する（`engine/metal/src/engine/window.cpp:3743-3745`）。
- `STRATA_METAL_PROMPT` が文字列全体で `window` と一致しないこと。一致時は matrix-unit の streaming 分岐を通らず、decode window 経路へ進む（`engine/metal/src/engine/window.cpp:3746-3749`）。
- `g_window->streaming()` が真であること。この分岐は SSD streaming 用で、非 streaming 時は別の `STRATA_METAL_PROMPT_MIN`（未設定時 32）を使う判定を先に行う（`engine/metal/src/engine/window.cpp:3747-3750`）。
- `STRATA_METAL_PROMPT_GEMM` が文字列全体で `0` と一致しないこと。未設定、空文字を含むその他の値では GEMM 分岐を許可する。`0` なら下限に達していても decode window の通常経路に進む（`engine/metal/src/engine/window.cpp:3750-3754`）。
- `n >= mn` であること。条件を満たさない場合、prompt は `MAXT` 行ごとに `run`、`commit` される（`engine/metal/src/engine/window.cpp:3753-3775`）。

なお、streaming arena の初期化側は `STRATA_METAL_PROMPT_GEMM` が未設定または `0` 以外なら `prompt_gemm_init` を呼び、prompt GEMM 用バッファを先に初期化する。この初期化には本変数の閾値は使われないため、prompt が閾値未満でも初期化・バッファ確保が行われる場合がある（`engine/metal/src/engine/window.cpp:1793-1808`）。

## 実行時の詳細

`prompt_run_rows` は `STRATA_METAL_PROMPT_GEMM_MIN` を呼び出しごとに読み、未設定なら 64 として prompt 全体の `n` と比較する。下限以上なら `prompt_gemm_init` を行い、初期化済み chunk 行数 `C` ずつ token を `int32_t` に変換して `prompt_chunk` へ渡す。chunk ごとに指定された `on_chunk` callback も呼ぶ。下限未満、または GEMM が無効なら `MAXT` 行ずつ通常の decode window を `run`・`commit` し、必要に応じて DFlash2 tap と callback を実行する（`engine/metal/src/engine/window.cpp:3743-3775`）。

`Window::prompt_gemm_on` の方は閾値と `STRATA_METAL_PROMPT_GEMM` の値を関数内 `static` にキャッシュする実装だが、現在は呼び出し箇所がない。実際の streaming 判定が環境変数を呼び出しごとに再読するため、実行中に環境を変更できるプロセスではその後の呼び出しに反映される。初期化時に GEMM が許可されていたかどうかは arena 作成時のバッファ初期化に影響するが、閾値による prompt 選択とは別の判定である（`engine/metal/src/engine/window.cpp:1793-1808, 3025-3035, 3750-3755`）。

## ログと測定値

閾値の値や、閾値未満で通常経路へ進んだことを示す専用ログはない。`prompt_gemm_init` が成功すると `strata metal: prompts on the matrix units in chunks of ...` を stderr に出す。streaming arena の作成時に呼ばれた場合、これは閾値による prompt 選択より前に出ることがある（`engine/metal/src/engine/window.cpp:1808, 3123-3127`）。

初期化失敗ではエラー文字列を設定して `false` を返し、呼び出し元へ伝播する。streaming arena 内の初期化では `prompt_gemm_init` が失敗すると `stream_arena` が `false` を返す。streaming prompt 中に初期化が失敗した場合も `prompt_run_rows` は `false` を返す。確認できる具体的な失敗文字列には、prompt バッファ用 arena 領域不足時の `metal prompt: no arena region for the prompt buffers` がある（`engine/metal/src/engine/window.cpp:1808, 3037-3039, 3118-3121, 3753-3755`）。

## 根拠

- `engine/metal/src/engine/window.cpp:3025-3035` — helper 内の読み取り、既定値 64、`n >= mn` 判定。helper はリポジトリ内で呼び出されていない。
- `engine/metal/src/engine/window.cpp:1793-1808` — streaming arena 初期化時に GEMM を許可する判定と初期化。
- `engine/metal/src/engine/window.cpp:3743-3775` — 実際の prompt streaming 分岐、閾値比較、chunk / 通常 window 経路。
- `engine/metal/src/engine/window.cpp:3037-3040, 3118-3127` — prompt GEMM 初期化、buffer 確保失敗と成功ログ。
- `terminal/data/settings-register.json:23539-23575` — 候補一覧の付帯情報（Metal、2 読み取り箇所、int、既定値 64）。挙動の根拠は上記ソースコード。
