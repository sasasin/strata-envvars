# `STRATA_ADAPT_ASYNC_BATCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena を使う非 pipeline の非同期 adaptive tier で、1 回に GPU へ投入する expert の copy-in 件数に上限を設けます。0 は上限なしで、その round に選ばれたコピーを一度に投入します。この変数は adaptive tier 自体を有効化せず、コピー元や expert の選択方法も変えません。

コード上の読み取りは `src/program/generate.cpp` の `a_env("STRATA_ADAPT_ASYNC_BATCH", 0)` だけです。`000_envvers.md` にある候補名はこの読み取りで実際に使われています。bench/results 以下にも値を設定する実験スクリプトがありますが、実装根拠にはしていません。

## 値と判定

`a_env` は環境値が存在し、かつ空文字でない場合に `std::atoi` を使います。それ以外は既定値を返します。その後 `std::max(0, ...)` で負値を 0 にし、`size_t` に変換します。

| 環境値 | 読み取り結果 | copy-in 上限 |
|---|---:|---:|
| 未設定 | 既定値 `0` | 上限なし。残りの swap をまとめて投入 |
| 空文字 | 既定値 `0` | 上限なし |
| 数値 0 | `0` | 上限なし |
| 正の整数 `N` | `atoi` の結果 `N` | 1 batch あたり最大 `N` 件 |
| 負の整数 | `atoi` の負値を `max(0, ...)` で `0` にする | 上限なし |
| 数字以外で始まる文字列 | `atoi` が通常 0 を返す | 上限なし |
| 数字の後ろに文字が続く文字列 | `atoi` が先頭の数値部分を変換 | その正値を上限にする。例: `16x` は 16 |

整数全体の厳密な書式検査、末尾文字の検証、範囲エラーの警告はありません。`atoi` が `int` で表せない値を受け取った場合の結果は、この実装で定義・検査されていません。

根拠: `src/program/generate.cpp:11689-11697`。

## 有効になる条件

- 上限が適用されるのは `srcp == &arena_src`、つまり expert arena 経路の場合です。arena 以外では `a_batch` を明示的に 0 にします。
- 非同期 adaptive tier の job が作られ、実際に `a_post_batch()` が呼ばれる必要があります。明示的な `--adapt-async 1`、または対応条件下での自動選択が必要で、adaptive tier の swap がなければ対象コピーもありません (`src/program/generate.cpp:11700-11716,11901-11916`)。
- 自動選択は CUDA build、`--serve`、adaptive tier 有効、arena、単一 GPU、pipeline 無効、batch slots 無効、peer / remote expert opt 無効、overlap 無効の条件を満たす場合だけ候補になります。`STRATA_ADAPT_ASYNC=0` は自動選択を止めます。`--adapt-async` を明示した場合は自動選択ではなく明示値が使われます (`src/program/generate.cpp:9026-9045`, `include/strata/core/adapt_async_default.hpp:19-55`)。
- `--adapt-async 0` では async tier を明示的に無効にするため、この上限は使われません。HIP build では自動選択されません (`include/strata/core/adapt_async_default.hpp:21-23,43-55`)。
- pipeline のコピー投入 (`a_stage_in` / `a_in`) は `a_batch` を参照せず、各 stage の gap にその stage のコピーを投入します。arena の async tier は `--pipeline-windows 2` と併用できず、無効化されます (`src/program/generate.cpp:9047-9062,11845-11855`)。

## 実行時の詳細

環境変数は server の adaptive state 初期化時に一度読み、ローカルの `const size_t a_batch` に保持されます。static cache ではありませんが、同じ engine/server 実行中に環境を書き換えても再読込する箇所はなく、変更は次回の初期化まで反映されません (`src/program/generate.cpp:11686-11697`)。

arena の逐次経路では、`a_post_batch()` が `a_lo` から `a_hi` までの範囲を次の copy-in batch にし、job thread に `a_copy_in()` を投稿します。`a_batch > 0` なら `a_hi = min(aswaps.size(), a_bi + a_batch)`、0 なら残り全部です。batch のコピー完了後に residency table を更新し、swap が残っていれば次の batch を投稿します (`src/program/generate.cpp:11827-11843,11972-11989`)。したがって正値は round 全体の swap 数を制限せず、各 batch の件数を制限します。

async tier の初期化があると stderr の累積統計に `arena, copy-in only, batch %zu` と実際の `a_batch` が出ます (`src/program/generate.cpp:17510-17518`)。値の形式が不正でもこの環境変数自体についての警告はありません。copy 元を読めない場合は `adaptive tier: layer ... could not be read`、GPU copy の投入に失敗した場合は `adaptive tier: copy of layer ... failed: ...` が stderr に出て、decode 側へ `ERR an adaptive refill failed` を返す経路があります (`src/program/generate.cpp:11798-11807,11810-11820,17083-17085`)。

## 根拠

- `src/program/generate.cpp:11686-11697` — arena 判定、helper の変換、既定値、適用値の生成。
- `src/program/generate.cpp:11827-11843` — batch 範囲と上限の適用。
- `src/program/generate.cpp:11972-11989` — batch 完了後の residency 更新と次 batch の投稿。
- `src/program/generate.cpp:9026-9045`, `include/strata/core/adapt_async_default.hpp:19-55` — async 自動選択条件と `STRATA_ADAPT_ASYNC` / CLI との関係。
- `src/program/generate.cpp:9047-9062,11845-11855` — pipeline 経路の条件と、batch 上限を通らないコピー投入。
- `src/program/generate.cpp:17510-17518` — arena async tier の統計ログ。
- `src/program/generate.cpp:11798-11820,17083-17085` — コピー読み取り・投入失敗と decode 側のエラー。
