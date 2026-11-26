# `STRATA_PIPE_HELPER_SIBLING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Linux の SYCL stepped verifier で、CPU expert の pool 処理を行う helper thread を、呼び出し元の host thread が使う CPU の SMT sibling に割り当てます。host thread が 1 CPU に pin されている場合に限る opt-in です。変数が未設定または無効なら、Strata は helper thread の affinity を変更しません。CPU 選択と affinity 設定は `engine/sycl/src/core/verify.cpp` の `pipe_helper_cpu()` と stepped serve 内で行います（同ファイル:151-154, 196-240, 2525-2543）。

## 値と判定

Linux では `pipe_helper_cpu()` の初回呼び出し時に `env_on("STRATA_PIPE_HELPER_SIBLING")` が環境値を読みます。`env_on()` は値が未設定でなく、空文字でなく、先頭文字が `0` でない場合に true を返します。数値変換や文字列全体の比較はしません（`engine/sycl/src/core/verify.cpp:151-154, 200-203`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| Linux の SYCL stepped verifier | helper thread の affinity を変更しない | `1`、`true`、`2`、` 1`（先頭文字が `0` 以外の非空値） | 空文字、`0`、`0anything` |
| Linux 以外 | helper thread の affinity を変更しない | なし（この変数を読み取らない） | なし |

大文字小文字、空白、数値としての妥当性は検査されません。設定値の後続文字は判定に影響しません。Linux でも値が有効なだけでは CPU は変更されず、後述の affinity と SMT sibling の条件を満たす必要があります（同ファイル:200-240）。

## 有効になる条件

- 実行経路が SYCL verifier の stepped run であること。`STRATA_VERIFY_STEPPED` が有効で、`ar_on()` が false、`STRATA_VERIFY_EAGER` が未設定で、捕捉済み segment がある場合に stepped run へ入ります（`engine/sycl/src/core/verify.cpp:192-194, 2098-2105, 2476-2495`）。
- `STRATA_VERIFY_PIPE` が `0` で始まる値で無効化されていないこと。未設定や空文字を含め、先頭文字が `0` でなければ pipe は有効です（同ファイル:2525-2528）。
- 次の segment が split segment（`seg_kind_[T][nxt] == 0`）であること。この場合だけ pool を別 thread で実行します。その他の segment では `run_pool()` をその場で実行します（同ファイル:2525-2557）。segment の split は `STRATA_VERIFY_SPLIT` が `0` で始まらない場合に記録されます（同ファイル:2067-2077）。
- 対象は Linux のみです。Linux では呼び出し元 host thread の affinity 取得が成功し、許可 CPU がちょうど 1 個である必要があります。そうでなければ sibling を選ばず、stderr に `strata verify: STRATA_PIPE_HELPER_SIBLING: host thread is not pinned to one CPU; unchanged` を出します（同ファイル:200-209）。
- host CPU の `/sys/devices/system/cpu/cpu<番号>/topology/thread_siblings_list` から host CPU 以外の sibling 番号を読み取れる必要があります。見つからない場合も affinity は変わりません（同ファイル:210-240）。
- stepped run では `--remote-expert-opt` が先に拒否されます。この変数でその経路を有効化することはできません（同ファイル:2492-2495）。

## 実行時の詳細

`pipe_helper_cpu()` は Linux でのみ環境値を参照し、選択 CPU を関数内 `static const int` に保存します。環境値・呼び出し元 thread の affinity・sysfs の sibling をプロセス内で最初の呼び出し時に判定し、その後の変更は再評価されません。Linux 以外では環境値を読まず `-1` を返します（`engine/sycl/src/core/verify.cpp:200-240`）。

pipe 対象 segment では、Strata は `std::thread` を作って `run_pool()` を呼び出します。Linux で sibling CPU が選べた場合だけ、thread 内から `pthread_setaffinity_np()` でその CPU を設定します。戻り値は無視されるため、設定失敗時の専用 fallback やログはありません。`-1` の場合は thread affinity を設定せず、継承した mask のままです（同ファイル:2525-2543）。thread と verifier の処理は flag A を待って segment を投入し、thread を join します（同ファイル:2544-2552）。

関数内 static のため値の読み取りは最初の pipe 対象 split segment まで遅延します。`STRATA_VERIFY_PIPE` の判定も `serve` 内の static で初回評価後に cache されます。CLI 引数によるこの CPU 選択の上書きはコード上確認できません（同ファイル:2525-2539）。

## ログと測定値

host thread が 1 CPU に pin されていない場合の警告は上記のとおりです。CPU 選択処理まで進んだ場合は `strata verify: pipelined pool helper on CPU %d (host thread CPU %d)%s\n` を stderr に出し、sibling がないとき suffix に `: no SMT sibling, unchanged` を付けます（`engine/sycl/src/core/verify.cpp:206-234`）。この変数固有の終了・失敗経路はなく、thread affinity API の失敗も無視されます。コード・関連資料でこの変数による性能測定値は確認できません。

## 根拠

- `engine/sycl/src/core/verify.cpp:151-154` — `env_on()` の値判定。
- `engine/sycl/src/core/verify.cpp:196-240` — Linux 限定の遅延読み取り、CPU affinity 条件、SMT sibling 検出とログ。
- `engine/sycl/src/core/verify.cpp:2067-2077, 2098-2105, 2476-2495` — stepped run と split segment の成立条件。
- `engine/sycl/src/core/verify.cpp:2525-2557` — pipe 分岐、helper thread、CPU affinity 設定、join と通常実行への分岐。
