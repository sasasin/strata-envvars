# `DS4_FLUSH_EACH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリ・GPU driver の挙動は対象外。

## 役割

`strata_ds4` の Metal runtime で、条件に合う単一 dispatch を deferred command buffer に積んだ直後、stream 同期と command buffer の commit・完了待ちを行います。コードコメントでは debugging 用とされています。`strata_ds4` が使う `STRATA_DS4_RUNTIME` 定義付きの runtime に限られ、通常の Metal `strata` target にはこの runtime 定義は付きません（`metal/CMakeLists.txt:151-169`）。

## 値と判定

変数値を parse せず、`std::getenv("DS4_FLUSH_EACH") != nullptr` で設定有無だけを判定します。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |
| `0`, `false` など | 有効。内容や大文字小文字は検査しない |

判定結果は関数内の `static const bool` に一度保存されます。初めて評価されるのは後述の fast path に入り、かつ `DS4_PROF` による早期 return を通らなかった呼び出しです。その後プロセス内で環境変数を変えても判定し直しません。CLI 引数や設定ファイルによる上書きは見つかりません（`metal/src/mtl_rt.mm:902-907,948-956`）。

## 有効になる条件

`STRATA_DS4_RUNTIME` 付きでコンパイルされた Metal runtime の `Context::run()` が、`ds.size() == 1`、`reps == 1`、`barrier_between == false` の fast path を通る必要があります（`metal/src/mtl_rt.mm:902-909`）。複数 dispatch の一括実行、反復実行、または dispatch 間 barrier を指定した呼び出しではこの環境変数の判定箇所へ到達しません（`metal/src/mtl_rt.mm:958-979`）。

さらに `DS4_PROF` が設定されていると、その fast path は profiling のための同期と `flush_runs()` を実行して `return` するため、`DS4_FLUSH_EACH` の判定は行われず、同変数による追加の flush はありません（`metal/src/mtl_rt.mm:948-956`）。`DS4_FLUSH_AFTER` の dispatch 名リストに現在の dispatch 名が含まれる場合も同じ同期・flush 分岐に入ります。これは別のトリガーであり、`DS4_FLUSH_EACH` の値の優先順位を変えるものではありません（同:951-956）。

## 実行時の詳細

fast path は dispatch を deferred encoder に encode し、必要なら encoder 内の memory barrier を設定した後、dispatch 数を増やします。`DS4_FLUSH_EACH` が有効なら、その dispatch の後に `ds4_gpu_sync_all_streams_weak` がリンクされている場合は呼び出し、続いて `flush_runs()` を呼びます。`flush_runs()` は開いている encoder を終了し command buffer を commit し、in-flight command buffer を `wait_spin()` で待ってから参照を解放します。したがって、この経路では各対象 dispatch の処理継続前に GPU 完了待ちが入ります（`metal/src/mtl_rt.mm:927-957,855-899,818-830`）。

この変数自身はログを出しません。別途 `DS4_TRACE_DISP` が設定されていれば `TRACE flush_runs (<queued> queued)` が stderr に出ることがあります（`metal/src/mtl_rt.mm:855-857`）。deferred command buffer が失敗した場合、`flush_runs()` は stderr に `mtl: deferred command buffer failed: ...` を出します。`DS4_ERRINFO` も設定されていれば失敗した command buffer の dispatch 名も出力します。この `flush_runs()` 内に明示的なプロセス終了処理はありません（同:884-895）。

## 根拠

- 候補名の実コード参照は `metal/src/mtl_rt.mm:950` の環境読み取り 1 箇所。リポジトリ全体の名前検索で他の読み取り箇所は見つかりませんでした。
- 値判定、fast path、profiling と `DS4_FLUSH_AFTER` の分岐、dispatch 後の同期・flush: `metal/src/mtl_rt.mm:902-979`。
- `flush_runs()` の commit・wait・失敗ログ: `metal/src/mtl_rt.mm:855-899`。待機処理: `metal/src/mtl_rt.mm:818-830`。
- 対象 runtime の build 条件: `metal/CMakeLists.txt:151-169`。
- `docs/DETAILS.md` に `DS4_FLUSH_EACH` の記述は見つかりませんでした。
