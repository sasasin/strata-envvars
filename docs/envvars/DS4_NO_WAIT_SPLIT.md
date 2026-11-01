# `DS4_NO_WAIT_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DS4 実行時に CUDA 互換イベントを同期するとき、イベントの mark より後に積まれた deferred dispatch を、ホストが mark の完了を待つ前に別 command buffer として commit するかを切り替えます。設定すると、この追加の `split_runs()` を省略します。mark 自体の完了待ちは省略されません。

## 値と判定

| 状態 | `no_wait_split` | 動作 |
|---|---:|---|
| 未設定 | `false` | mark 後の dispatch があれば `split_runs()` で commit してから mark を待つ |
| 何らかの値を設定 | `true` | `split_runs()` を呼ばずに mark を待つ |

実装は `std::getenv(...) != nullptr` による設定有無だけを見ます。値の変換・文字列比較はありません。そのため空文字、`0`、`false` を含め、設定された値はすべて同じ扱いです。CLI 引数や他の環境変数による値の上書きはありません。

判定値は `ds4_ctx_wait()` 内の `static const bool` に保存されます。最初の `ds4_ctx_wait()` 呼び出し時に一度だけ評価され、それ以降にプロセス環境を変更しても再評価されません。

## 有効になる条件

- 対象コードは Metal の `strata_ds4` 実行ファイル向け runtime です。CMake では同実行ファイルに `STRATA_DS4_RUNTIME=1` を定義した runtime object をリンクしています。CUDA/HIP backend 全般を切り替える変数ではありません。
- `ds4_ctx_wait()` は DS4 runtime の `cudaEventSynchronize()` 経路から呼ばれます。この経路はイベントに context mark token があり、`ctx_queue_ops()` が有効で、stream capture 中でない場合に `event_record()` が token を作った場合に使われます。
- `ctx_queue_ops()` は `ds4_ctx_copy` が存在し、かつ `DS4_STREAM_COPIES` が未設定の場合に有効です。したがって `DS4_STREAM_COPIES` が設定されていると、通常の stream event 経路となり、この変数が読む `ds4_ctx_wait()` には進みません。
- `g_cx` が null の場合は split をしません。token が null の場合は wait もしません。これらの guard は値の判定とは独立です。

## 実行時の詳細

DS4 runtime の context queue event 経路では、`event_record()` が `ds4_ctx_mark()` を呼び、現在までの dispatch を mark します。`event_synchronize()` は token を取り出して `ds4_ctx_wait(token)` に渡します。`ds4_ctx_wait()` は既定では `g_cx->split_runs()` を呼んでから `g_cx->wait_mark(token)` を呼びます。`DS4_NO_WAIT_SPLIT` を設定すると前者だけを飛ばし、後者による mark の完了待ちは引き続き実行します。

`split_runs()` は deferred dispatch を command buffer として commit し、完了を待たずに戻ります。従ってこの変数を設定した場合は、mark 後に現在の deferred buffer にある処理をこの地点では commit しません。後続の処理が別の split / flush を行うまで未 commit のままになり得ます。設定は event wait 時のこの一回の split に限られ、別の `ds4_metal_kick()` や `ds4_metal_flush()` の split / flush を無効化しません。

この変数専用のログ、警告、終了経路はありません。wait 対象 command buffer が完了状態でなければ、共通の `wait_mark()` が `mtl: deferred command buffer failed: ...` を stderr に出し、`DS4_ERRINFO` も設定されていれば追加の `mtl: recent: ...` と `mtl: info: ...` を出します。これは wait 側の共通エラー報告です。

## 根拠

- 候補一覧には `DS4_NO_WAIT_SPLIT` が掲載されています（調査文書リポジトリ `docs/envvars/000_envvers.md:258`）。Strata 本体の全参照検索では読み取り箇所は `metal/src/engine/ds4_finish.cpp:2719` の一箇所です。
- 値の判定と split / wait の順序: `metal/src/engine/ds4_finish.cpp:2718-2721`。
- Metal command buffer を mark し、その完了を待つ処理: `metal/src/mtl_rt.h:114-117`, `metal/src/mtl_rt.mm:796-816,832-852`。
- DS4 runtime での event mark / synchronize 経路: `metal/src/gpu/runtime.cpp:242-250,692-723`。`DS4_STREAM_COPIES` による queue 経路の条件は `metal/src/gpu/runtime.cpp:249-250`。
- `STRATA_DS4_RUNTIME` を定義した runtime object と `strata_ds4` へのリンク: `metal/CMakeLists.txt:151-169`。
- `ds4_metal_kick()` と `ds4_metal_flush()` は別に `split_runs()` / flush を呼びます: `metal/src/engine/ds4_finish.cpp:2723-2735`。
- `docs/DETAILS.md` と他の Strata docs にこの変数の説明は見つかりませんでした。性能や正確性について、この調査では測定していません。
