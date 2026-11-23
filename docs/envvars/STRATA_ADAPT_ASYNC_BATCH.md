# `STRATA_ADAPT_ASYNC_BATCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP の `strata serve` にある非同期 adaptive tier のうち、expert arena から GPU expert cache へコピーする際、1 バッチにまとめる copy-in の最大件数を指定する。これは swap 候補数や 1 ラウンド全体の上限ではなく、コピーを複数バッチに分ける上限である。`0` は全件を 1 バッチにする。arena 以外の resident RAM モードでは `a_batch` を常に `0` にするため、この変数は参照されても実際の分割数に影響しない（`engine/src/program/generate.cpp:15489-15502,15632-15646`; 分割規則は `engine/include/strata/program/adaptive_range.hpp:18-40`）。

## 値と判定

`generate.cpp` 内の `a_env` が `std::getenv` で値を取得する。未設定または空文字なら既定値を返し、それ以外は `std::atoi` で変換する。その後 `std::max(0, ...)` で負値を `0` にし、`size_t` に変換する。全体の文字列検証はなく、`atoi` が読む先頭の数値部分が使われ、数値にできない文字列は `0` となる。従って `2tail` は `2`、`true` / `false` / `junk` / `0anything` は `0` として扱われる。符号と先頭空白も `atoi` の変換対象になる。`atoi` の表現範囲を超える値の結果は保証できない（`engine/src/program/generate.cpp:15494-15497,15502`）。

| 条件 | unset | 有効になる値（例） | 無効・その他の値（例） |
| --- | --- | --- | --- |
| expert arena (`a_arena == true`) | `0`（全件を 1 バッチ） | 正の整数。例 `1` は 1 件ずつ、`16` は最大 16 件ずつ | 空文字も既定値 `0`。`0`, `-1`, `true`, `junk`, `0anything` はすべて `0`（全件を 1 バッチ） |
| arena 以外 | 適用なし。`a_batch` は `0` | 適用なし | 設定値はバッチ分割に使われない |

正の上限が残りの swap 件数以上なら、そのバッチで残り全部を処理する。値が無効でも警告や fallback ログはなく、変換結果 `0` の通常規則（全件を 1 バッチ）が適用される（`engine/include/strata/program/adaptive_range.hpp:24-31`）。

## 有効になる条件

- `srcp == &arena_src` の expert arena であること。expert arena 以外ではこの変数の値を使わない（`engine/src/program/generate.cpp:15489-15502`）。
- 非同期 adaptive tier が実際に動くこと。tier は `--serve` と有効な adaptive 設定（`--adapt-every` / swap 数）を必要とし、`--adapt-async` または自動選択などが別途 tier の起動を決める。この変数自体は tier を有効化しない（`engine/src/program/generate.cpp:11675-11732,15503-15517`; 自動選択条件は `engine/include/strata/core/adapt_async_default.hpp:19-60`）。
- arena の `--pipeline-windows 2` は非同期 adaptive tier の対象外。pipeline 用の arena copy-in 経路では全 round がひとつのバッチになるため、通常の `a_batch` 分割は使われない（`engine/src/program/generate.cpp:11717-11732,15762-15769`; `engine/include/strata/program/adaptive_range.hpp:33-37`）。
- resident RAM モードでは非同期 tier が利用可能でも `a_batch` は `0` 固定であり、この変数は無効（`engine/src/program/generate.cpp:15491-15502`）。

この値の判定自体に OS 別分岐はない。Windows の AMD/HIP で非同期 tier を拒否する場合など、tier の別の起動条件により copy-in 自体が実行されない経路はある（`engine/src/program/generate.cpp:11682-11690`）。

## 実行時の詳細

`a_batch` は adaptive tier の状態・job thread を準備する際に一度計算され、関数内に保持される。リクエストや decode tick ごとに環境を読み直す処理、プロセス起動後の環境変更を再取得する処理はない（`engine/src/program/generate.cpp:15494-15512`）。

serial loop では `a_post_batch` が `AdaptiveCopyRange::next_batch` に上限を渡し、job thread が指定範囲の arena blob を GPU cache slot へ非同期コピーする。コピー完了後にその範囲を resident として反映し、残りがあれば次のバッチを投入する。従って正の値は同時にキューへ送る copy-in 件数を区切り、`0` はラウンドの残りをまとめる（`engine/src/program/generate.cpp:15593-15625,15632-15646,15778-15795`; `engine/include/strata/program/adaptive_range.hpp:24-40`）。

## ログと測定値

arena で `ajob` がある場合、リクエスト終了時の累積ログに ` (arena, copy-in only, batch %zu, wait %d, pick %s %.2f ms/round)` と表示され、`batch` がこの変数から計算された値（未設定時は `0`）を示す。起動時にこの値だけを理由とするログや無効値警告はない（`engine/src/program/generate.cpp:23704-23713`）。

`docs/DETAILS.md` は `--adapt-async` の概要と別変数の測定記録を載せるが、この batch 上限の値ごとの測定値は記載していない（`docs/DETAILS.md:274-276,1648-1651`）。

## 根拠

- 読み取り、既定値、arena 条件: `engine/src/program/generate.cpp:15489-15507`
- copy-in と batch 分割: `engine/src/program/generate.cpp:15593-15646,15778-15795`; `engine/include/strata/program/adaptive_range.hpp:18-44`
- 非同期 tier の適用条件: `engine/src/program/generate.cpp:11675-11732`; `engine/include/strata/core/adapt_async_default.hpp:19-60`
- 観測ログと設計資料: `engine/src/program/generate.cpp:23704-23713`; `docs/DETAILS.md:274-276,1648-1651`
