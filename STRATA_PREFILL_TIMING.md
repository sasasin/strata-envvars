# `STRATA_PREFILL_TIMING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

プロンプト処理（prefill）の GPU 実行時間をフェーズ別に計測し、処理完了後に標準エラーへ出します。CUDA系とSYCL系の `Prefill::run_impl()` にあるローカルタイマーが環境変数を読みます。多 GPU の peer がある場合は peer 側のタイムラインも計測します。

計測は処理時間の観測用です。計算や入力を選ぶ分岐には使いません。ただし CUDA event / SYCL event の記録など計測処理が加わるため、計測中の実行時間が無計測時と同一とは限りません。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 計測しない。通常のフェーズイベントと timing ログを出さない |
| 空文字を含む任意の設定値 | 計測する。値の内容、数値、大小文字は調べない |

CUDA系・SYCL系とも `std::getenv(...) != nullptr` で判定します。したがって `0`、`false`、空文字も設定されていれば有効です。タイマーは `run_impl()` 内で作られるたびに値を読みます。プロセス起動時に一度だけ固定する `static` キャッシュではありません。

## 有効になる条件

- `Prefill::run_impl()` が実行されること。値の設定だけでは prefill は起動しません。
- CUDA系は `src/prefill/prefill.cpp`、SYCL系は `sycl/src/prefill/prefill.cpp` の実装が対象です。
- peer GPU 用タイマーは `m.pp` がある場合だけ有効です。peer がなければ `pe.on` を無効にします。
- SYCLでは別の `STRATA_PREFILL_SYNC` が設定されていると、`STRATA_PREFILL_TIMING` の有無とは独立して各計測マークで queue を待ち、`strata prefill sync:` ログを出します。これはこの変数単独の判定ではありません。

## 実行時の詳細

各チャンクの先頭や計算フェーズの境目で、主 GPU の compute stream / queue にイベントを記録します。隣り合うイベント間の時間を先行マークのフェーズに加算するため、ホストの expert grouping や expert copy を待つ区間も、待っていた側のフェーズ時間に含まれます。CUDA系のフェーズ名には `embed+steps`、`router+shared`、`wait copy`、`dequant`、`gemm gate/up`、`gemm down`、`combine` などがあります。SYCL系も同じフェーズ表を使います。

通常完了時、stderr に `strata prefill timing:` で始まる行を出します。行には token 数、GPU timeline の合計、wall time、host staging 時間と、時間が正だったフェーズごとの ms / 合計に対する割合が含まれます。続く行はホスト側の chunk setup、chunk 待ち、chunk 後処理、PLE 時間です。peer GPU がある場合は別行に peer の idle / MoE 入出力・GEMM 時間、MoE layer や row 数を出し、peer-streamed experts があれば追加行を出します。

CUDA系ではフェーズイベントの区間を layer の同期地点で集計し、終了時に残りを集計します。peer 側も必要な同期後に集計します。SYCL系も layer の同期地点と終了時に集計します。またSYCL系は `STRATA_PREFILL_TIMING` が有効なとき、チャンク開始前に queue を待ち、各 setup 区間の経過を `strata prefill timing: setup ...` として逐次出力します。このため、CUDA系とSYCL系で出力・計測時の待機に差があります。

## 根拠

- `src/prefill/prefill.cpp:1952-2037` は CUDA系のフェーズ表、設定有無の判定、イベント記録・集計、peer timer を定義します。`2095-2098` は `run_impl()` 内でのタイマー生成と peer 不在時の無効化です。
- `src/prefill/prefill.cpp:2133-2139, 3160-3163, 4111-4140` はチャンクの計測開始、layer同期時の集計、完了時の集計および出力を示します。
- `sycl/src/prefill/prefill.cpp:1970-2099` は SYCL系の同等の判定と event 記録・集計です。`2167-2170` はタイマー生成、`2225-2231` はチャンク開始前の待機と setup ログ、`3335-3350, 4615-4654` は集計および出力です。
- `docs/DETAILS.md` などの通常ドキュメントにこの変数の説明や、この計測機能の測定条件は見つかりませんでした。ベンチ結果はこの変数の挙動や一般的な性能値の根拠には使っていません。
