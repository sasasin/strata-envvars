# `STRATA_WATCHDOG_S`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

serve エンジンのリクエスト中に進捗 heartbeat が止まったとき、エンジンを停止するまでの基本秒数を指定します。進捗が止まったまま GPU が待ち続ける状態を、サーバーがエンジンを起動し直せるよう終了させる watchdog です。環境変数はエンジン初期化時に一度読み取られ、値が正なら watchdog 用の detached thread を起動します。実行中に環境を変更しても再読込されません。

## 値と判定

値は `std::atoi` で `int` に変換されます。文字列全体の妥当性検査はありません。未設定なら 60 秒、変数を設定した場合は変換結果が使われます。

| 値 | watchdog の扱い |
|---|---|
| 未設定 | 60 秒を基本上限として有効 |
| 数値の正の値（例: `30`） | 指定秒数を基本上限として有効 |
| `0`、空文字、数値として読めない文字列 | 変換結果が 0 となり無効 |
| 負の数 | `limit > 0` を満たさず無効 |
| 数値の後ろに文字が続く値（例: `30sec`） | `atoi` が読む先頭の数値部分（この例では 30）を使用 |

`atoi` のため、小数秒は扱いません。通常 backend では正の `limit` に対し `STRATA_WATCHDOG_IO_S` が別途ファイル読み込み猶予を制御します。これはこの変数とは別の環境変数です。

根拠: `src/program/generate.cpp:8997-9009`, `sycl/src/program/generate.cpp:8438-8446`。

## 有効になる条件

- 変換後の `limit` が正であること。0 以下なら watchdog thread 自体を起動しません。
- エンジンがリクエストを処理中であること。`Progress::busy` が false の間は監視時間をリセットして待ち、リクエスト処理の `BusyScope` が true にすることで監視対象になります。
- prompt chunk、verify window、生成 token などで heartbeat が更新されていないこと。beat が変化すれば経過時間がリセットされます。

通常 backend（`src`）では、`STRATA_WATCHDOG_IO_S` の有効値が `limit` より大きく、かつその猶予時間内にファイル tier の読み込み活動が検出される場合、停止判定を延長します。`STRATA_WATCHDOG_IO_S` 未設定時の値は `limit * 10` 秒です。読み込み活動の検出条件は直近のカウンター増分が 16 以上で、ログは最初の延長時に一度出ます。SYCL backend の watchdog にはこの I/O 猶予処理がなく、`STRATA_WATCHDOG_S` の基本上限で判定します。

どちらの backend でも、セッションファイル操作の一部は `progress_allow()` が設定する明示的な期限までは停止判定されません。この許可は `STRATA_WATCHDOG_S` の値を変更するものではなく、許可期限を過ぎても進捗 beat がない場合は watchdog の対象に戻ります。

根拠: `src/program/generate.cpp:9004-9038`, `sycl/src/program/generate.cpp:8443-8457`, `include/strata/core/progress.hpp:17-27,53-68`, `src/program/generate.cpp:9749-9761,9789-9802`。

## 実行時の詳細

watchdog は1秒ごとに状態を確認します。リクエスト中で beat が変わらないまま基本上限に達し、適用可能な I/O 猶予またはセッション操作の期限延長もない場合、stderr に `strata serve: no progress for %d s during a request (%s) - stopping the engine so the server starts it again (issue #29)` を出します。通常 backend では、`CUDA_LAUNCH_BLOCKING=1` が設定されている場合に追加の注意文が付きます。続いて stall report を stderr に出し、GPU wait を解放する処理を呼び、stderr を flush して `std::abort()` します。したがって、これは要求をエラー応答だけで終える処理ではなく、エンジンプロセスを異常終了させる処理です。

通常 backend の I/O 猶予ログは `strata serve: no step finished for %d s, but the file tier is still being read (slow storage or low RAM): waiting up to %d s in all (STRATA_WATCHDOG_IO_S) (#1407)` です。SYCL では基本の停止ログに `CUDA_LAUNCH_BLOCKING` の注意文を加える分岐もありません。

進捗状態は `strata::core::progress()` の共有 `Progress` に保持されます。リクエスト範囲は `BusyScope` が busy 状態にし、終了時に idle に戻します。ヘッダーの説明とコード上では token、prompt chunk、verify window が heartbeat の単位です。停止直前の状態報告には、処理 stage や expert pool / verifier 等の診断関数が使われます。

## 文書との照合

`docs/DETAILS.md` は `STRATA_WATCHDOG_S` を秒単位の時間設定、0 を無効として説明し、停止ログとサーバーによるエンジン再起動を案内しています。現在の実装では未設定時の基本値が 60 秒です。ただし、通常 backend ではファイル tier の進行時やセッションファイル処理の明示的許可中に実際の停止判定が後ろへ延びるため、「60秒」をあらゆるケースの厳密な終了時刻とは解釈できません。docs の簡易説明にはこの backend 差と I/O 猶予の詳細はありません。

根拠: `docs/DETAILS.md:1813`; 実装 `src/program/generate.cpp:9002-9049`, `sycl/src/program/generate.cpp:8443-8466`。

## 根拠

- 全直接読み取り箇所: `src/program/generate.cpp:9002-9003`, `sycl/src/program/generate.cpp:8443-8444`。
- 通常 backend の値判定、I/O 猶予、停止処理: `src/program/generate.cpp:8997-9049`。
- SYCL backend の値判定と停止処理: `sycl/src/program/generate.cpp:8438-8466`。
- busy / beat / 許可期限の状態定義と更新: `include/strata/core/progress.hpp:17-27,53-68`; request scope `src/program/generate.cpp:9749-9761`。
- 関連するセッション処理の期限設定: `src/program/generate.cpp:9789-9802`。
- Strata の利用者向け説明: `docs/DETAILS.md:1813`。
