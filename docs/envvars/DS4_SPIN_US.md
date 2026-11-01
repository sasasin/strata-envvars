# `DS4_SPIN_US`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal runtime が command buffer の完了を待つとき、ブロッキング待ちに移る前に CPU で状態を spin poll する時間予算をマイクロ秒単位で指定します。待ち処理は `metal/src/mtl_rt.mm` の `wait_spin()` にあります。この変数自体について Strata が行う処理は値を読み、秒へ換算し、poll loop の終了条件に使うことです。

## 値と判定

`wait_spin()` の関数内 static 初期化で `getenv()` を確認し、設定されていれば `std::atof(value) * 1e-6` 秒、未設定なら `20e-3` 秒（20 ms）を使います。設定値を整数のマイクロ秒数として厳密に検査する処理、範囲制限、fallback はありません。

| 値 | 判定と結果 |
|---|---|
| 未設定 | 既定の 20 ms を使う |
| 空文字 | 設定済みとして `atof("")` が 0 を返し、予算 0 秒になる |
| 数値文字列 | `atof` が先頭から変換できる数値を double として読み、秒へ換算する。例: `250` は 250 µs |
| 数値の後ろに文字がある | `atof` が変換した数値部分を使う。例: `250us` は 250 µs |
| 数値に変換できない文字列 | `atof` の変換結果 0 により予算 0 秒になる |
| 0 または負数 | 予算が 0 以下となり、完了していない状態を最初に確認した時点で poll を抜ける |
| 正数 | 指定秒数を超えるまで poll し、その時点で command buffer が未完了ならブロッキング待ちへ進む |

NaN や無限大を含む値の妥当性検査もありません。`atof` の変換結果が NaN なら `経過時間 > 予算` の比較は成立しないため status が Completed 以上になるまで poll が続き、正の無限大も時間切れになりません。負の無限大は負数と同じく直ちに時間切れになります。

## 有効になる条件

`metal/src/mtl_rt.mm` は Foundation と Metal を import する Objective-C++ runtime です。対象箇所は `STRATA_DS4_RUNTIME` が定義された場合に使われる Metal command buffer の待ち経路です（同ファイル 9-20, 43-57, 744-899 行）。CUDA/HIP/SYCL の待ち処理をこの変数が制御する参照はありません。

同じ `wait_spin()` で `DS4_NO_SPIN` も判定されます。`DS4_NO_SPIN` が unset であれば `DS4_SPIN_US` の予算で poll します。`DS4_NO_SPIN` が設定されていると、空文字を含め値にかかわらず poll loop を飛ばし、command buffer が未完了なら `waitUntilCompleted` へ進みます。この場合 `DS4_SPIN_US` の数値は待ち方に影響しません。CLI 引数や別設定からこの予算を上書きする経路は、対象名の全参照と `wait_spin()` 呼び出し経路にはありません。

## 実行時の詳細

予算は `wait_spin()` の static local なので、プロセス内で最初に呼ばれた時に一度だけ評価されます。その後に環境変数を変更しても値は再読込されません。初期化後は、`DS4_NO_SPIN` が偽なら `cb.status < MTLCommandBufferStatusCompleted` の間 status を busy-poll し、経過時間が予算を超えると loop を抜けます。まだ未完了なら `[cb waitUntilCompleted]` を呼びます。値を大きくするとブロッキング待ちまでの CPU poll 時間が長くなり、小さくすると早くブロッキング待ちに移ります（`metal/src/mtl_rt.mm:818-830`）。

この関数は `Context::wait_mark()` と `Context::flush_runs()` から呼ばれます。前者は `ds4_ctx_wait()` の token 待ちに使われ、後者は deferred command buffer を flush する際に使われます（`metal/src/mtl_rt.mm:844-849,884-895`; `metal/src/engine/ds4_finish.cpp:2718-2721,2728-2735`）。予算値そのものを示すログはありません。待ち後に status が Completed 以外なら stderr に `mtl: deferred command buffer failed: ...` が出ます。`wait_mark()` では `DS4_ERRINFO` が設定されていると追加の `mtl: recent:` と `mtl: info:` も出力され、`flush_runs()` では `DS4_ERRINFO` 設定時に `mtl: failed cb held:` が出ます（`metal/src/mtl_rt.mm:850-852,892-894`）。この変数による明示的な終了処理や timeout エラーはありません。

## 根拠

- `metal/src/mtl_rt.mm:818-830` — `DS4_NO_SPIN` と `DS4_SPIN_US` の読み取り、既定値、換算、poll と blocking wait。
- `metal/src/mtl_rt.mm:844-852,884-895` — 待ち関数の呼び出しと失敗時のログ。
- `metal/src/engine/ds4_finish.cpp:2711-2721,2728-2735` — DS4 context の mark/wait と flush の呼び出し元。
