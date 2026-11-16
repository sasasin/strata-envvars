# `STRATA_WORKLOAD_TRACE_DECODE_ONLY`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は、任意の SYCL workload trace の出力対象を decode 区間に絞る診断用フラグです。設定すると `Scope` が `decode.` で始まるラベルと `request.decode` 以外を記録対象外にし、`phase()` の即時イベントも記録しません。decode の計算や token 選択を切り替える処理はこの変数の読み取り箇所にはありません。`sycl/include/strata/workload_trace.hpp:38-45,61-64,84-89`

通常の実行では `STRATA_SYCL_WORKLOAD_TRACE` が未定義のため trace API は no-op です。CMake の `STRATA_SYCL_WORKLOAD_TRACE` オプションは既定で `OFF` で、`ON` のときに限り trace 実装を含む指定ソースへ macro を付けます。`sycl/CMakeLists.txt:31-44` ビルド時のこの CMake オプションと実行時の環境変数は別の設定です。

## 値と判定

`Sink` の初回生成時に `std::getenv` で値を読み、未設定でなく、空文字でなく、先頭文字が `'0'` でなければ有効です。文字列全体の parse や真偽値検証はしません。先頭文字だけを見るため、大文字小文字や後続文字は判定されず、先頭の空白も取り除かれません。`sycl/include/strata/workload_trace.hpp:34-45`

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_SYCL_WORKLOAD_TRACE` を定義して trace 実装をビルド | decode 限定なし | 先頭が `0` 以外の任意の非空文字列（例: `1`, `true`, `false`, ` 0`） | 空文字、`0`, `00`, `0anything` |
| macro なし（CMake 既定） | 実装自体が no-op | なし。この値を読まない | なし。この値を読まない |

値は `atoi` などで数値化されません。たとえば `false` は先頭が `f` なので有効、`0anything` は先頭が `0` なので無効です。`STRATA_WORKLOAD_TRACE_DECODE_ONLY` 自体に数値境界や無効値エラーはありません。`sycl/include/strata/workload_trace.hpp:40-41,116-125`

この値を上書きする CLI 引数や設定ファイルの経路は見つかりませんでした。読み取り元は上記の `std::getenv` だけです。`sycl/include/strata/workload_trace.hpp:40-41`

## 有効になる条件

- `STRATA_SYCL_WORKLOAD_TRACE` を有効にしてビルドしている必要があります。CMake オプションの既定値は `OFF` です。`sycl/CMakeLists.txt:31-44`
- 実際に trace をファイルへ書くには、別変数 `STRATA_WORKLOAD_TRACE_FILE` に空でないパスを指定し、そのファイルを `fopen(path, "a")` で開ける必要があります。未設定・空文字・open 失敗では `file` が null のままとなり、trace は出力されません。Strata はこの失敗を警告しません。`sycl/include/strata/workload_trace.hpp:34-46,84-89`
- `STRATA_WORKLOAD_TRACE_MIN_POSITION` が空でない値として指定されると `strtoll(..., nullptr, 10)` で閾値を読み、context の position がその値未満の Scope は出力されません。このフィルターは decode 限定とは独立して適用されます。`sycl/include/strata/workload_trace.hpp:37,42-43,86-88`
- 実際に通過する Scope がなければイベント行は出ません。生成処理には `request.decode`、`decode.verify`、`decode.commit_emit`、`decode.draft` の Scope があり、prompt 側には `request.prefill` の Scope があります。後者は decode 限定時に除外されます。`sycl/src/program/generate.cpp:11193,11336-11337,12371-12376,12400-12404,12502-12505`

## 実行時の詳細

値は `sink()` 内の関数ローカル static `Sink` が初めて生成されるときに一度読み込まれます。その後の環境変更は反映されません。設定値は `decode_only` に保存されます。同じ `Sink` が trace ファイルのパスと最小 position も初期化時に読むため、これらも同じ時期に固定されます。`sycl/include/strata/workload_trace.hpp:34-50`

有効時、`Scope` は `decode.` prefix または完全一致の `request.decode` を持つラベルだけ開始時刻を取り、完了時に JSON trace event を追記します。それ以外は start 時刻が 0 のままで、`finish()` は何も書きません。`phase()` は decode 限定フラグが立つと常に return するため、prefill phase などの即時イベントも抑止されます。`sycl/include/strata/workload_trace.hpp:61-75,84-108`

request 終了処理では `workload_trace::flush()` が呼ばれ、trace file を flush します。Sink の破棄時にはファイルを close します。`sycl/src/program/generate.cpp:12783-12785` `sycl/include/strata/workload_trace.hpp:48,112-115`

## ログと測定値

この変数による stdout/stderr のメッセージや警告はありません。trace が有効なら、`STRATA_WORKLOAD_TRACE_FILE` で指定したファイルへ JSON Lines 形式の event が追記されます。Scope event は `"ph":"X"` と `"cat":"StrataCPU"` を含み、decode 限定では名称が `decode.*` または `request.decode` の event に限られます。ファイルを開けない場合もエラー表示はありません。`sycl/include/strata/workload_trace.hpp:44-45,72-74,87-105`

この変数についての性能測定値は、調査対象の Strata 資料では確認できませんでした。ソース上の trace は CPU 側で時刻を記録する診断出力です。`sycl/include/strata/workload_trace.hpp:24-32,70-74,89-105`

## 根拠

- 変数の唯一の実読み取りと判定、Sink の初期化: `sycl/include/strata/workload_trace.hpp:34-50`
- decode Scope / phase のフィルターとイベント書き込み: `sycl/include/strata/workload_trace.hpp:61-75,84-115`
- trace 実装の CMake 条件: `sycl/CMakeLists.txt:31-44`
- 生成処理での request/decode/prefill Scope と request 終了時 flush: `sycl/src/program/generate.cpp:10705-10706,11193,11336-11337,12371-12376,12400-12404,12502-12505,12783-12785`
