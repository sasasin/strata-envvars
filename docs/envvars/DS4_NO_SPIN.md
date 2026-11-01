# `DS4_NO_SPIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main` の HEAD と一致していました。

## 役割

Metal の DS4 runtime が committed `MTLCommandBuffer` の完了を待つとき、完了状態を短時間 busy-spin で確認する処理を省き、未完了なら直ちに `waitUntilCompleted` で待つようにします。待機完了自体を省く設定ではありません。参照は `metal/src/mtl_rt.mm` の `wait_spin()` に一か所だけあり、汎用 env helper や動的な名前渡しはありません。

## 値と判定

| 環境変数 | 未設定 | 設定時の判定 |
|---|---|---|
| `DS4_NO_SPIN` | busy-spin を行う | 値の内容に関係なく busy-spin を行わない |

実装は `std::getenv(...) != nullptr` の有無だけを判定します。したがって `DS4_NO_SPIN=0`、空文字、その他どの文字列も設定済みとして扱われ、数値変換や文字列比較はありません。未設定時は spin し、spin 上限時間は `DS4_SPIN_US` が未設定なら 20 ms、設定時は `std::atof(DS4_SPIN_US) * 1e-6` 秒です。この上限は `DS4_NO_SPIN` が設定されていれば使われません。`DS4_SPIN_US` が設定されていても `DS4_NO_SPIN` の判定を上書きしません。根拠: `metal/src/mtl_rt.mm:818-830`。

## 有効になる条件

この読み取りは Metal の DS4 runtime に限られます。`metal/src/mtl_rt.mm` は DS4 runtime 実装を `STRATA_DS4_RUNTIME` guard 内に持ち、`metal/CMakeLists.txt` は `ds4_rt_mm` として同ファイルをコンパイルし、この macro を付けて `strata_ds4` にリンクします（`metal/src/mtl_rt.mm:9-20,43-44,76`; `metal/CMakeLists.txt:151-165`）。このソース上、CUDA/HIP 等の別 backend や通常の `strata` ターゲットに同変数の読み取りはありません。

CLI 引数や別の設定による `no_spin` の上書きは見つかりません。プロセス起動後に環境を書き換えても、初回 `wait_spin()` 呼び出し時に初期化された `static const bool` は再評価されず、プロセス内の後続呼び出しでも維持されます。

## 実行時の詳細

`wait_spin()` は `DS4_NO_SPIN` が未設定の場合、command buffer の status を完了まで busy-spin で確認します。完了しないまま `DS4_SPIN_US` の予算を超えると spin を止め、status が未完了なら `waitUntilCompleted` でブロックします。`DS4_NO_SPIN` が設定済みの場合は最初から spin ループを飛ばし、未完了時にブロック待ちします。すでに完了済みならどちらの経路も追加のブロック待ちはしません。値の読み取りと判定結果の cache は、最初に `wait_spin()` が呼ばれた時点です。

`wait_spin()` は `Context::wait_mark()` と `Context::flush_runs()` から呼ばれます。前者は deferred command buffer の mark を待ち、後者は in-flight buffer を待つ処理です（`metal/src/mtl_rt.mm:844-849,855-895`）。この変数について専用ログ、終了、失敗経路はありません。待機後も command buffer が `Completed` でない場合、呼び出し側が stderr に `mtl: deferred command buffer failed: %s` を出します。`DS4_ERRINFO` も設定されている場合は追加情報を出しますが、これらは `DS4_NO_SPIN` によるログではありません（同:850-852,892-895）。

## 根拠

- `metal/src/mtl_rt.mm:818-830` — `DS4_NO_SPIN` の設定有無判定、static cache、`DS4_SPIN_US` と fallback 予算、spin と block wait。
- `metal/src/mtl_rt.mm:844-852,855-895` — `wait_spin()` の呼び出し元と待機後のエラー観測。
- `metal/CMakeLists.txt:151-165` — `STRATA_DS4_RUNTIME` 付きの Metal DS4 runtime build/link。
