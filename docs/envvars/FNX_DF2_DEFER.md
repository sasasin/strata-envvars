# `FNX_DF2_DEFER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

split engine の batch decode で DFlash2 を使うとき、次の window に割り当てられた draft 数が 0 の lane について、DFlash2 の draft 呼び出しを一時延期するかを制御する。既定値は延期有効。延期中も window の tap 行は `df2_defer` で保存され、一定数の延期後には DFlash2 を呼び出す。生成 token や plan の選択規則をこの変数が直接変える処理はない（`engine/src/split/src/batch.cpp:260-292, 487-510`）。

この環境変数は Strata の `env_int` が直接読み取る。参照箇所は `engine/src/split/src/batch.cpp:493` の 1 箇所。

## 値と判定

`env_int` は `std::getenv` で値の有無を調べ、設定されていれば符号付き base-10 整数として文字列全体を `std::strtoll` で変換する。先頭の `+` / `-` は許されるが、空文字、前後の空白、数字以外を含む文字列、`long long` の範囲外はエラーになる。したがって `0anything` も無効。変換結果が 0 以外なら延期有効で、数値の上限・下限による追加制限はない（`engine/src/split/src/env.hpp:15-22, 33-40`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| batch の DFlash2 経路 | `1`（延期有効） | `1`, `-1`, `+2`（整数として非 0） | `0`, `00`（延期無効）。空文字、`true`, `0anything`, ` 1`, `9223372036854775808` は値の parse エラー |

無効な設定値は既定値へ戻らず、`FNX_DF2_DEFER: '<値>' is not a whole number` の `std::runtime_error` を送出する（`engine/src/split/src/env.hpp:33-40`）。

## 有効になる条件

- `BatchDecoder::draft_next` が batch drafts の `mtp` mode にあり、engine に DFlash2 が attach されていること。このとき batch 経路の drafter は DFlash2 と判定される（`engine/src/split/src/batch.cpp:262-267`）。
- その処理が `draft_df2` に到達すること。対象機能は CUDA/HIP GPU engine の DFlash2 実装であり、CMake は同 engine を CUDA または HIP 有効時に構成し、DFlash2 を定義する。Metal と SYCL はこの GPU engine の DFlash2 build 対象ではない（`engine/cmake/strata_gpu_engine.cmake:6-13`）。
- defer 値が非 0、当該 lane の `plan[g] == 0`、かつ `++L.idle < FNX_DF2_REFRESH`（既定 8）であること。plan が正数なら延期せず drafter を呼び、idle を 0 に戻す。refresh 到達時も延期せず drafter を呼ぶ（`engine/src/split/src/batch.cpp:491-510`）。

## 実行時の詳細

値は `draft_df2` の関数内 `static const bool` 初期化で初めて読むため、その関数の初回実行時に一度評価され、以後プロセス中の環境変更は反映されない。batch lane の `idle` は lane 開始時に 0 で初期化される（`engine/src/split/src/batch.cpp:40-58, 489-493`）。

延期条件を満たすと `e_.df2_defer(q)` を呼び、その lane を今回の `rq` から除外する。全 lane が除外されて `rq.empty()` ならそこで戻り、DFlash2 draft round は実行しない。延期しない lane は `e_.df2_draft(rq)` にまとめて渡され、実行後に idle を 0 に戻す（`engine/src/split/src/batch.cpp:496-511`）。

CUDA/HIP 実装の `df2_defer` は DFlash2 未接続や window 行範囲外を例外にし、lane ごとの pinned host ring を必要時に確保して対象 tap 行を device から host にコピーする。次の drafter 呼び出しで ring の文脈を取り込む処理がある（`engine/src/split/src/engine_common.cu:1699-1720, 1722-1743`）。DFlash2 なし build の stub は `df2_defer` を何もしない実装だが、通常の batch 分岐では `df2_on()` が真のときだけこの経路へ進む（`engine/src/split/src/engine_common.cu:1762-1768`, `engine/src/split/src/batch.cpp:265-267`）。

## ログと測定値

`FNX_DF2_DEFER` の判定や延期について専用ログは出さない。整数でない値は前述の `std::runtime_error` になる。Strata の `docs/SPLIT_ENGINE.md` はこの名前を DFlash2 の tester switch の一つとして列挙するが、値や具体的な処理は説明していない（`docs/SPLIT_ENGINE.md:83-85`）。この変数に関する測定値の記載はない。

## 根拠

- `engine/src/split/src/env.hpp:15-40` — 整数の構文、範囲検査、未設定時の既定値と parse error。
- `engine/src/split/src/batch.cpp:40-58, 260-292, 487-538` — batch DFlash2 経路、環境変数の cache、延期条件、再呼び出し。
- `engine/src/split/src/engine_common.cu:1699-1743, 1762-1768` — tap 行の保存と DFlash2 有無による実装。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — DFlash2 を含む CUDA/HIP engine の build 条件。
- `docs/SPLIT_ENGINE.md:83-85` — 文書上の DFlash2 起動条件と tester switch の記載。
