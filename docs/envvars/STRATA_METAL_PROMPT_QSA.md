# `STRATA_METAL_PROMPT_QSA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の streaming prompt GEMM 経路で、QSA prompt attention を `flash` と `v1` のどちらで dispatch するか選ぶ。未設定時は `coop_k4()` が判定した matmul2d layout (`p.k4`) に合わせ、K4 なら flash、そうでなければ v1 になる。設定されている場合は値が `flash` と完全一致したときだけ flash を選ぶ。選択結果は初期化ログにも出る。`prompt_chain.inc` の通常 prompt 経路にはこの環境変数の参照がなく、同経路の `b.k4` による処理とは別である。根拠: `engine/metal/src/engine/window.cpp:3061-3066,3124-3126,3287-3308`; `engine/metal/src/engine/prompt_chain.inc:26-46,49-60`。

## 値と判定

値は `std::getenv` で取得し、未設定かどうかを見た後、設定値全体を `std::string(eq) == "flash"` で比較する。大文字小文字を区別し、空白除去や数値・真偽値への変換はしない。空文字、`v1`、`FLASH`、`flash `、`1`、`0`、その他の値はいずれも v1 を選ぶ。無効値の警告や fallback ログはなく、値の受理範囲の検証もない。未設定時の結果のみ `p.k4` に依存する。根拠: `engine/metal/src/engine/window.cpp:3061-3066`。

| 条件 | unset | 設定時に flash になる値 | 設定時に v1 になる値 |
|---|---|---|---|
| Metal streaming prompt GEMM の初期化 | `p.k4 == true` なら flash、それ以外は v1 | 完全一致の `flash` | 空文字を含む `flash` 以外すべて（例: `v1`, `FLASH`, `flash `, `1`, `0`） |

`p.k4` は `coop_k4()` の結果で、`COOP_K4` が設定されていれば `atoi(e) != 0`、未設定なら Metal の協調レイアウトを実行して判定する。このため `COOP_K4` が設定されている場合はその変換結果が未設定時の既定選択に影響する。根拠: `engine/metal/src/engine/window.cpp:3061`; `engine/metal/src/engine/prompt_chain.inc:26-46`。

## 有効になる条件

- Metal backend の `Window::prompt_gemm_init` が走る streaming prompt GEMM 経路で読む。`STRATA_METAL_PROMPT_GEMM=0` は streaming arena の初期化時の GEMM setup を無効にし、prompt 実行時の streaming GEMM 分岐も通さない。未設定または文字列 `0` 以外なら有効候補になる。根拠: `engine/metal/src/engine/window.cpp:1793-1808,3749-3765`。
- streaming prompt では `STRATA_METAL_PROMPT=window` の指定がなく、かつ token 数が `STRATA_METAL_PROMPT_GEMM_MIN`（未設定時 64）以上である必要がある。満たさない場合は decode window 経路に進み、この変数による選択は使われない。根拠: `engine/metal/src/engine/window.cpp:3746-3775`。
- 非 streaming の長い prompt は `Window::prompt` を呼び、`prompt_chain.inc` の実装を使う。この変数はその経路では読み取られず、設定しても選択に影響しない。`STRATA_METAL_PROMPT=window` の場合も `prompt_run_rows` は prompt GEMM 経路を迂回する。根拠: `engine/metal/src/engine/window.cpp:3743-3775`; `engine/metal/src/engine/prompt_chain.inc:49-60`。
- `COOP_K4` は値が未設定のときの既定選択 (`p.k4`) にだけ関係する。`STRATA_METAL_PROMPT_QSA` が設定されていれば、その値の `flash` 判定が QSA variant を決める。ただし flash kernel の dispatch には `p.k4` も function constant として渡される。根拠: `engine/metal/src/engine/window.cpp:3061-3066,3290-3293`。

## 実行時の詳細

streaming arena を作る際、`STRATA_METAL_PROMPT_GEMM` が無効でなければ `prompt_gemm_init` が初期化される。streaming prompt 実行時にも同じ初期化関数を呼ぶが、すでに `pg_` がある場合は直ちに成功して戻る。その初回初期化で環境変数を読み、`p.flash` に保存し、以後はその値で scratch buffer サイズと QSA dispatch を決める。したがって初期化後にプロセス環境を変更しても既存の `PromptGemm` には反映されない。根拠: `engine/metal/src/engine/window.cpp:1808,3037-3039,3065-3066,3096,3123-3126,3753-3755`。

flash では `p.part` に小さい固定領域を確保し、QSA を `qsa_q_f16` と `qsa_flash` で処理する。v1 では `p.QS` と QSA geometry に応じた partial buffer を確保し、`qsa_attn` を `p.QS` 行単位で実行して `qsa_merge` で結合し、出力を fp16 化する。どちらも後続の出力 projection に進む。コード上、この変数が直接変えるのはこの QSA prompt attention の kernel variant と scratch buffer であり、モデル選択や CLI 引数の値を変更する処理はない。根拠: `engine/metal/src/engine/window.cpp:3096,3287-3308`。

## ログと測定値

初期化が成功すると stderr に `strata metal: prompts on the matrix units in chunks of ... (experts ..., QSA flash|v1, matmul2d layout K4|other; ... GB of buffers...)` の形式で選択結果を出す。明示値が無効でも警告は出ず、`flash` 以外はログ上 `QSA v1` となる。stream arena の確保に失敗した場合は `metal prompt: no arena region for the prompt buffers` をエラー文字列に設定して初期化失敗するが、これはこの変数の値の検証エラーではない。ソース資料から当該変数を使った性能測定値は確認できない。根拠: `engine/metal/src/engine/window.cpp:3117-3127`。

## 根拠

- `engine/metal/src/engine/window.cpp:3061-3066` — matmul2d layout 判定と対象変数の取得・比較。
- `engine/metal/src/engine/window.cpp:3096,3123-3127` — variant 別バッファ、初期化完了ログ。
- `engine/metal/src/engine/window.cpp:3287-3308` — flash / v1 の QSA kernel dispatch。
- `engine/metal/src/engine/window.cpp:1793-1808,3743-3775` — streaming 設定と prompt 経路の条件。
- `engine/metal/src/engine/prompt_chain.inc:26-46,49-60` — `COOP_K4` による `p.k4` 判定と別 prompt 実装。
