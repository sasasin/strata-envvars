# `STRATA_HANDOFF_PIPE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

CUDA/HIP 系の prompt prefill で layer split を使うとき、各 stage 間で渡す chunk の行を複数の部分に分けて転送する opt-in 設定です。既定の 1 回の host hand-off では、前段 stage が chunk 全体を pinned host buffer にコピーしてから次段を始めます。2 以上を指定すると、前段は chunk の計算完了 event と各部分の転送完了 event を記録し、後段は各部分の event を GPU stream 上で待って対応行を upload します。転送の分割だけを変更し、同じ行データを引き渡す実装です。値の読取りと分割数の決定は `handoff_pipe_pieces()`、イベントの準備は `Prefill::init()`、転送は `Prefill::run_impl()` にあります（`engine/src/prefill/prefill.cpp:899-920,2488-2501,4425-4448,7748-7820`）。

## 値と判定

最初の評価で `std::getenv` を呼び、設定値を `std::atoi` で整数化します。2 未満は 0（通常の 1 回 hand-off）、2 以上は `min(p, 16)` です。設定文字列全体の妥当性検査はありません。したがって未設定・空文字・数値に変換できない文字列は 0、`0`・`1`・負数も 0、`2`〜`16` はその値、`17` 以上は 16 になります。`atoi` の変換規則により、先頭空白や符号の後の数字は読まれ、数字の後ろの文字は判定されません（例: `"  +2tail"` は 2、`"0anything"` は 0）。`true` / `false` のような語は数値に変換できず 0 です。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 共通 prefill 実装 | 0（1 回 hand-off） | `2`〜`16`。`17` 以上は 16 に clamp | 空文字、非数値、`0`、`1`、負数（すべて 0 に変換、1 回 hand-off） |

値域変換は `engine/src/prefill/prefill.cpp:906-913`、行の分割は同ファイル `:915-920` です。`atoi` の表現範囲を超える入力に対する追加の検査はありません。

## 有効になる条件

- `Prefill` が後続 stage (`next_ != nullptr`) を持つ layer split である必要があります。初期化時に後続 stage がある場合だけ pinned hand-off buffer を用意し、分割数が 2 以上ならイベントも作ります（`engine/src/prefill/prefill.cpp:2488-2501`）。単一 GPU など後続 stage がない経路では分割転送は行いません。
- `STRATA_HANDOFF_PIPE` の分割転送は、`Prefill::run_impl()` の chunk-major hand-off 経路です。Metal は `Prefill::run()` から `metal_engine::prompt_run()` に直接進み、この共通 `run_impl()` 経路を通りません（`engine/src/prefill/prefill.cpp:9629-9651`）。
- 通常の `--prefill-pipe` などが chunk の切り方を決め、この変数は stage 間の hand-off の分割数を決めます。環境変数を読むコードに CLI 値との優先順位や上書きはありません（`engine/src/prefill/prefill.cpp:899-913,4298-4301,7748-7820`）。
- 分割 hand-off (`hp > 0`) では pinned host buffer と CUDA event を使います。通常の 1 回 hand-off (`hp == 0`) で条件を満たす場合に試みる peer-to-peer 経路は、分割 hand-off の場合には選択されません（`engine/src/prefill/prefill.cpp:7751-7770,7771-7795`）。
- `STRATA_HANDOFF_PIPE_WORKER` は転送分割とは別に後段を実行する thread の方式を選びます。分割 hand-off が有効で同変数が未設定または `atoi` 結果が非 0 なら、stage 所有の worker thread を遅延作成して再利用します。`=0`、空文字、非数値など `atoi` が 0 を返す値では chunk ごとの `std::async` に戻ります。分割数が 0 のとき、この worker 設定は使われません（`engine/src/prefill/prefill.cpp:921-927,7821-7832`）。
- GPU engine の共通 prefill ソースに実装があります。ビルド構成上、CUDA/HIP engine はこのファイルを含みます（`engine/cmake/strata_gpu_engine.cmake:482-488`）。実行時に必要な multi-GPU layer split が構成されていない場合、数値が有効でも転送分割は発生しません。

## 実行時の詳細

`handoff_pipe_pieces()` の `static const int` は初回呼び出し時にだけ環境を読み、その後はプロセス内で値を保持します。初期化時、後続 stage がある場合に初めて評価されます。従って、その評価後にプロセス内で環境を変更しても反映されません。CLI 引数、設定ファイル、他の環境変数による同値の上書きはありません（`engine/src/prefill/prefill.cpp:907-913,2488-2501`）。

分割数が有効な場合、初期化で hand-off buffer ごとに chunk 完了 event と最大 16 個の部分完了 event を作成します。各 chunk では行範囲をほぼ均等な連続区間に分け、前段の copy stream に device-to-host copy と部分 event を順に記録します。host は chunk 完了 event を待ち、後段は部分 event を stream wait してから各部分を host-to-device copy します。後段側で受け取る chunk が前段の chunk 全体と一致しない場合は、全部分を待った後に通常の 1 回 upload を行います。2 個の pinned buffer を交互に使います（`engine/src/prefill/prefill.cpp:915-920,4427-4444,7748-7820`）。

## ログと測定値

有効・無効を知らせる通常の on/off ログはありません。イベント作成に失敗すると `Prefill::init()` は `prefill: the layer split's hand-off events (STRATA_HANDOFF_PIPE)` を `err` に設定して失敗します。実行中の部分転送・event 同期に失敗すると `prefill: the layer split's hand-off: <CUDA error>`、後段 upload が失敗すると `prefill: the layer split's hand-off upload failed (STRATA_HANDOFF_PIPE): <CUDA error>` を `err` に設定して失敗します（`engine/src/prefill/prefill.cpp:2493-2501,4445-4448,7771-7785`）。`strata generate` は init/run の失敗時に `strata generate: <err>` を stderr に出し、終了コード 1 を返します（`engine/src/program/generate.cpp:24118-24123,24163-24167`）。

この変数単独の測定値は、参照したソースと関連資料から条件を特定できませんでした。

## 根拠

- `engine/src/prefill/prefill.cpp:899-920` — 設定値の変換、最大値、行区間の計算。
- `engine/src/prefill/prefill.cpp:2488-2501` — layer split 用 pinned buffer とイベントの初期化。
- `engine/src/prefill/prefill.cpp:4427-4448` — 後段で event を待ち、部分または全 chunk を upload する処理と失敗経路。
- `engine/src/prefill/prefill.cpp:7748-7834` — 前段の download、イベント、後段起動、および worker thread。
- `engine/src/prefill/prefill.cpp:9629-9651` — Metal 実行経路の分岐。
- `engine/src/program/generate.cpp:24118-24123,24163-24167` — init/run 失敗の stderr 表示と終了コード。
- `engine/cmake/strata_gpu_engine.cmake:482-488` — CUDA/HIP GPU engine での共通 prefill ソース組み込み。
