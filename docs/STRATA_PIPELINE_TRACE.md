# `STRATA_PIPELINE_TRACE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。作業ツリーには調査対象外の `bench/results/2026-10-12-community-ai-pro-r9700-qwen3-8-flash-next-iq2-xs/` の未追跡データがある。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の pipeline windows decode loop が発生させるイベントと、その loop 開始からの経過ミリ秒をファイルに追記します。これは診断トレースで、pipeline の選択や生成処理を変更する値ではありません。

## 値と判定

この変数は `pipe_dbg_env("STRATA_PIPELINE_TRACE")` 経由で読み取られます。同 helper はまず `STRATA_PIPELINE_DEBUG` を判定し、無効なら対象変数を読まず `nullptr` を返します。debug gate の判定は helper 内の `static const bool` に一度だけ保存されます。

| `STRATA_PIPELINE_DEBUG` の値 | `STRATA_PIPELINE_TRACE` の扱い |
|---|---|
| unset または空文字 | 無効。helper は `nullptr` を返す |
| 先頭文字が `0` | 無効（例: `0`, `0anything`） |
| 空でなく先頭文字が `0` 以外 | 有効（例: `1`, `true`, `false`, `2`）。文字列全体や数値としての妥当性は検査しない |

gate が有効なとき、`STRATA_PIPELINE_TRACE` が unset ならトレースしません。設定値はパスとして扱い、真偽値や数値には変換しません。空文字は非 null の値ですが、後段で `fopen("", "a")` が失敗するためファイル出力されません。パスの形式や書き込み権限などの検証はありません。

## 有効になる条件

- pipeline windows decode loop が実行されることが必要です。`--pipeline-windows` の要求がない場合や、要求が実行条件を満たさず無効化された場合は、この loop 内のトレース初期化・記録処理に到達しません。
- `STRATA_PIPELINE_DEBUG` gate が有効であることが必要です。これが無効なら `STRATA_PIPELINE_TRACE` は無視されます。
- `src/program/generate.cpp` の CUDA/HIP系実装と `sycl/src/program/generate.cpp` のSYCL実装の双方に同じ機構があります。

## 実行時の詳細

pipeline loop に入ったとき `pl_trace_path` を static 初期化し、以降の loop invocation でもそのポインタを使います。したがって、プロセス起動後に `STRATA_PIPELINE_DEBUG` を変更しても gate の判定は変わらず、`STRATA_PIPELINE_TRACE` の変更も `pl_trace_path` 初期化後には反映されません。

イベント記録時には `%.3f %s %d %d %d\n` の形式で、loop 開始からの経過時間（ミリ秒、小数3桁）、イベント名、sequence 番号、整数引数2つをメモリ上の文字列に追加します。実装には、window の完了・launch（`F0`, `L0`, `L1`）、commit/undo（`CE`, `CD`, `CL`, `U`）、検証結果（`V`）などの記録箇所があります。各イベントが記録されるのはそのコード箇所を通ったときだけです。

loop を drain した後、記録がありパスが非 null なら `fopen(path, "a")` で追記モードにし、`# request p0=<n-1>` の行とイベント列を書き込みます。ファイルを開けない場合は何も書かず、戻り値も確認しないため、書き込み失敗はこの処理からログやエラーとして報告されません。request ごとに loop 経過時間の基準を取り直します。

## 根拠

- `src/program/generate.cpp:251-257`, `sycl/src/program/generate.cpp:293-298` — pipeline debug 用 env helper。設定有無と先頭文字による gate 判定、および gate の static cache。
- `src/program/generate.cpp:10531-10543` — helper の他の利用例。`STRATA_PIPELINE_*` 変数群は helper 経由で参照されます。
- `src/program/generate.cpp:11261-11270`, `sycl/src/program/generate.cpp:10543-10553` — トレースパスの static cache、経過時間とイベント行の生成。
- `src/program/generate.cpp:11285`, `11427`, `11479`, `11503`, `11532`, `11599`, `11647`, `11689`, `11719`; `sycl/src/program/generate.cpp:10566`, `10746`, `10790`, `10818`, `10847`, `10910`, `10956`, `10995`, `11020` — イベントの記録箇所。
- `src/program/generate.cpp:11762-11778`, `sycl/src/program/generate.cpp:11055-11069` — loop の drain 後に request 見出しとトレースを append する処理。
- `docs/DETAILS.md` を確認したが、`STRATA_PIPELINE_TRACE` の説明や測定値は見つからなかった。
