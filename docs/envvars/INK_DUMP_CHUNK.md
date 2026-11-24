# `INK_DUMP_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling` の `--dump-ref` 実行で、teacher-forced の参照 logits を計算するときに、入力 token を `forward_batch` へ何個ずつ渡すかを指定する。既定は全 token を一度に渡す。`1` なら一度に 1 token ずつ処理する。値を使うのは `cmd_dump_ref` だけであり、通常の生成、`--serve`、`--bench`、`--kld-eval` などの batch サイズを設定する環境変数ではない（`engine/src/inkling2/ink_main.cpp:325-357, 1039-1043`）。

## 値と判定

`cmd_dump_ref` 内で `std::getenv` により設定有無を確認し、設定されている場合は `std::atoi` の結果が正数のときだけ採用する。既定値は `n_tok`（今回の入力 token 数）、有効な値は `min(atoi(値), n_tok)`。文字列全体の検証や数値変換エラーの確認はないため、`atoi` が先頭の数値部分を変換し、後続文字を無視する値も受理される。例として `2junk` は 2、`2.5` は 2、`0anything` は 0 として扱われる。空文字と数値に変換できない文字列は `atoi` が 0 を返すため既定値のまま。0 と負数も採用されず、正数は `n_tok` を超えても `n_tok` に制限される。明示的な上限外・整数変換エラーの検査はない（`engine/src/inkling2/ink_main.cpp:342-350`）。

| 条件 | unset | 有効になる値（例） | 無効・既定値になる値（例） |
|---|---|---|---|
| `--dump-ref` の処理 | `n_tok`（全 token を一括） | 正数に変換される値。`1`, `+2`, `2junk`。上限は `n_tok` | 空文字、`0`, `-1`, `false`, `abc`, `0anything` は `atoi` 結果が正でないため `n_tok` |

この判定は大文字小文字を比較せず、空白を trim する処理も独自には行わない。`atoi` の変換規則により、先頭の空白と符号付き数値は変換対象になり、数値の後ろは検査されない。

## 有効になる条件

- `strata-inkling` が `--dump-ref OUT` を受け取り、引数処理後に `dump_ref` が空でない場合に `cmd_dump_ref` が呼ばれる。`--kld-eval` を選んだ場合は別関数へ進み、この値は読まれない（`engine/src/inkling2/ink_main.cpp:866-870, 1039-1043`）。
- `cmd_dump_ref` はモデルを開き、選択された backend を初期化して slot を確保した後にこの値を読む。従ってこれらの処理に失敗した場合、値の判定や chunk 処理には到達しない（`engine/src/inkling2/ink_main.cpp:326-335, 347-357`）。
- `--prompt-ids` が空なら既定の8 token、指定されていれば parse 成功した token 列が対象になるため、chunk の最大値もその `n_tok` で決まる（`engine/src/inkling2/ink_main.cpp:336-344, 957-963`）。
- `--chunk` は `cfg.bopts.chunk` を設定するが、`cmd_dump_ref` の chunk 判定はそれを参照しない。`INK_DUMP_CHUNK` が未設定または無効でも、`--chunk` の値ではなく全 token 一括になる（`engine/src/inkling2/ink_main.cpp:347-350, 879-881`）。
- 調査した環境変数参照に OS / backend / build macro の条件分岐はない。backend の選択自体は `make_default_backend(force_cpu, &bopts)` に渡される設定に従う（`engine/src/inkling2/ink_main.cpp:326-335`）。

## 実行時の詳細

値は `cmd_dump_ref` の実行中、logits 用 buffer の確保後に一度読み、環境変数の値を static cache には保存しない。決定した `dump_chunk` ごとに `i0` を進め、範囲 `[i0, min(i0 + dump_chunk, n_tok))` の token を `StepBatch` に積んで `forward_batch` を呼ぶ。各 batch の logits は対応する token 位置の buffer offset へ書き込まれ、その後すべての token IDs と logits を指定ファイルへ出力する（`engine/src/inkling2/ink_main.cpp:342-363`）。

この値を読み直すループはなく、同じ `cmd_dump_ref` 呼び出しの途中で環境が変化しても chunk は変わらない。別のプロセス実行ではその実行時の環境が判定される。コード上、chunk 数を `cfg.bopts.chunk`、CLI の `--chunk`、または別環境変数と合成する処理はない（`engine/src/inkling2/ink_main.cpp:347-353, 879-881`）。

## ログと測定値

有効・無効な環境値自体を報告するログはない。各 `forward_batch` が失敗すると stderr に `forward: <backend error>` を出して終了コード 1 を返す。dump ファイルを開けない場合は `dump-ref: cannot write <path>` を出して 1 を返し、成功時は stdout に `[dump-ref] wrote <path> (n_tok=<n>, V=<v>, backend=<name>)` を出す（`engine/src/inkling2/ink_main.cpp:353-365`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:325-357` — `cmd_dump_ref` のモデル/backend 初期化、token 数と既定 chunk、環境値の判定、batch 処理、出力とエラー。
- `engine/src/inkling2/ink_main.cpp:866-870, 1039-1043` — `--dump-ref` の引数取得とコマンド分岐。
- `engine/src/inkling2/ink_main.cpp:879-881` — `--chunk` が別設定であること。
- `engine/src/inkling2/ink_main.cpp:957-963` — `--prompt-ids` の指定と `@file` 展開。
