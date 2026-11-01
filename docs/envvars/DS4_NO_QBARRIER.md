# `DS4_NO_QBARRIER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek の Metal runtime で、非同期 fill/copy を通常の stream 経路へ記録する直前に実行する、二つの Metal queue 間の barrier を省略します。未設定時は barrier を実行し、値が何か設定されていれば省略します。判定は真偽文字列や数値の parse ではなく `std::getenv(...)` の null 判定です。

対象となるのは `memset_async()` と `memcpy_async()` のうち、stream が graph capture 中でなく、context queue の短絡経路も使われない呼び出しです。同期 API の `memset_device()`、`memcpy_sync()`、`stream_synchronize()` の barrier はこの変数では省略されません。

## 値と判定

| 環境変数の状態 | `memset_async()` / `memcpy_async()` の判定 | 結果 |
|---|---|---|
| 未設定 | `std::getenv()` が null | 条件に合う場合 `both_queues_barrier()` を呼ぶ |
| 空文字を含む何らかの値を設定 | `std::getenv()` が non-null | barrier 呼び出しを省く |

値の文字列比較、数値変換、範囲検査、無効値時の fallback はありません。CLI 引数や別の環境変数との優先順位を決める処理も、この変数の読み取り箇所にはありません。

## 有効になる条件

- ビルドが macOS 用 Metal project の `strata_ds4` target であること。`metal/CMakeLists.txt` は macOS 以外での構成を拒否し、DeepSeek 用に `gpu/runtime.cpp` のコピーを `STRATA_DS4_RUNTIME=1` 付きでコンパイルします。Qwen engine の `strata` および他 target はこの macro なしの runtime を使います。
- `memset_async()` または `memcpy_async()` が通常の runtime 経路を通ること。graph capture 中 (`S(st)->rec` が真) は barrier 判定を行いません。
- `DS4_STREAM_COPIES` が未設定で context queue 経路が有効な場合、バッファ条件を満たし `ds4_ctx_fill()` / `ds4_ctx_copy()` が成功すると、その処理は barrier 判定より先に成功 return します。この経路では `DS4_NO_QBARRIER` の値にかかわらず、この関数内の barrier は呼ばれません。context queue 経路は `ds4_ctx_copy` の存在と `DS4_STREAM_COPIES` 未設定を static 値に cache します。

## 実行時の詳細

`memset_async()` は、capture 中でなく、context queue の最適化経路で処理されないとき、`DS4_NO_QBARRIER` が未設定なら `both_queues_barrier()` を呼び、その後 fill を encode します。`memcpy_async()` も同様に、context queue 経路を試した後で環境変数を確認し、未設定なら barrier を呼んでから copy を encode します。`memcpy_2d_async()` は各行について `memcpy_async()` を呼び、`memcpy_peer_async()` も検証後に `memcpy_async()` へ委譲するため、これらの経路も同じ判定を受けます。

この barrier は `ds4_metal_flush()` を呼びます。そこではまず stream 側の未処理処理を flush して完了を待ち、その後 DeepSeek engine 側の deferred runs を flush します。ソースコメントは、copies が一方の queue、kernel dispatch がもう一方の queue にあるため、単に片方だけを commit すると queue 間の順序が保証されない場合があると説明しています。したがって変数を設定すると、この非同期 API 呼び出し前の Strata runtime の queue 間 flush/wait が省略され、後続の encode は続行します。Strata はこの設定を受けて警告やログを出しません。エラーや終了を直接起こす処理もありません。省略による個別の結果を測定した資料は確認できませんでした。

環境変数は各 `memset_async()` / `memcpy_async()` 呼び出しで直接 `getenv()` され、static cache されません。したがってプロセス内で環境を変更した場合、以後の判定に反映されるコードです。CLI による上書きや子プロセスへの明示的な転送は見つかりませんでした。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:252`。
- macOS 限定、Metal project/target、および DeepSeek 用 runtime に限った macro: `metal/CMakeLists.txt:1-2,16-18,151-169`。
- context queue の有効条件と cache: `metal/src/gpu/runtime.cpp:242-251`。
- 二つの queue の stream sync/wait と engine flush を行う処理: `metal/src/gpu/runtime.cpp:554-566`; `metal/src/engine/ds4_finish.cpp:2728-2736`。
- `memset_async()` の context 経路と環境変数判定: `metal/src/gpu/runtime.cpp:579-595`。
- `memcpy_async()` の context 経路と環境変数判定: `metal/src/gpu/runtime.cpp:618-634`。
- `memcpy_2d_async()` / `memcpy_peer_async()` の委譲: `metal/src/gpu/runtime.cpp:607-616`。
- 変数の対象外である同期 API の barrier: `metal/src/gpu/runtime.cpp:569-577,597-605,650-656`。
- queue 間順序の説明は実装コメント `metal/src/engine/ds4_finish.cpp:2729-2733` にあります。`docs/DETAILS.md` にはこの変数の挙動や測定値に関する記載を確認できませんでした。
