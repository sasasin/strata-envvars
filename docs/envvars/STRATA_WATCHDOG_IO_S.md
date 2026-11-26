# `STRATA_WATCHDOG_IO_S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP エンジンの serve watchdog が、リクエストの進捗が止まっているとき、ファイル tier の読み取りが続いていれば通常の watchdog 上限を超えて待つ合計秒数を指定する。読み取り中の低速・ページングを停止と誤認してエンジンを終了するのを遅らせる値であり、読み取り速度やファイル I/O 自体は変更しない。通常の進捗上限は `STRATA_WATCHDOG_S` が決める。`engine/src/program/generate.cpp:16261-16323`。

この変数を読む実装は CUDA/HIP 側の `generate.cpp` にあり、SYCL 側の同名 watchdog 節（`engine/sycl/src/program/generate.cpp:9543-9571`）は `STRATA_WATCHDOG_S` だけを読み、この変数は参照しない。登録データも backend を `cuda-hip` としている（`terminal/data/settings-register.json:52261-52271`）。

## 値と判定

`std::getenv` の結果を共通関数 `watchdog_seconds` に渡す。未設定（null）または空文字は既定値になり、警告は出ない。それ以外は `strtol(..., 10)` で基数 10 の `long` に変換し、変換失敗・範囲外・負値・数字の後ろに文字が残る場合は既定値へ戻して不正値フラグを立てる。0 以上 604800 以下を受け付け、上限は 604800 秒（7日）。`strtol` のため先頭空白と `+` 符号は受け付けるが、末尾空白は残余文字となり無効。`0anything`、`12s`、`-1`、`604801`、数値オーバーフロー、`true` は無効である。`engine/include/strata/core/watchdog_limits.hpp:16-29`。

| 条件 | unset / 空文字 | 有効値の例 | 無効値の例と fallback |
|---|---|---|---|
| CUDA/HIP serve watchdog | 解決済みの `STRATA_WATCHDOG_S` の10倍。`STRATA_WATCHDOG_S` も未設定・空文字なら 60 秒なので既定は 600 秒 | `0`、`1`、`600`、`604800` | `-1`、`true`、`0anything`、`12s`、`604801` は既定値へ戻り、警告 |
| SYCL | この変数を読まないため該当なし | 該当なし | この変数による判定なし |

`STRATA_WATCHDOG_S=0` のとき、この変数の既定値も 0 秒になる。ただし `STRATA_WATCHDOG_IO_S` に正数を明示しても watchdog thread 自体は起動しない（下記）。`STRATA_WATCHDOG_S` が無効なら同変数の fallback 60 秒を基にし、I/O 上限の既定は 600 秒。値の解決は `engine/src/program/generate.cpp:16265-16275`。

この読み取りに CLI 引数や設定ファイルによる上書きはなく、環境変数が指定されていればそれを parse し、未設定・空文字・不正値なら上記 fallback を使う。

## 有効になる条件

- CUDA/HIP の `engine/src/program/generate.cpp` にある serve watchdog 経路で使われる。SYCL 実装には I/O allowance の分岐がない（`engine/sycl/src/program/generate.cpp:9547-9571`）。
- `STRATA_WATCHDOG_S` の解決値が 1 秒以上で watchdog thread が起動している必要がある。0 なら thread が起動せず、この変数の値も効果を持たない（`engine/src/program/generate.cpp:16276-16278`）。
- リクエストが busy のまま heartbeat が進まず、通常上限 `STRATA_WATCHDOG_S` を超え、さらに `STRATA_WATCHDOG_IO_S` がその上限より大きい必要がある。I/O 上限が通常上限以下、または 0 の場合は延長しない（`engine/src/program/generate.cpp:16291-16301`）。
- 通常上限を超えた時点で、file tier activity のカウンターが直近10秒以内に動いている必要がある。コード上は1秒ごとにサンプルし、1秒間の差分が16以上なら活動時刻を更新する（`engine/src/program/generate.cpp:16292-16301`）。
- 同時に、セッションファイル等の処理が `progress_allow` で設定した個別の期限内なら、I/O allowance の有無に関わらずその期限までは終了しない（`engine/src/program/generate.cpp:16311-16312`; `engine/include/strata/core/progress.hpp:71-75`）。

## 実行時の詳細

変数は serve watchdog の初期化時に `std::getenv` で一度読み、秒数を値コピーして detached thread に渡す。リクエストごとの読み直しや関数内 static cache はなく、プロセス起動後の環境変更はこの watchdog に反映されない（`engine/src/program/generate.cpp:16265-16278`）。

watchdog は1秒ごとに進捗 heartbeat と file tier activity を調べる。heartbeat が進むかリクエストが busy でなくなると通常上限・I/O 上限の計時をリセットする。heartbeat が通常上限を超えても、I/O 上限以内で file tier activity が直近10秒にあれば待機を続け、次の延長判断では最長 `STRATA_WATCHDOG_IO_S` 秒（計時開始からの合計）まで待つ。最後の活動から10秒以上経った場合は延長を打ち切る。I/O 活動が条件を満たしている間、延長の案内ログは一度だけ出る（`engine/src/program/generate.cpp:16280-16309`）。

延長しない場合、または上限を使い切った場合、明示的な個別 allowance の期限を確認した後、停止理由と stall report を stderr に出し、GPU wait を解放して `std::abort()` でエンジンを終了する。値が生成 token や選択結果を変える処理はない（`engine/src/program/generate.cpp:16311-16321`）。

## ログと測定値

不正値を指定した場合は stderr に `strata serve: STRATA_WATCHDOG_IO_S is not a whole number of seconds (0 to 604800): using <秒> s` と出る。`STRATA_WATCHDOG_S` も不正なら名前を `and` で連結し、双方 fallback の場合は末尾に `(and 10 x that for the file tier)` が付く（`engine/src/program/generate.cpp:16272-16275`）。

通常上限を超えた際に I/O が続いていると、stderr に `strata serve: no step finished for <通常上限> s, but the file tier is still being read (slow storage or low RAM): waiting up to <I/O上限> s in all (STRATA_WATCHDOG_IO_S) (#1407)` と一度出る。最終的に停止すると `strata serve: no progress for ... s during a request (...) - stopping the engine so the server starts it again (issue #29)` と stall report が出てから abort する（`engine/src/program/generate.cpp:16301-16321`）。サーバーは死んだエンジンを再起動し、10分以内に3回停止した場合は再起動を止めてリクエストに 503 を返す（`terminal/serve/server.py:4865-4885,4965-4979`）。

`docs/DETAILS.md:1544-1545` は `STRATA_WATCHDOG_S` の通常の停止通知だけを説明し、この I/O allowance の挙動や測定値は記載していない。

## 根拠

- `engine/include/strata/core/watchdog_limits.hpp:16-29` — 秒数の parse、既定値、不正値判定、上限。
- `engine/src/program/generate.cpp:16261-16323` — CUDA/HIP 側の読み取り、I/O 活動条件、延長、警告、停止経路。
- `engine/sycl/src/program/generate.cpp:9543-9571` — SYCL 側には `STRATA_WATCHDOG_IO_S` の読み取りがないこと。
- `engine/include/strata/core/progress.hpp:17-27,61-75` — watchdog が参照する進捗状態と個別 allowance。
- `terminal/serve/server.py:4843-4885,4965-4979` — エンジン停止後のサーバー側再起動・crash-loop 抑止。
- `terminal/data/settings-register.json:52261-52289` — 候補一覧の backend と登録情報。
