# `STRATA_HANDOFF_PIPE_WORKER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_HANDOFF_PIPE` による layer split の prompt hand-off で、後段 `Prefill` の chunk 処理を専用の常駐 worker thread に投入するか選びます。既定では worker を使います。無効にすると、各 chunk を `std::async` で起動する従来の thread-per-chunk 経路になります。

この変数は hand-off の分割数や GPU 転送内容を変えません。`STRATA_HANDOFF_PIPE` が有効な場合だけ worker の選択に影響します。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| 値 | worker 選択 |
|---|---|
| 未設定 | 有効（既定） |
| `0`、空文字、数値に変換できない文字列（例: `off`） | 無効 |
| 0 以外に変換される値（例: `1`, `2`, `-1`, `1tail`） | 有効 |

`atoi` が先頭の整数部分を変換するため、`0tail` は無効、`1tail` は有効です。空白と符号は `atoi` の変換規則に従います。値は `handoff_pipe_worker()` 内の function-local `static const bool` に保存されるので、最初の評価後にプロセス環境を変更しても再評価されません。

## 有効になる条件

- `STRATA_HANDOFF_PIPE` が有効であること。実装は値を `atoi` で読み、2 未満を無効、2 以上を有効とし、16 に clamp します。
- `Prefill` に後段 stage (`next_`) がある layer split であること。分割数が有効なら初期化時に hand-off event が作成されます。
- Metal backend では `Prefill::init()` が Metal engine に委譲して戻るため、この CUDA/HIP hand-off 実装は通りません。

`STRATA_HANDOFF_PIPE` が未設定・0・1などで分割数が無効なら、`handoff_pipe_worker()` はこの変数の値に関係なく false となり、worker 経路を選びません。

## 実行時の詳細

有効時、前段 `Prefill` は `HandWorker` を最初の successor hand-off 時に遅延作成し、以後の successor `run_impl()` を packaged task としてその worker の queue に投入します。worker thread は起動時に `strata::aux_cpus::pin_current_thread()` を呼び、job を順に実行します。future を通して戻り値を受け取り、通常の chain drain で待ちます。worker は `Prefill::release()` 時に破棄され、thread を join します。

無効時は chunk ごとに `std::async(std::launch::async, ...)` を使い、同じく新しい thread 上で `pin_current_thread()` を呼びます。どちらの経路も後段の `run_impl()` の結果を future で chain に返します。

変数自身に対応するログ出力はありません。hand-off event の初期化失敗時には `prefill: the layer split's hand-off events (STRATA_HANDOFF_PIPE)` がエラー文字列になりますが、これは分割数側の初期化エラーであり、worker の選択状態を示すログではありません。

## 根拠

- `src/prefill/prefill.cpp:349-363`: `STRATA_HANDOFF_PIPE` の parse、範囲制限、static cache。
- `src/prefill/prefill.cpp:371-377`: 本変数の parse と、分割数が有効な場合だけ true となる条件。
- `src/prefill/prefill.cpp:379-418`: worker の queue、thread 起動、CPU pinning、job 実行、join。
- `src/prefill/prefill.cpp:1036-1048`: `Prefill` の破棄・release と worker の後始末。
- `src/prefill/prefill.cpp:1234-1270`: Metal 早期分岐、layer split 用 hand-off buffer/event の初期化。
- `src/prefill/prefill.cpp:4581-4629`: 前段から後段への chunk hand-off、worker queue と `std::async` fallback。
- `docs/BATCHING.md:124`: `STRATA_HANDOFF_PIPE` の概要。P 個の piece と persistent thread を説明しており、ソースの hand-off 概要と一致します。本変数による opt-out の値判定はこの資料には記載されていません。
