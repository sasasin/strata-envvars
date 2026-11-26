# `FNX_ROPE_SCALE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Flash-Next（sFNX）エンジンで、GGUF の学習済み context 長を基準に YaRN RoPE scaling を指定する。scale `S > 1` なら rotary の位置計算を YaRN で変え、エンジンが受け付ける context 上限を原則 `max(学習済み長, floor(基準長 × S))` にする。これは位置表現自体を変えるので、要求 context が学習済み長以内でもスケールは適用される。値が未設定ならこの変数による scaling はなく、モデル自身の YaRN metadata があればそちらを使う。実装は `fnx::rope_scale()` と `fnx::Engine` の初期化処理にある（`engine/src/split/src/engine_common.cu:1025-1032`、`engine/src/split/src/engine.cu:40-64`、`engine/src/split/src/rope.hpp:82-113`）。

## 値と判定

`env_num` は設定有無を `getenv` で見てから、有限の十進数として文字列全体を parse する。符号、数字、小数点、指数表記は受理されるが、先頭空白、末尾の余分な文字、空文字、hex float、`inf` / `nan`、範囲外や underflow は数値 parse エラーになる。parse 後は `1` だけが scaling 無効として扱われ、`1` より大きい値が有効。0、負数、`1` 未満は scale 値エラーになる。上限値はコードで定めていない（`engine/src/split/src/env.hpp:24-30,42-48`、`engine/src/split/src/engine_common.cu:1025-1032`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `rope_scale()` の判定 | `0.0`（この変数による scaling なし） | `2`, `1.5`, `1e1` | 空文字・`true`・` 2`・`2x` は数値 parse エラー。`0`, `-1`, `0.5` は「want 1 (off) or a scale above 1」エラー。 |
| `sfnx --rope-scale S` | オプション省略時は環境の値を使う | 引数文字列を `FNX_ROPE_SCALE` に設定。環境値が未設定か、引数と文字列が完全一致なら受理 | 環境値が設定済みで引数文字列が異なれば不一致エラー。文字列比較なので、数値として同じでも表記が違えば不一致。 |

設定値 `1`（例: `1`, `1.0`, `1e0`）は parse 後に正確に `1.0` と等しい場合に限り無効扱い。入力の前後空白は許容されず、大文字小文字を使う真偽値形式はない。環境変数が空文字で設定されている場合は未設定扱いにならず、parse エラーとなる（`engine/src/split/src/env.hpp:15-30,33-48`; `engine/src/split/src/engine_common.cu:1025-1032`; `engine/src/split/tools/sfnx.cpp:94-102`）。

## 有効になる条件

- 対象は `engine/src/split` の Flash-Next sFNX Engine 経路。通常の Strata engine の `--rope-scale` と同じ実装であるとは、このコードからはいえない。
- `sfnx` の `--rope-scale` は引数 parse 中に環境へ設定される。環境変数が未設定なら任意の引数文字列を設定した後、scale として検証する。環境変数が既にあれば引数文字列との完全一致が必要（`engine/src/split/tools/sfnx.cpp:73-117`）。
- GGUF の `context_length` が正で `INT32_MAX` 以下であることがモデル読み込み条件。scale の基準長 `orig` はモデルに `original_context_length` があればそれ、なければ `context_length`（`engine/src/split/src/model.cpp:1338-1348`; `engine/src/split/src/rope.hpp:99-112`）。
- モデル自身の YaRN factor が `1` より大きい場合、環境変数が未設定ならそのモデル factor を使う。変数が設定されている場合は、値がモデル factor と数値として一致しないと拒否される。したがって `FNX_ROPE_SCALE=1` でモデル自身の YaRN を無効化することもできない（`engine/src/split/src/rope.hpp:82-93`）。
- `FNX_YARN_ORIG_CTX` はこの設定の基準長に関係する。設定時は整数 `1..INT32_MAX` が必要。モデルに `original_context_length` があれば一致が必要で、なければ学習済み `context_length` を超えられない。scale がモデルにも環境にもなく無効なら、`FNX_YARN_ORIG_CTX` のみの指定は拒否される（`engine/src/split/src/engine.cu:44-51`; `engine/src/split/src/rope.hpp:94-110`）。
- 設定した scale に対し `--max-context`（既定 `262144`）が RoPE の適用上限を超えると Engine の初期化に失敗する。上限は `max(ctx_train, (long long)(orig × S))`。逆に、scale が有効でも context 要求が学習済み長以内なら、上限だけが必要になるわけではないが、YaRN は適用され、stderr に注記が出る（`engine/src/split/tools/sfnx.cpp:65-69,88,116`; `engine/src/split/src/rope.hpp:111-113`; `engine/src/split/src/engine.cu:52-63`）。

## 実行時の詳細

`sfnx` は `parse_args()` で `--rope-scale` を `setenv` / `_putenv_s` に反映し、モデルのロード前に `fnx::rope_scale()` を呼んで不正値を検査する。モデル読み込み後、`Engine` constructor が再度環境変数の設定有無と数値を読み、モデルの YaRN metadata と `FNX_YARN_ORIG_CTX` を `choose_rope()` に渡す。環境値は関数内 static に cache されず、Engine を作るたびに読み直される。Engine 作成後にプロセス環境を書き換えても、既存 Engine の `rope_` と `max_ctx_` は再計算されない（`engine/src/split/tools/sfnx.cpp:94-117,1122-1135`; `engine/src/split/src/engine.cu:34-64`; `engine/src/split/src/engine_common.cu:1025-1032`）。

`fnx_run` の exactness/lab 経路も `rope_scale()` を呼んで run identity の build 行に有効 scale を記録し、scale 使用時には比較用 llama.cpp reference の案内に `FNX_ROPE_SCALE` と任意の `FNX_YARN_ORIG_CTX` を組み立てる。この文字列は案内・参照ファイル選択用で、ここで子プロセスに変数を注入する処理ではない（`engine/src/split/tools/fnx_run.cpp:388-418,831-871`）。

## ログと測定値

- `sfnx` の引数処理で値 parse または `rope_scale()` 判定が失敗すると、stderr に `sfnx: <理由>` を出して終了コード `2`。数値でない値の理由は `FNX_ROPE_SCALE: '<値>' is not a number`、数値だが `1` でも `>1` でもない値の理由は `FNX_ROPE_SCALE: want 1 (off) or a scale above 1, got <値>`（`engine/src/split/src/env.hpp:42-48`; `engine/src/split/src/engine_common.cu:1029-1032`; `engine/src/split/tools/sfnx.cpp:1110-1115`）。
- Engine 初期化でモデル factor との不一致や context 上限超過などが起きると、stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出し、終了コード `1` で終了する（`engine/src/split/tools/sfnx.cpp:1094-1103,1122-1135`）。
- scale が有効なら stderr に `fnx: rope scaling YaRN x%.4f%s: n_ctx_orig %lld, pairs %.0f..%.0f of %d blended, mscale %.4f` が出る。モデル factor 由来の場合 `%s` は ` (the model's own)`、環境指定由来なら空文字。環境指定由来で要求 context が学習済み長以内なら続けて `fnx: note: context %d is within the trained %d: the scaling changes every position's rotary and no length needs it` が出る。scale が無効ならこの scale ログは出ない（`engine/src/split/src/engine.cu:57-64`）。
- この調査では性能測定を行っていない。`FNX_ROPE_SCALE` の動作を定量化する測定値は記載しない。

## 根拠

- 数値 parse / 空文字等の判定: `engine/src/split/src/env.hpp:15-30,33-48`
- scale の既定値と境界: `engine/src/split/src/engine_common.cu:1025-1032`
- CLI からの設定、早期検証: `engine/src/split/tools/sfnx.cpp:73-117`
- YaRN の選択、model factor・original context との整合、適用上限: `engine/src/split/src/rope.hpp:82-113`
- Engine 初期化、context 拒否、実行時ログ: `engine/src/split/src/engine.cu:34-64`
- GGUF の学習済み長とモデル YaRN metadata: `engine/src/split/src/model.cpp:1338-1348`
- sFNX の起動時エラー出力: `engine/src/split/tools/sfnx.cpp:1094-1103,1107-1135`
- exactness/lab 用の読み取り・identity・reference 案内: `engine/src/split/tools/fnx_run.cpp:388-418,831-871`
