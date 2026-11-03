# `FNX_PF_GATHER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の Qwen3.8-Flash-Next prompt path が、カード間で部分和を集約した後の all-gather を ring forwarding 方式にするか direct gather 方式にするかを選びます。CUDA の既定は ring、HIP の既定は direct です。通常の Strata engine や別の prefill 実装を切り替える変数ではありません。

## 値と判定

値は文字列全体を `strcmp` で比較します。数値変換、空白除去、大文字小文字の正規化、無効値のエラー出力はありません。

| build | 未設定 | ring にする値 | direct にする値 | その他の設定値（空文字を含む） |
|---|---|---|---|---|
| CUDA | ring | すべて（`ring` を含む） | `direct` のみ | ring |
| HIP | direct | `ring` のみ | すべて（`direct` を含む） | direct |

したがって `direct` / `ring` は小文字の完全一致が必要です。たとえば `DIRECT` は CUDA では ring、HIP では direct になります。設定値が無効な形でも警告や失敗にはならず、上表の分岐結果を使います。根拠: `src/split/src/prefill.cu:883-890`。

## 有効になる条件

- `strata-split` は opt-in の別 executable で、CMake の `STRATA_BUILD_SPLIT` によって追加されます。Linux CUDA または HIP build が必要で、カード数は 2〜4 です。通常の Strata 実行経路にはこの実装が含まれません。既定では split build 自体が OFF、カード数は 2 です（`src/split/CMakeLists.txt:1-27,92-105,113-123`）。
- この設定が選ぶのは `prefill.cu` の host exchange 用 copy-engine ring plan です。CUDA/HIP のどちらでも `FNX_PF_RING_SM` が非ゼロなら prompt の和は `ring_sum` 経路に入り、`pf_ring` の plan を使わないため、この変数は効きません（`src/split/src/prefill.cu:738-745,1241-1247,1299-1306`）。
- HIP では RCCL が実際に有効な場合も `FNX_PF_GATHER` は効きません。`pf_ring` は RCCL の `AllReduce` を呼び出して return し、host exchange の `r.plan` を実行しません（`src/split/src/prefill.cu:512-533`）。RCCL の利用には peer push が有効で、RCCL の open が成功する必要があります。`FNX_PF_RCCL` と build 既定値が選択に関わります（`src/split/src/engine.cu:81-104`, `src/split/src/hip/rccl_dl.hpp:61-82`）。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が呼ばれ、カードごとの `PfRing` を初期化するときに値を読みます。判定結果は各 `PfRing::direct` として保存され、`pf_ring_plan_direct()` または `pf_ring_plan()` の操作列を `r.plan` に格納します。その後の prompt pass は同じ plan を `pf_ring_run()` で実行します。環境変数を engine 構築後に変更しても plan は再評価されません（`src/split/src/engine.cu:274-275`, `src/split/src/prefill.cu:625-635,866-906`, `src/split/src/pf_common.cuh:167-175,209-290`）。

両方式ともカードごとの和の reduce-scatter 部分は ring で進めます。ring plan は完成した part を次のカードへ順に転送し、全 part が揃うまで forwarding します。direct plan は完成 part を各カードの gather buffer に書き、各カードの gather flag を通知して待つため、完成 part の host-to-host forwarding を行いません（`src/split/src/pf_ring_plan.hpp:43-77,80-105`; `src/split/src/pf_common.cuh:230-273`）。この変数の値を選択したというログはありません。

リング処理は加算値を fp16 に変換し、範囲外または NaN を検出すると ring error bit を立てます。prompt pass は stream が 120 秒以内に完了しない場合 `prefill: a pass did not finish in 120 s (a ring step's flag never came?)` で失敗し、完了後に error bit があれば `prefill: ring error <値>` を投げます。これらは ring 処理の一般的な失敗経路であり、特定の `FNX_PF_GATHER` 値に固有のエラーではありません（`src/split/src/pf_common.cuh:91-105,126-135`; `src/split/src/prefill.cu:1320-1335`）。

## 根拠

- 候補一覧には `FNX_PF_GATHER` が載っています（`docs/envvars/000_envvers.md:564`）。Strata ソース内の完全一致参照は `src/split/src/prefill.cu:884-885` のコメントと直接 `std::getenv` する箇所だけです。共通 helper に名前を渡す参照はありません。
- 選択結果から plan の作成: `src/split/src/prefill.cu:883-890,905`。
- ring と direct gather の各操作: `src/split/src/pf_ring_plan.hpp:43-105`, `src/split/src/pf_common.cuh:209-290`。
- RCCL による plan の迂回と有効条件: `src/split/src/prefill.cu:512-533`, `src/split/src/engine.cu:81-104`, `src/split/src/hip/rccl_dl.hpp:61-82`。
