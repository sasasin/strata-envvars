# `STRATA_ADAPT_PICK_INLINE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--adapt-async 1` の adaptive tier が arena mode で swap 候補を選ぶ処理を、decode loop の tick を処理するスレッド上で実行するか、job thread に渡すかを切り替えます。候補選択の規則や swap 上限を変える変数ではなく、選択処理を実行するスレッドを選びます。

## 値と判定

共通 helper `a_env()` は、環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を返します。この変数の既定値は `1` です。変換後の整数が 0 以外なら inline が有効です。

| 値の例 | `a_env()` の結果 | 選択処理 |
|---|---:|---|
| 未設定、空文字 | 既定値 `1` | inline |
| `1`, `-1`, `2` | 0 以外 | inline |
| `0`, `false`, `x` | `0` | job thread |
| `1tail` | 数値 prefix の `1` | inline |

`atoi()` は文字列全体の妥当性を検査せず、数値として読める先頭部分を変換します。先頭の空白や符号も `atoi()` の規則で処理されます。従って `false` は真偽値文字列としては扱われず、数値を読めないため 0 になります。読み取り結果は `a_inline` に一度保存され、同じ adaptive tier の間は再評価されません。

根拠: `src/program/generate.cpp:9062-9068`。

## 有効になる条件

この変数が読み取られるのは `a_arena` が true の場合だけです。`a_arena` は `srcp == &arena_src` で判定されます。さらに `ajob`（asynchronous adaptive tier）が作られるには `--adapt-async` が有効で、usage table が空でなく、resident RAM mode または arena mode である必要があります。非同期 tier は `--serve` で適応層（正の `--adapt-every` と `--adapt-swaps`）が有効な場合に限られます。arena mode では layer split と `--pipeline-windows 2` は無効条件です。ほかに `--batch-groups`、`--peer-device`、`--remote-expert-opt` などの制約で `--adapt-async` が無効化される場合もあります。

arena 以外では `a_arena && a_env(...)` の短絡評価により環境変数を読みません。`--adapt-async` が無効なら、この設定が 1 でも選択処理の実行場所には影響しません。

根拠: `src/program/generate.cpp:6978-6994,9057-9078`。

## 実行時の詳細

swap round の開始時、inline が有効なら現在の tick 内で `a_pick()` を直接呼び、その後の状態を copy-in に進めます。無効なら `a_choose()` を job thread に post します。`a_choose()` は同じ `a_pick()` を呼び、続けて必要な copy-back 処理を行います。arena 経路では copy-back 対象はなく、その後 copy-in に進みます。arena 経路では `--pipeline-windows 2` が無効条件のため、pipelined loop はこの設定の実行経路に含まれません。

この値は `main()` の adaptive tier 初期化時に通常の `getenv()` で一度読み取られ、`static` cache は使いません。初期化後に環境変数を書き換えても再評価されません。選択場所を変えるログは、arena の非同期 tier が最後に出す累積統計行に `pick inline` または `pick on the job` として含まれます。inline の場合だけ選択処理の所要時間 `a_pick_ms` を計測し、job thread の場合はこの値を計測しません。

根拠: `src/program/generate.cpp:9272-9286, 9095-9129, 9183-9187, 13025-13034`。

## 資料との照合

`docs/DETAILS.md` は arena の `--adapt-async 1` 経路について、既定では `STRATA_ADAPT_PICK_INLINE=1` とし、選択を host thread 上で行うと説明しています（`docs/DETAILS.md:180-187`）。ソースの helper の既定値 1 と一致します。同資料には RTX 3090 + Ryzen 5 5600X での arena 非同期 tier 全体の cold-prompt 測定として x1.07–1.11、12 回中 12 回で高速だったとの記載がありますが、`STRATA_ADAPT_PICK_INLINE` 単独の効果を分離した測定ではありません。

## 根拠

- `src/program/generate.cpp:9057-9078` — arena 判定、値の読み取り、非同期 tier の初期化条件。
- `src/program/generate.cpp:9272-9286` — inline と job thread の分岐。
- `src/program/generate.cpp:9095-9129,9183-9187` — 候補選択と job thread 側の処理。
- `src/program/generate.cpp:13025-13034` — arena 非同期 tier の統計ログ。
- `docs/DETAILS.md:180-187` — arena 非同期 tier の説明と測定条件。
