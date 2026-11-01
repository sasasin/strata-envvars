# `DS4_STREAM_COPIES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の Metal 実行ファイル `strata_ds4` にある互換 GPU runtime のコピー・fill・event 処理経路を切り替えます。変数が未設定で context 側のコピー関数がリンクされている場合、`cudaMemcpyAsync` / `cudaMemsetAsync` 相当の呼び出しを DS4 context queue に渡し、event record / synchronize もその queue の mark / wait に結び付けます。変数が設定されている場合はこの経路を無効にし、Strata GPU runtime の stream queue に処理させます。

## 値と判定

値の文字列や数値は parse せず、`getenv()` が null かどうかだけを見ます。

| 環境の状態 | context queue 経路 |
|---|---|
| 未設定 | `ds4_ctx_copy` がリンクされていれば有効 |
| 設定あり（空文字を含む） | 無効 |

`0`、`1`、`false` など値の内容による違いはありません。CLI 引数や別の設定値との優先順位もありません。DS4 context copy 関数が利用できない場合は、変数が未設定でも context queue 経路は有効になりません。根拠: `metal/src/gpu/runtime.cpp:242-252`。

## 有効になる条件

- この分岐は `STRATA_DS4_RUNTIME` が定義された GPU runtime に限られます。CMake では `STRATA_DS4_RUNTIME=1` を `ds4_rt_gpu` に付け、その object を `strata_ds4` にリンクします。他の Metal target はこの DS4 runtime copy を使いません (`metal/CMakeLists.txt:151-165`)。
- Context queue への async copy / fill は、stream が graph capture 中でなく、byte 数が正であり、対象 allocation が Strata GPU runtime の allocation として見つかり、対応する `ds4_ctx_copy` / `ds4_ctx_fill` が成功した場合に限り実行されます (`metal/src/gpu/runtime.cpp:579-595,618-634`)。
- これらの条件を満たさない場合は通常の stream 経路へ進みます。graph capture 中なら操作を graph に記録します。非 capture 経路では、`DS4_NO_QBARRIER` が未設定なら `both_queues_barrier()` を先に行います。したがって `DS4_STREAM_COPIES` を設定したときも、`DS4_NO_QBARRIER` の有無が fallback の barrier に影響します (`metal/src/gpu/runtime.cpp:560-566,580-595,618-634`)。
- 未設定時の context queue 経路では、`event_record` が DS4 context queue に mark を置き、`event_synchronize` が token を wait します。変数設定時は通常の stream event record / synchronize に進みます (`metal/src/gpu/runtime.cpp:692-709,711-728`)。

## 実行時の詳細

`ctx_queue_ops()` 内の `static const bool` が初回呼び出し時に環境を読み、値をプロセス内で cache します。以後の環境変更では再評価されません。関数の呼び出し箇所は `memset_async`、`memcpy_async`、`event_record` です (`metal/src/gpu/runtime.cpp:249-252,579-585,618-624,692-700`)。

未設定で context 経路が選ばれた場合、コピーは両端が runtime allocation として認識され、DS4 側の処理が成功したときに context queue に渡されます。fill は宛先が認識されて処理が成功した場合に同経路を使います。コピー/fill が認識されないか context 側の関数が失敗した場合は stream の通常処理に戻ります (`metal/src/gpu/runtime.cpp:581-595,620-634`; `metal/src/engine/ds4_finish.cpp:2658-2688,2690-2709`)。DS4 側の `ds4_ctx_copy` は `ensure()`、host view、wrapped Metal buffer、pipeline の各準備に失敗すると `false` を返し、runtime は通常経路へ進みます (`metal/src/engine/ds4_finish.cpp:2663-2679`)。

対象変数を読み取ったこと自体によるログや警告はありません。通常経路の copy/fill が失敗した場合は runtime の既存エラー戻り値経路を通りますが、`DS4_STREAM_COPIES` 専用の終了・警告・fallback ログは確認できません。`DS4_NO_QBARRIER` は fallback の queue barrier を制御する別変数であり、この変数の判定値を上書きしません。

## 根拠

- `metal/src/gpu/runtime.cpp:242-252` — DS4 関数宣言と、環境変数の有無・weak symbol の存在による判定、static cache。
- `metal/src/gpu/runtime.cpp:579-595,618-634` — async fill/copy の context queue 経路、fallback、`DS4_NO_QBARRIER`。
- `metal/src/gpu/runtime.cpp:692-728` — event mark/wait と通常 event 経路。
- `metal/src/engine/ds4_finish.cpp:2646-2649,2658-2688,2690-2721` — DS4 側の copy/fill 実装と event token 処理。
- `metal/CMakeLists.txt:151-165` — DS4 runtime macro が `strata_ds4` 用 object に設定されること。
