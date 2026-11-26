# `STRATA_METAL_PROMPT_GEMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal engine の expert streaming 時に、prompt を decode window で処理するか、matrix units 用の prompt GEMM で chunk ごとに処理するかを切り替える。未設定を含め `"0"` 以外なら GEMM 側を選べる状態になる。無効化時は decode window の通常経路に戻る。prompt GEMM と decode window ではコメント上、数値が異なる（GEMM の重みを chunk ごとに fp16 化する実装）とされるが、token の同一性を保証する比較はこのコードからは確認できない。実装は `Window::stream_arena` と `prompt_run_rows`（`engine/metal/src/engine/window.cpp`）。

## 値と判定

| 読み取り箇所 | unset | GEMM を許可する値 | GEMM を止める値 |
|---|---|---|---|
| `Window::stream_arena` の arena 構築時 | ON | `"0"` 以外すべて（空文字を含む） | 文字列全体が `"0"` |
| `prompt_run_rows` の各 prompt 呼び出し時 | ON | `"0"` 以外すべて（空文字を含む） | 文字列全体が `"0"` |

両方とも `std::getenv` の結果が null かを確認し、値がある場合は `std::string(e) == "0"` の完全一致だけを無効扱いにする。数値変換や trim、大文字小文字の正規化はない。そのため `0anything`、`00`、`false`、`1`、空文字は ON、unset も ON。読み取り時点が異なるため、実行中に環境を書き換えると以後の prompt 分岐は変わり得る一方、すでに構築した arena の設定は変わらない（下記参照）。

`window.cpp:3025-3035` にも同じ名前を読む `Window::prompt_gemm_on` があるが、現行 checkout 内に呼び出し箇所は見つからない。この関数では結果を関数内 `static` に保存し、未設定を ON、完全一致 `"0"` を OFF と判定する。実際の prompt 分岐はこの helper を使わず、毎回環境を読み直す（`window.cpp:3743-3754`）。

## 有効になる条件

- Metal engine の `Window` を使い、`ExpertStream::wanted` が true となって `stream_` が有効であること。これは `STRATA_METAL_STREAM=1` で強制でき、`=0` で無効化できる。それ以外はモデル等の resident footprint 判定による（`engine/metal/src/engine/window.cpp:736-743`、`engine/metal/src/engine/stream.cpp:34-49`）。
- prompt 呼び出し時に `STRATA_METAL_PROMPT` が完全一致 `window` でないこと。`window` ならこの GEMM 分岐を通らず decode window 経路へ進む（`window.cpp:3745-3753`）。
- `STRATA_METAL_PROMPT_GEMM_MIN` が unset の場合は `n >= 64`、設定時は `std::atoll` の結果に対して `n >= 値` を満たすこと。`atoll` は先頭の空白と符号の後にある10進数部分を読み、後続文字列を検証しないため、`64tail` は 64、`-1` は -1 になる。空文字や数値で始まらない文字列（例: `abc`）は 0 となり、`0` なら `n >= 0` で通る。値の parse 失敗に対する警告や fallback はない（`window.cpp:3750-3754`）。
- prompt GEMM の初期化が成功すること。初期化失敗時は `prompt_run_rows` が false を返し、エラー文字列を呼び出し元へ返す。streaming arena に prompt buffer 用 region がなければ `metal prompt: no arena region for the prompt buffers` が設定される（`window.cpp:3037-3040, 3116-3128, 3754-3755`）。

非 streaming の Metal prompt は `STRATA_METAL_PROMPT_MIN` を基準とする別の `Window::prompt` 経路であり、この変数はその選択条件ではない。上記の streaming 条件はモデル容量と `STRATA_METAL_STREAM` の設定に依存し、CLI の prompt 長条件には `STRATA_METAL_PROMPT_GEMM_MIN` が関与する（`window.cpp:3746-3754`）。

## 実行時の詳細

`Window` 構築時に `ExpertStream::wanted` で streaming の有無が決まり、streaming の arena を作る際にこの変数を読み取る。値が `"0"` 以外なら `ExpertStream::make_arena` に渡す slot 数を 576、`"0"` なら 64 とし、前者は arena 構築後に prompt GEMM buffer の初期化も行う。後者では初期化を呼ばない（`engine/metal/src/engine/window.cpp:1726, 1793-1808`）。

その後、streaming prompt ごとに `prompt_run_rows` が環境変数を再読し、未設定または `"0"` 以外かつ長さ条件を満たせば prompt GEMM を初期化（未初期化の場合）し、`C` 行以下の chunks に分割して `prompt_chunk` を実行する。初期化済みの場合は既存の `pg_` を再利用する。`C` の既定値は `STRATA_METAL_PROMPT_CHUNK` または streaming と物理 RAM に基づく別ロジックで決まり、この変数は chunk サイズを指定しない（`window.cpp:3037-3049, 3116-3128, 3749-3765`）。

GEMM 分岐に入らないときは `MAXT` 以下の単位で `Window::run`、`commit`、`tap_deliver_dec` を呼ぶ decode window 経路へ進む。GEMM 側では各 chunk の `prompt_chunk` と `on_chunk` の結果が失敗するとループを止め、その結果を返す（`window.cpp:3759-3775`）。この変数に対応する専用の警告や失敗ログはない。成功時は prompt GEMM 初期化時に `strata metal: prompts on the matrix units in chunks of ...` が出る。失敗文字列には `metal prompt: chunk size out of range`、`metal prompt: the chunk runs past the context` などがあり、呼び出し元へ返される（`window.cpp:3120-3128, 3131-3139`）。

## 根拠

- `engine/metal/src/engine/window.cpp:1726-1729, 1793-1808` — streaming arena 内の値判定、slot 数、初期化呼び出し。
- `engine/metal/src/engine/window.cpp:3023-3035` — prompt GEMM 判定 helper と cache。ただし現行コードで呼び出しなし。
- `engine/metal/src/engine/window.cpp:3037-3049, 3116-3128` — prompt GEMM 初期化、buffer region 条件、初期化ログ。
- `engine/metal/src/engine/window.cpp:3735-3775` — streaming prompt ごとの値読み取り、優先経路、chunk 実行と decode window fallback。
- `engine/metal/src/engine/window.cpp:736-743` — streaming 状態の決定。
- `engine/metal/src/engine/stream.cpp:28-49` — `STRATA_METAL_STREAM` と自動 resident 判定。
