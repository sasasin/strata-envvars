# `STRATA_STOP_LAYERS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

サーバーでプロンプト読み込み中に `STOP` が要求されたとき、現在の chunk を最後まで読むか、レイヤー間で打ち切るかを選ぶ。未設定時は chunk 内のレイヤー境界で停止可能、`0` を含む整数 0 として解釈される値では chunk の終端まで続ける。生成済み token の停止制御ではなく、CUDA/HIP の chunk-major prefill を中断するタイミングの制御である。読み取りと分岐は `engine/src/prefill/prefill.cpp` の `Prefill::run_impl` にある（同ファイル:4214, 4970-4991）。

## 値と判定

`run_impl` 内の関数ローカル `static const bool` 初期化子で `std::getenv` を一度呼び、未設定なら `true`、設定時は `std::atoi(v) != 0` とする。文字列全体の検証はせず、`atoi` が先頭から変換した整数が 0 かどうかだけで決める。したがって空文字・数値で始まらない文字列は 0、先頭の空白や符号は `atoi` の整数変換規則に従い、数値の後ろの文字列は無視される（`engine/src/prefill/prefill.cpp:4973-4976`）。

| 条件（build など） | unset | 有効になる値（レイヤー間停止） | 無効になる値（chunk 終端まで継続） |
|---|---|---|---|
| CUDA / HIP の chunk-major prefill | 有効（`true`） | `1`, `-1`, `2`, `1junk` など `atoi` 結果が非 0 | `0`, `0anything`, `true`, `false`, 空文字, 空白だけ, ` 0` など `atoi` 結果が 0 |

数値の全体一致、大文字小文字、値域の検査、clamp はない。`atoi` の整数範囲外の入力の結果は保証できないため、指定値として扱わない。

## 有効になる条件

- サーバーの入力処理で `STOP` が受け取られ、`stop_req` が立つこと。サーバーは `Prefill` の `should_stop` callback を `stop_req` に結び付ける（`engine/src/program/generate.cpp:15932-15951`）。CLI からこの callback を設定する箇所は見つからず、CLI の通常実行ではこの環境変数による停止契機はない。
- CUDA/HIP の `Prefill::run` が layer-major 経路を選ばず `run_impl` に入ること。Metal は別の `prompt_run` を呼んで戻る（`engine/src/prefill/prefill.cpp:9629-9650, 9657-9705`）。索引上の登録 backend も `cuda-hip`（`terminal/data/settings-register.json:45759-45769`）。
- chunk 内で少なくとも 1 レイヤーを処理済みであること。条件は `l > LB` なので、chunk の最初のレイヤーを開始する前にはこの分岐で止めない（`engine/src/prefill/prefill.cpp:4977-4979`）。
- layer split では後段にも callback が渡されるかが `STRATA_STOP_STAGES` に依存する。未設定または `atoi` が非 0 なら全 stage に渡し、0 なら先頭 stage のみが見る（`engine/src/program/generate.cpp:15955-15960`）。
- `--prefill` などが決める chunk 境界は停止可能な位置に影響するが、本変数自体に CLI 引数や別設定による上書きはない。`--prefill` は batched prompt chunk のサイズを指定する（`engine/src/program/generate.cpp:969-981, 1375-1378`）。

## 実行時の詳細

設定値は `run_impl` が初めて当該初期化子に到達した時に static cache され、そのプロセス内では以後の呼び出しや環境変更で再評価されない（`engine/src/prefill/prefill.cpp:4973-4976`）。chunk 内で `should_stop()` が真になると、layer issuer thread を join し、該当する stager と後段 prefill stream を待ち、device を同期してから `err = "cancelled"` を返す（同:4977-4991）。通常の chunk 境界での停止確認は別にあり、`STRATA_STOP_LAYERS=0` でも chunk 間の停止は残る（同:4379-4385）。

サーバー側では読み込みが失敗しても `stop_req` が立っている場合、通常のエラー応答扱いではなくキャンセルとして後続処理へ進む。キャンセル中の prompt 部分の session state は次の request 用に採用せず、直前に保存された checkpoint だけを保持する。完了時は `DONE` 行の finish が `cancel`、stderr に `strata serve: prompt ... (cancelled)` が記録される（`engine/src/program/generate.cpp:21487-21501, 23287-23303, 23437-23478, 23648-23659`）。

## ログと測定値

chunk 内で停止した場合の stderr は次の文字列で始まる（`engine/src/prefill/prefill.cpp:4988-4990`）。

```text
strata prefill: stopped in the chunk from token <p0> before layer <l> (STOP)
```

Strata の資料にこの環境変数の測定値は見つからなかった。索引・設定 UI の登録メモは「既定で有効、0 で従来の chunk 間停止に戻す」「Internal: users never set it」としており、実装と一致する（`terminal/data/settings-register.json:45785-45787`）。

## 根拠

- `engine/src/prefill/prefill.cpp:4214` — `Prefill::run_impl`。
- `engine/src/prefill/prefill.cpp:4379-4385` — chunk 境界での停止確認。
- `engine/src/prefill/prefill.cpp:4970-4991` — static cache、layer 境界での停止、同期、ログ、cancel 戻り値。
- `engine/src/program/generate.cpp:15932-15960` — サーバーの `STOP` 入力と `should_stop` callback、stage への伝播。
- `engine/src/prefill/prefill.cpp:9629-9705` — Metal の別経路と layer-major 選択後の `run_impl` 呼び出し。
- `engine/src/program/generate.cpp:21487-21501, 23287-23303, 23437-23478, 23648-23659` — serve 側のキャンセル処理、session/checkpoint、観測ログ。
- `terminal/data/settings-register.json:45759-45789` — backend と内部用途の設定登録。
