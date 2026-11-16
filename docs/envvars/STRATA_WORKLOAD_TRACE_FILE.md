# `STRATA_WORKLOAD_TRACE_FILE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は、診断用にコンパイルされた SYCL workload trace を追記するファイルのパスです。`Sink` がパスを `std::fopen(path, "a")` に渡し、処理区間や prefill phase の記録を JSON Lines 形式で書きます。これは計算結果を選ぶ設定ではなく、トレースの出力先を決めます。読み取りと書き込みの実装は `sycl/include/strata/workload_trace.hpp:34-50,61-75,76-115` にあります。

この機能は CMake の `STRATA_SYCL_WORKLOAD_TRACE` が有効な SYCL build に限られます。この build option 自体は既定で `OFF` で、有効時にトレースを使うソースへ `STRATA_SYCL_WORKLOAD_TRACE=1` を追加します。通常の非診断 build では同ヘッダー内の関数と `Scope` が no-op で、環境変数を読むコードもコンパイルされません（`sycl/CMakeLists.txt:31-44`; `sycl/include/strata/workload_trace.hpp:6-18,20-21,116-126`）。

## 値と判定

この変数は文字列の値を変換せず、パスとして使います。未設定または空文字ならファイルを開きません。空でない値ならその文字列をそのまま `"a"` モードの `fopen` に渡します。数値解析、真偽値判定、大小文字変換、空白除去、パス検証、fallback はありません。たとえば `trace.jsonl` や空白だけの値も非空パスとして渡されます（`sycl/include/strata/workload_trace.hpp:44-46`）。

| ビルド条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| `STRATA_SYCL_WORKLOAD_TRACE=ON` の SYCL build | ファイルなし。トレースを書かない | 空でない任意のパス文字列。追記モードで開けた場合に記録する | 空文字。`fopen` が失敗した場合も記録先は得られず、無効値として扱われる |
| 通常 build、または当該マクロなし | 読み取り自体がない | 該当なし | 該当なし |

`fopen` が失敗しても `Sink` は例外や警告を出さず `file == nullptr` のままです。その後の trace 呼び出しは出力先がないため記録しません（`sycl/include/strata/workload_trace.hpp:34-48,61-64,86-88`）。

## 有効になる条件

- CMake の SYCL build で `-DSTRATA_SYCL_WORKLOAD_TRACE=ON` が必要です。既定の `OFF` では変数は読み取られません（`sycl/CMakeLists.txt:31-44`）。
- build 内の workload trace 計測地点に処理が到達する必要があります。記録地点には request / prefill / decode の範囲や各種カーネルが含まれます（例: `sycl/src/program/generate.cpp:10704-10706,11192-11194,11334-11338,12371-12375`; `sycl/src/prefill/prefill.cpp:2573-2577,2609-2611,3130-3134`; `sycl/src/core/verify.cpp:1041-1045,1626-1632`）。
- `STRATA_WORKLOAD_TRACE_DECODE_ONLY` が設定され、空でなく、先頭文字が `'0'` でない場合、`phase()` の instant event はすべて抑制され、`Scope` は名前が `decode.` で始まるものか `request.decode` の場合だけ記録します。したがって `STRATA_WORKLOAD_TRACE_FILE` が有効でも、decode 以外の scope と prefill phase は出ません。空文字・`0`・`0anything` は decode-only を有効にしません（同ヘッダー `:40-41,61-64,86-89`）。
- `STRATA_WORKLOAD_TRACE_MIN_POSITION` が設定され、空でなければ `strtoll(..., nullptr, 10)` で読み取った値が最小 position になります。position がその値より小さい trace event は出ません。完全な数値検証はなく、変換できない文字列は `strtoll` の結果 0 となります。未設定・空文字では初期値 `-1` です（同ヘッダー `:37-43,61-64,86-88`）。
- CLI 引数による上書きや別ファイルへの fallback は、この変数の読み取り経路にはありません。

## 実行時の詳細

`Sink` は `sink()` の function-local `static` として最初の `phase()` または `Scope` 呼び出し時に一度だけ生成されます。その時点で `STRATA_WORKLOAD_TRACE_FILE`（および上記二つのフィルター変数）を読み、ファイルを開きます。以後の環境変数変更は再読込されず、ファイルの再オープンや失敗後の再試行もありません（`sycl/include/strata/workload_trace.hpp:34-50,61-64,84-89`）。

ファイルは append モードで開かれ、1 MiB の fully buffered I/O が設定されます。trace scope の完了時に duration 付きの `"ph":"X"` レコードを書き、prefill phase は `"ph":"i"` の instant レコードを書きます。レコードには `cat:"StrataCPU"`、イベント名、時刻、pid/tid、position / rows / layer などが含まれます（同ヘッダー `:46-47,61-75,96-108`）。request 処理の終端では `flush()` が呼ばれ、ファイルが開いていれば mutex の下で `fflush` します（`sycl/src/program/generate.cpp:12783-12785`; ヘッダー `:112-115`）。

## ログと測定値

標準出力・標準エラーに有効化やファイルオープン失敗を知らせるログはありません。出力は指定ファイルへの JSON Lines のみです。Strata の参照資料にこの変数の性能測定値は見つかりませんでした。コード上では診断 trace の書き込みに使われ、生成 token の決定を変更する分岐はありません（`sycl/include/strata/workload_trace.hpp:61-75,96-115`）。

## 根拠

- `sycl/include/strata/workload_trace.hpp:34-50` — 環境変数を読む唯一の箇所、値の判定、追記 open、buffering、static cache。
- `sycl/include/strata/workload_trace.hpp:61-75,76-115` — フィルター、記録形式、scope 完了時の書き込みと flush。
- `sycl/include/strata/workload_trace.hpp:116-126` — macro がない build の no-op 実装。
- `sycl/CMakeLists.txt:31-44` — SYCL 診断 build option の既定値と compile definition。
- `sycl/src/program/generate.cpp:10704-10706,11192-11194,11334-11338,12371-12375,12783-12785` — request/prefill/decode/verify の代表的な記録地点と request 終端 flush。
- `sycl/src/prefill/prefill.cpp:2361-2368,2573-2577,2609-2614,3130-3134`; `sycl/src/core/verify.cpp:1041-1045,1626-1632` — prefill phase・chunk/layer、decode layer の記録地点。
