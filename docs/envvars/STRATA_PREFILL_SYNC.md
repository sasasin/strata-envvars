# `STRATA_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL prefill の診断用フック。設定されていると、prefill の各 phase mark で compute queue を同期し、完了した mark の phase 名と待ち時間を stderr に出す。通常は GPU 処理を非同期に積む mark を同期点にするため、待ちが長い区間を特定しやすくなる一方、同期の追加により実行時間は変わり得る。値を読み取る実装は `PfTimer::mark` と `Prefill::run_impl` にある（`engine/sycl/src/prefill/prefill.cpp:2560-2589,2693-2700`）。

## 値と判定

`PfTimer` の構築時に `std::getenv("STRATA_PREFILL_SYNC") != nullptr` を評価する。値の変換・文字列比較はなく、設定の有無だけで決まる（`engine/sycl/src/prefill/prefill.cpp:2560-2569`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL prefill の `PfTimer` | `sync=false` | 空文字、`0`、`1`、`false`、任意の文字列（いずれも非 null） | 該当なし。変数が存在すれば値の内容にかかわらず有効 |

## 有効になる条件

- この読み取りは `engine/sycl/src/prefill/prefill.cpp` にのみあり、Strata の SYCL engine を使って prefill が実行される経路に限られる。トップレベル CMake では SYCL は `STRATA_ENABLE_SYCL` で選ぶ別 backend で、CUDA/HIP と同時には構成できない（`engine/CMakeLists.txt:23-32`）。
- `Prefill::run_impl` 内で `PfTimer` が構築され、実行された `pt.mark(...)` ごとに同期する。prompt chunk の開始・終了や各処理 phase で mark されるため、同期回数は実行経路・chunk 数・モデル処理内容に依存する（`engine/sycl/src/prefill/prefill.cpp:2762-2765,2826-2839,3379-3380,3437,3520-3848,3925-5326,5530-5532`）。
- CLI 引数や別環境変数との優先順位・上書きはこの読み取り箇所にはない。`STRATA_PREFILL_TIMING` は別に `PfTimer::on` を決める。同期ログは timing の有効・無効にかかわらず出るが、GPU timeline の計測・出力は timing 側が有効な場合だけ（`engine/sycl/src/prefill/prefill.cpp:2560-2568,2570-2589,5731-5746`）。

## 実行時の詳細

`PfTimer` は `Prefill::run_impl` の呼び出しごとにローカル構築され、構築時に環境を一度読み取る。したがってその呼び出し中の環境変更は既に保持した `sync` に反映されず、次に構築される `PfTimer` から評価される。関数内 static cache ではない（`engine/sycl/src/prefill/prefill.cpp:2560-2569,2693-2700,2762-2765`）。

各 mark ではまず phase を workload trace に通知し、`sync` が真なら mark が渡された compute queue (`s`) の `wait()` を呼ぶ。待ちに timeout は設けられていない。wait が戻った後に連番、phase 名、待ち時間を stderr に出し、その後 `STRATA_PREFILL_TIMING` が有効なら別途 SYCL event を記録する。従って同期変数だけでは event の作成や timing 集計は有効にならない（`engine/sycl/src/prefill/prefill.cpp:2560-2589`）。

## ログと測定値

各同期 mark が完了すると、次の形式で stderr に出力する（phase 名は `embed+steps`, `hc read`, `gdn`, `qsa proj`, `qsa indexer`, `qsa select`, `qsa attn`, `router+shared`, `host grouping`, `gather`, `wait copy`, `dequant`, `gemm gate/up`, `gemm down`, `combine`, `ple`, `kv stage`, `gdn conv+gates`, `gdn recurrence`, `gdn out proj` のいずれか）。

```text
strata prefill sync: mark <番号> phase <phase名> done (waited <ミリ秒> ms)
```

このログは `wait()` が戻った後に限り出る。ある mark の wait が戻らず停滞した場合、その mark の `done` 行は出ない（`engine/sycl/src/prefill/prefill.cpp:2556-2559,2570-2578`）。`wait()` から `sycl::exception` が送出された場合は `run_impl` の catch が例外内容とソース位置を stderr に出して `exit(1)` する実装だが、この変数専用のエラー文言や timeout 処理はない（`engine/sycl/src/prefill/prefill.cpp:5790-5796`）。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:2560-2589` — 設定有無の判定、queue wait、同期ログ、独立した timing event。
- `engine/sycl/src/prefill/prefill.cpp:2693-2700,2762-2765` — prefill 関数と `PfTimer` の構築位置。
- `engine/sycl/src/prefill/prefill.cpp:2826-2839,3379-3380,3437,3520-3848,3925-5326,5530-5532` — mark の呼び出し経路。
- `engine/sycl/src/prefill/prefill.cpp:5790-5796` — SYCL exception 時の終了処理。
- `engine/CMakeLists.txt:23-32` — SYCL backend の選択条件。
