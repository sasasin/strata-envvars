# `STRATA_PIPE_HELPER_SIBLING`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Linux の SYCL verifier が stepped mode で CPU expert pool 用の helper thread を起動するとき、その thread を host thread の SMT sibling CPU に配置します。host thread が単一 CPU に pin されている場合に限り、その CPU affinity mask から sibling 番号を探します。GPU の処理や pool の内容は変えず、helper thread の CPU affinity を指定する設定です。

## 値と判定

変数は `env_on()` で判定します。未設定、空文字、先頭文字が `0` の値は無効です。それ以外は有効で、文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | 無効（既定） |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、空白で始まる値、その他先頭が `0` でない値 | 有効 |

有効でも host thread が単一 CPU に pin されていない、または sibling を特定できないと、helper thread は継承した affinity のままです。CLI 引数による同変数の上書きはありません。`STRATA_VERIFY_PIPE=0` は別の条件として helper thread 経路そのものを無効にします。

根拠: `sycl/src/core/verify.cpp:94-97,111-120,2211-2224`。

## 有効になる条件

- Linux 上で SYCL 版 Strata が動作していること。この読み取りと affinity 設定は `__linux__` の条件付きコード内にあり、Linux 以外では関数が `-1` を返すだけです。
- `STRATA_VERIFY_STEPPED` が有効で、all-resident (`ar_on()`) ではなく、`STRATA_VERIFY_EAGER` が未設定で、capture された segment があること。これは stepped run の条件です。
- stepped serve 中に pool 用 helper を使う分割点に到達すること。さらに `STRATA_VERIFY_PIPE` が無効でなく、次 segment が split segment である必要があります。`STRATA_VERIFY_PIPE` は未設定なら有効、値の先頭が `0` なら無効です。
- host thread の affinity mask がちょうど 1 CPU であること。Linux sysfs の `/sys/devices/system/cpu/cpu<host>/topology/thread_siblings_list` から host CPU 以外の最初の番号を見つけたときだけ、その番号を helper に設定します。

この変数単独では stepped mode や pipeline を有効にしません。条件を満たさない経路では helper の配置に影響しません。`STRATA_VERIFY_STEPPED` の初期判定も `STRATA_VERIFY_PIPE` の判定もそれぞれ初回評価値を static に保持します。

根拠: `sycl/src/core/verify.cpp:102-105,111-152,1830-1837,2160-2164,2209-2235`。

## 実行時の詳細

`pipe_helper_cpu()` は `STRATA_VERIFY_PIPE` が有効で split segment を処理する時点で呼ばれます。Linux では関数内 static 値の初期化時に対象変数を読み、host affinity と sysfs topology を一度調べます。その後は同一プロセス中に環境値や affinity を変更しても再評価されません。変数が有効で host affinity が複数 CPU などの場合は stderr に `strata verify: STRATA_PIPE_HELPER_SIBLING: host thread is not pinned to one CPU; unchanged` を出して、配置を変えません。

単一 CPU の場合、sysfs の sibling list はカンマ区切りと範囲（例 `0,8`、`0-1`）を走査し、host CPU と異なる最初の番号を選びます。sysfs を読めない場合や他の番号が見つからない場合は sibling を `-1` として、stderr に `strata verify: pipelined pool helper on CPU -1 (host thread CPU <番号>): no SMT sibling, unchanged` を出します。番号が見つかった場合も同じログ形式で選択 CPU を表示します。

helper thread の開始時に `pthread_setaffinity_np()` でその CPU を指定しますが、戻り値は検査していません。そのためログは選択した CPU を示しますが、OS が affinity 変更を受理したことまでは確認しません。helper が投げた `std::exception` は `verify: pool: <例外内容>` として呼び出し側へ返り、thread 作成や join の例外は `verify: pipelined serve: <例外内容>` になります。これらの serve 失敗は stepped window を失敗させます。`STRATA_PIPE_HELPER_SIBLING` 自体の値が原因で終了や失敗になる分岐はありません。

根拠: `sycl/src/core/verify.cpp:111-151,2185-2240,2258-2270`。

## 根拠

- 環境値判定 helper: `sycl/src/core/verify.cpp:94-97`。
- sibling CPU の探索、sysfs 読み取り、診断ログ、Linux 以外の no-op: `sycl/src/core/verify.cpp:107-152`。
- stepped mode の条件と helper thread 起動・affinity 適用: `sycl/src/core/verify.cpp:2160-2164,2209-2240`。
- stepped capture 条件: `sycl/src/core/verify.cpp:1830-1837`。
