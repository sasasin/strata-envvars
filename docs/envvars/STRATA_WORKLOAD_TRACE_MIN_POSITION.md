# `STRATA_WORKLOAD_TRACE_MIN_POSITION`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は、SYCL の診断用 CPU workload trace に記録する position の下限を指定する。現在の trace context の `position` が下限未満なら、その phase/event を出力しない。trace を有効にしていても、閾値より前の記録を省くための絞り込みであり、生成や decode の計算・token 選択は変更しない。読み取りと両方の出力判定は `strata::workload_trace::Sink`、`phase`、`Scope` にある（`sycl/include/strata/workload_trace.hpp:34-50,61-88`）。

候補名の全参照を検索したところ、環境から直接読む箇所はこの `std::getenv` 1 箇所だけだった。間接 helper 経由の読み取りはない。

## 値と判定

`Sink` 初期化時に `std::getenv` し、値が未設定または空文字なら初期値 `-1` を保つ。空でない場合は `std::strtoll(minimum, nullptr, 10)` で符号付き base-10 整数へ変換する。終端位置を調べず、変換エラーの検査や独自の範囲 clamp もない（`sycl/include/strata/workload_trace.hpp:37-43`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_SYCL_WORKLOAD_TRACE` を有効にしてビルド | 閾値 `-1` | `0`、`1`、`-2`。現在の context position が変換後の値以上なら記録対象 | 閾値以上の position が無い場合、または位置が閾値未満なら記録されない |
| 同 macro が無効の通常ビルド | 環境変数を読まない | 該当なし | 該当なし |

有効/無効は文字列の真偽値ではなく、変換された数値と position の比較で決まる。たとえば空文字は未設定と同じ `-1`、`0anything` は先頭の `0` から `0`、`true` のように数字で始まらない文字列は変換結果 `0` になる。`1.5` は `1`、`-2tail` は `-2` として扱われる。`strtoll` の base 10 変換なので先頭の空白と符号は数値変換規則に従い、末尾は検査されない。表の「有効」は trace event の対象になり得る意味で、trace 出力全体には次節の条件も必要となる。

## 有効になる条件

- `sycl/CMakeLists.txt` の CMake option `STRATA_SYCL_WORKLOAD_TRACE` は既定 `OFF`。`ON` のとき、列挙された SYCL ソースに `STRATA_SYCL_WORKLOAD_TRACE=1` が定義される。macro 無効時の `workload_trace` 関数・型は no-op であり、この環境変数も読まれない（`sycl/CMakeLists.txt:31-44`、`sycl/include/strata/workload_trace.hpp:6-18,116-126`）。
- `STRATA_WORKLOAD_TRACE_FILE` が空でない値に設定され、`std::fopen(path, "a")` が成功している必要がある。設定なし・空文字・open 失敗の場合 `Sink::file` は null のままで、trace event は出ない。失敗理由のログはこのコードからは出さない（`sycl/include/strata/workload_trace.hpp:34-48,64,87`）。
- `STRATA_WORKLOAD_TRACE_DECODE_ONLY` が空でなく先頭文字が `'0'` 以外の場合、`Scope` は `decode.` で始まる label と `request.decode` のみを記録し、`phase` event は記録しない。この別変数のフィルターも満たす必要がある（`sycl/include/strata/workload_trace.hpp:40-41,64,87-88`）。
- context position が閾値以上であること。request は `0`、prompt は `n - 1`、decode は `n - 1`、verify は `p` を context position として設定する箇所があるため、同じ閾値でも処理段階によって記録対象が変わる（`sycl/src/program/generate.cpp:10705-10706,11193,11336-11337,12371-12373`）。

この変数に CLI 引数、設定ファイル、別の環境変数から値を上書きする経路は見つからなかった。閾値は trace 記録の選別にのみ使われ、request の position や計算を変更しない（`sycl/include/strata/workload_trace.hpp:64,87`）。

## 実行時の詳細

`Sink` は関数内 `static` の singleton として、`phase()` または `Scope` から `sink()` が初めて呼ばれた時に初期化される。その初期化時にこの値を読み、プロセス内では保持するため、初回呼び出し後に環境を変更しても閾値は再読込されない。プロセスごとに singleton が初期化される（`sycl/include/strata/workload_trace.hpp:34-50,61-64,84-88`）。

`phase()` は position が閾値未満なら即時 return し、`Scope` も constructor で同条件なら計測を開始しない。`Scope` が開始されなければ destructor の `finish()` も何も書かない。position が閾値以上で、trace file と他のフィルター条件も通る場合は、phase event またはスコープの開始・所要時間を JSON Lines 形式でファイルへ書く。request の終わりには trace file を flush する経路がある（`sycl/include/strata/workload_trace.hpp:61-75,84-108,112-115`、`sycl/src/program/generate.cpp:12783-12785`）。

## ログと測定値

この変数について専用の stdout/stderr ログ、警告、終了・失敗経路はない。閾値により trace file 内の event が省かれる。実装は JSON Lines event を `STRATA_WORKLOAD_TRACE_FILE` で指定したファイルに追記するが、閾値の値を記録するログはない（`sycl/include/strata/workload_trace.hpp:42-46,64,72-74,87,101-105`）。測定値は該当なし。

## 根拠

- `sycl/CMakeLists.txt:31-44` — workload trace build option と compile definition。
- `sycl/include/strata/workload_trace.hpp:34-50` — 閾値の読み取り、変換、singleton 初期化。
- `sycl/include/strata/workload_trace.hpp:61-115` — phase/Scope の position 判定、出力、flush。
- `sycl/include/strata/workload_trace.hpp:116-126` — macro 無効時の no-op 実装。
- `sycl/src/program/generate.cpp:10705-10706,11193,11336-11337,12371-12373,12783-12785` — position context の設定と request 終了時の flush。
