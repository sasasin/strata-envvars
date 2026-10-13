# `STRATA_FS_ADMIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Foresight swap space が、通常の resident cache 等から利用できなかった expert miss を何回観測してから、その expert を GPU slot に非同期コピーするかを指定します。miss 後に expert が CPU で処理されるか PCIe 経由で GPU に送られるかは別の計画条件で決まります。これは CUDA の serve 経路にある機能の調整値です。スロットを有効にする `STRATA_FS_SLOTS` が未設定または 0 以下なら Foresight swap space 自体が作られず、この値は読まれません。

## 値と判定

初期化時に `env_int("STRATA_FS_ADMIT", 1, 1)` で読みます。helper は `getenv` の結果を `atoi` に渡し、未設定なら既定値を使った後、最小値 1 に clamp します。したがって文字列全体の厳密な整数 parse ではありません。

| 環境値 | `admit` の値 |
|---|---:|
| 未設定 | 1 |
| 空文字、整数に変換できない文字列、0、負数 | 1（`atoi` の結果 0 以下を 1 に clamp） |
| 正の整数 | その整数 |
| 数字の後ろに文字がある文字列 | `atoi` が先頭から変換できた整数。例: `3x` は 3、`x3` は 0 から clamp され 1 |

符号や先頭空白を含む場合も `atoi` の変換規則に従います。値に上限 clamp はありません。`atoi` が表現範囲外の値に対して保証する結果はこの実装から定まりません。

## 有効になる条件

- `STRATA_FS_SLOTS` を `atoi` で変換した値が 1 以上であること。slots は最大 64 に制限されて初期化されます。
- `STRATA_VERIFY_DEVICE_PLAN` が設定され、かつ `atoi` が 0 以外になる場合は機能全体が無効です。このとき stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` と出ます。
- miss をコピーへ進めるには、expert source が pinned arena にあり、その expert の blob を取得できること、対象 layer に空きまたは再利用可能な slot があること、カード単位の window コピー budget を超えていないことも必要です。条件を満たさない miss はこの値に関係なくコピーされません。
- RouterLookahead から来る予測コピーは admission miss 回数の対象外です。`STRATA_FS_AHEAD` が予測を有効にしている場合、予測対象はこの閾値を待たずコピー要求に進みます。

## 実行時の詳細

設定値は `foresight_swap_from_env()` の初期化時に一度だけ読み、`ForesightSwap::admit` に保存します。以後、プロセス環境の変更は反映されません。各 verify plan の作成時、expert が通常の resident cache にも peer/helper にもなく、Foresight slot から利用できない場合に `note_miss()` が呼ばれます。`request_locked()` は同じ expert について既に slot コピー中なら何もしません。そうでなければ、`admit > 1` のときだけ miss 回数を数え、閾値に届くまでは戻ります。

miss 回数は `(layer, expert)` ごとに保持し、最後に数えた時点から完了 window 数が 4 を超えた場合にカウンタをリセットします。つまり現在の完了 window 数と前回 miss の差が 4 以下なら同じ連続 miss 群に数えます。カウンタは 255 で飽和します。既定値 1 ではこの集計分岐に入らず、最初の対象 miss で slot コピーを要求します。

閾値に達した後も、要求は即時 GPU 使用を保証しません。空き slot がなければ busy として見送られます。要求したコピーが完了していなければ `take()` は miss 扱いを続け、その間の窓で再要求が可能です。完了した slot が使われた場合は GPU group として計画され、実行後の完了窓数が slot の安全な再利用判定に使われます。

初期化成功時は stderr に `strata serve: foresight swap: %d slots per layer on %zu card(s), up to %d copies per card and window, admit after %d miss(es), reuse after %d windows` の形式で、採用された閾値を含む設定行が出ます。リクエスト終了時の統計には slot で処理した expert 数、コピー数、look-ahead 由来のコピー数、未着・slot不足・budget超過が出ます。コピー API または event 記録に失敗すると、初回は `strata serve: foresight swap: a copy failed - swap space off` が出て以後の要求は無視されます。

## 根拠

- `src/core/expert_source.cpp:4951-4976`: slots による有効化、device-plan 条件、`env_int` の定義、`STRATA_FS_ADMIT` の既定値と下限、初期化ログ。
- `src/core/expert_source.cpp:4876-4936`: miss と予測要求の分岐、4 window のカウント窓、slot・budget・pinned source 条件およびコピー要求。
- `src/core/expert_source.cpp:4839-4874,4939-4948`: コピー完了後の slot 利用と統計文字列。
- `src/core/expert_source.cpp:3730-3747`: expert cache / peer / helper / Foresight slot を確認した後に miss を通知する実行計画経路。
- `src/core/expert_source.cpp:2409-2412`, `src/program/generate.cpp:5492-5499`: RouterLookahead の予測要求と `STRATA_FS_AHEAD` の条件。
- `include/strata/core/foresight_swap.hpp:2-21,49-54`: 機能の説明と miss カウンタの役割。`docs/DETAILS.md:1680-1688` は `STRATA_FS_SLOTS` の概説と記載測定を扱いますが、`STRATA_FS_ADMIT` の parse や回数制御は説明していないため、上記の挙動は実装コードに基づきます。
