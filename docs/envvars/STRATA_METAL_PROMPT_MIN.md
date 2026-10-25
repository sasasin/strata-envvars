# `STRATA_METAL_PROMPT_MIN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンの非ストリーミング実行で、通常の decode window を使う代わりに、prompt 用の行バッチ処理 `Window::prompt()` を選ぶ最小 prompt token 数を指定します。既定値は 32 です。`STRATA_METAL_PROMPT=window` を指定した場合はこの切替を抑止し、prompt の長さにかかわらず decode window 経路を使います。

この変数はストリーミング実行の経路選択には使われません。streaming 時の prompt GEMM の閾値は別変数 `STRATA_METAL_PROMPT_GEMM_MIN` が決めます。

## 値と判定

`prompt_run_rows()` の初回呼び出し時に `getenv()` で値の有無を調べ、設定されていれば `std::atoll()` で符号付き整数に変換します。変換文字列全体の検査や値の clamp はありません。

| 値 | 判定結果 |
|---|---|
| 未設定 | 閾値 32 |
| 数値文字列 | 変換された整数を閾値にする。prompt token 数 `n` が閾値以上なら、後述の条件下で prompt 経路を選ぶ |
| 空文字、数値に変換できない文字列 | `atoll()` の結果 0 |
| 数字の後ろに文字がある値 | 数字として読める先頭部分を変換し、その後ろは判定しない（例: `64rows` は 64） |
| 負数 | 負の閾値をそのまま使う。非負の `n` は閾値以上になる |

先頭の空白や符号を含む文字列の扱いも `atoll()` に従います。無効値を既定値 32 に戻す処理はありません。

## 有効になる条件

閾値による切替が使われるのは、Metal の `Prefill::run()` から `prompt_run_rows()` に到達し、decode window が存在する場合です。次の条件をすべて満たすと `Window::prompt()` に進みます。

- `STRATA_METAL_PROMPT` が文字列全体として `window` ではない。
- window が streaming モードではない。
- prompt token 数 `n` が `STRATA_METAL_PROMPT_MIN` の閾値以上。

閾値未満、または `STRATA_METAL_PROMPT=window` の場合は、通常の window `run()` を最大 8 行ずつ実行し、各 chunk を `commit()` します。streaming モードではこの閾値を参照せず、`STRATA_METAL_PROMPT_GEMM` と `STRATA_METAL_PROMPT_GEMM_MIN` による別の分岐を試し、それも選ばれなければ同じ decode window 経路に進みます。

## 実行時の詳細

閾値は関数内の `static const int64_t` です。したがって、プロセスで最初に `prompt_run_rows()` が呼ばれた時点の環境値が保存され、以後の prompt 呼び出しや実行中の環境変更では再評価されません。

条件を満たした `Window::prompt()` は prompt 用の chunk 処理を実行します。chunk サイズは別の `STRATA_METAL_PROMPT_CHUNK` が制御し、この関数では既定 2048、64〜8192 の範囲に収めています。フォールバック経路は `MAXT=8` の decode window を使います。`STRATA_METAL_PROMPT_MIN` 自体に専用ログ出力はありません。

`docs/MAC.md` は `STRATA_METAL_PROMPT=window` を遅い exact fallback として紹介し、`STRATA_METAL_PROMPT_CHUNK` を prompt chunk size の設定として記載していますが、`STRATA_METAL_PROMPT_MIN` の閾値や値変換規則は説明していません。性能値は本調査では追加測定していません。

## 根拠

- `src/prefill/prefill.cpp:4338-4349` — Metal build では prefill を `strata::metal_engine::prompt_run()` に渡す。
- `metal/src/engine/window.cpp:52` — decode window の最大 token 数 `MAXT` は 8。
- `metal/src/engine/window.cpp:2545-2559` — `prompt_run_rows()`、`STRATA_METAL_PROMPT=window` の完全一致判定、閾値の `atoll()` 変換と既定値 32。
- `metal/src/engine/window.cpp:2560-2586` — 非 streaming 時の閾値分岐、streaming 時の別環境変数による分岐、および decode window fallback。
- `metal/src/engine/prompt_chain.inc:394-420` — 選択先 `Window::prompt()` の chunk 処理と専用 profile/trace ログ条件。
- `metal/src/engine/prompt_chain.inc:396-400` — `STRATA_METAL_PROMPT_CHUNK` の既定値・clamp。
- `docs/MAC.md:183-190` — Mac の環境変数一覧にある関連スイッチの説明。
