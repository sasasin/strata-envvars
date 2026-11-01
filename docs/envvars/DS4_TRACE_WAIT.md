# `DS4_TRACE_WAIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DeepSeek (DS4) ランタイムが、遅延 command buffer の完了を待つ直前に呼び出し stack を stderr に出す診断用フックです。待つかどうかや待機方法を切り替える設定ではありません。`Context::flush_runs()` は command buffer を commit してから完了を待つ関数で、この変数は未完了 buffer に対する待機直前にだけ参照されます。

## 値と判定

| 環境の状態 | 動作 |
|---|---|
| 未設定 | stack trace を出さない |
| 設定あり（空文字を含む） | 条件を満たす `flush_runs()` で stack trace を出す |

コードは `std::getenv("DS4_TRACE_WAIT")` の null 判定だけを行います。値の文字列・数値変換、空文字判定、真偽値 parse はありません。そのため `0`、`false`、空文字なども「設定あり」として扱われます。CLI 引数や別の環境変数による優先順位・上書きはありません。

## 有効になる条件

- Apple 専用の `metal/` ビルドであること。`metal/CMakeLists.txt` は Apple 以外では構成を停止します。
- DS4 実行ファイルの `ds4_rt_mm` オブジェクトとして `mtl_rt.mm` を `STRATA_DS4_RUNTIME=1` 付きでコンパイルすること。この runtime macro の有効範囲に `Context::flush_runs()` が含まれます。通常の `mtl_rt` ライブラリは同じ定義を付けずにコンパイルされます。
- `flush_runs()` の呼び出し時に `impl_->inflight != nil` であること。未完了 buffer がない呼び出しでは環境変数を参照する行に到達しません。

## 実行時の詳細

`std::getenv()` は `flush_runs()` が未完了 buffer を処理するたびに評価され、結果を static cache しません。したがって、その呼び出し時点で値が設定されていれば診断出力が行われます。Strata 内でこの変数を子プロセスへ転送したり、値を書き換えたりする箇所は見つかりませんでした。

条件を満たすと、`backtrace(fr, 8)` で最大 8 フレームを取得し、stderr に `WAIT flush_runs:` を出した後、先頭フレームを除く取得分を `backtrace_symbols_fd(..., 2)` で file descriptor 2（stderr）へ出力します。その直後に通常の `wait_spin(impl_->inflight)` を呼び、待機時間の集計、command buffer の失敗ログ判定、inflight の解放へ進みます。この変数による追加の終了・例外・待機 timeout 経路はありません。

`flush_runs()` は DS4 の engine / host の複数箇所から呼ばれます。呼び出し元によらず、上記の未完了 buffer 条件を満たした待機が診断出力の対象です。

## 根拠

- `metal/src/mtl_rt.mm:9-20,76-77` — `execinfo.h` と DS4 runtime 実装の macro guard。
- `metal/src/mtl_rt.mm:818-830` — `wait_spin()` の待機方法。変数による切り替えはありません。
- `metal/src/mtl_rt.mm:855-899` — `flush_runs()` の commit、環境変数判定、stderr 出力、待機と後続処理。
- `metal/src/mtl_rt.h:117-119` — `flush_runs()` が commit と wait を行う API であること。
- `metal/src/engine/ds4_finish.cpp:100-112,229-235,272,355-361,1285,2735`、`metal/src/engine/ds4_host.cpp:135,178,223,246` — DS4 engine / host 側の呼び出し例。
- `metal/CMakeLists.txt:16-18,155-165` — Apple 専用条件、DS4 実行ファイルが runtime macro 付きの object を使うこと。

