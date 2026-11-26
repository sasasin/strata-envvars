# `STRATA_PIPE_ADAPT_EVERY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の multi-GPU layer split で、`--batch-groups` による pipelined slot groups を使うとき、VRAM expert tier の適応ラウンドを何 group windows ごとに実行するかを指定する。既定は無効（0）で、通常の pipelined loop は独自の適応ラウンドを開始しない。正の値を指定すると、指定数の group windows が完了した後に新しい group の開始を止め、実行中の group を完了させてから適応ラウンドを実行する。`auto` は初期間隔 32 から始め、ラウンドで移動した expert 数に応じて間隔を調整する。対象は `engine/src/program/generate.cpp` の pipelined loop と `engine/include/strata/program/batch_groups.hpp` の判定 helper（`pipe_adapt_every`、`pipe_adapt_due`、`pipe_adapt_next`）。

この変数は適応 tier 自体を有効化する設定ではない。`--adapt-every` と `--adapt-swaps` が正で、VRAM に全 expert が載っていないなどの条件を満たして tier が有効な場合にだけラウンドを実行できる。起動時の案内ログは `--serve`、batch、複数 group、multi-GPU の条件下だけで出る（`engine/src/program/generate.cpp:11813-11826`、`15001-15002`、`17529-17533`）。

## 値と判定

`generate.cpp` は環境値を `std::getenv` で取得し、helper は `auto` だけを文字列全体で `std::strcmp` 比較する。それ以外は `std::atoi` の結果が正ならその整数を group-window 間隔として使い、0 以下なら無効にする。厳密な数値文字列検査や上限 clamp はない。`atoi` が読む先頭の空白や符号、数値以降の文字列の扱いに従う（例えば `" 12tail"` は 12、`"0anything"` と `"off"` は 0）。`auto` は小文字の完全一致だけで、大文字小文字を区別する。整数範囲を超える入力の扱いはこの実装で検査されない（`engine/include/strata/program/batch_groups.hpp:29-39`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 共通 | 0（無効） | `"auto"`（初期値 32）、`"1"`、`"128"` など `atoi` の結果が正の値 | 空文字、`"0"`、`"-5"`、`"off"`、`"AUTO"`、`"0anything"` など `atoi` が 0 以下を返す値 |

`--adapt-every` は適応 tier の有効化・通常の batch window 側の間隔を決め、`STRATA_PIPE_ADAPT_EVERY` は pipelined loop 側の group-window 間隔を決める。どちらかが他方の値を上書きする仕組みではない。`--adapt-every 0` または `--adapt-swaps 0` なら環境変数が正値でも tier が無効である。`--adapt-swaps` は1回の適応で選べる上限にも使われる。CLI 値の parse 箇所は `engine/src/program/generate.cpp:4058,4202`、起動時に tier usage を用意する条件は `15001-15002` にある。

## 有効になる条件

- 実行経路が `--serve` で、batch が正、`--batch-groups > 1`、複数 GPU の layer split であること。pipelined loop 自体も batch、複数 group、複数 stage を条件にする（`engine/src/program/generate.cpp:11815-11817,17529-17533`）。
- 適応 tier が有効であること。少なくとも `--adapt-every > 0`、`--adapt-swaps > 0`、全 expert が VRAM 常駐ではなく GPU cache slot がある場合に usage 配列が用意され、loop は `!drive.d.usage.empty()` を tier 有効条件としている（`engine/src/program/generate.cpp:14932-14933,15001-15002,18018-18027`）。適応の swap 候補は使用量、常駐状態、最小 gain、`--adapt-swaps` 上限などでも絞られる（`15349-15379`）。
- `--adapt-async` の job が動いていないこと。`pipe_adapt_due` は async tier 中に false を返す（`engine/include/strata/program/batch_groups.hpp:62-76`、`engine/src/program/generate.cpp:18018-18027`）。また `--adapt-async 1` は pipelined groups と併用できない経路として起動時に無効化理由が出る（`engine/src/program/generate.cpp:11796-11811`）。
- Slot groups の横で prompt read が進行中でないこと、前回 swap のコピーが未完了でないこと。どちらも round の開始を保留する（`engine/include/strata/program/batch_groups.hpp:62-76`）。
- `STRATA_ADAPT_MID` は中程度の cache coverage で `--adapt-every` / `--adapt-swaps` の既定値を調整し得る。`STRATA_TINY_CACHE` は小さい cache の swap 数を調整し得る。これらはこの変数の値を変更せず、tier の有効性や1 round の swap 数に影響し得る（`engine/src/program/generate.cpp:14943-14975`）。`STRATA_CACHE_PIN_FRAC` 等による pinning も選択可能な cache entry に影響する（`14976-14999,15364-15379`）。

条件を満たさない場合、この値は pipeline の適応を発生させない。起動案内では `--adapt-every` または `--adapt-swaps` が無効なら ` - but the adaptive tier is off` が付く（`engine/src/program/generate.cpp:11818-11826`）。

## 実行時の詳細

起動案内用に条件付きで1回読み、pipelined loop の初期化時に再度 `getenv` して `pa_auto` と `pipe_adapt_every` に保持する。loop 中に環境を読み直す処理はなく、この値の実行中変更は反映されない（`engine/src/program/generate.cpp:11815-11826,18014-18017`）。static cache ではなく、当該 loop のローカル状態として保持する。

固定の正値 `N` では、完了済み group windows 数が前回 round から `N` に達すると新しい stage 0 group を開始せず、in-flight group がなくなったところで `snapshot_usage` と `adapt` を実行する。adaptive refill が失敗すると stdout に `ERR an adaptive refill failed` を出して処理を失敗終了する。round 後は `apply_pending(true)` で swap copy を待って cache table を更新し、次の group launch に進む（`engine/include/strata/program/batch_groups.hpp:73-76`、`engine/src/program/generate.cpp:18118-18120,18135-18138,18330-18347`）。

`auto` は 32 windows で開始し、round の swap 数が `--adapt-swaps` の 75% 以上なら間隔を半分（下限32）、25% 以下なら倍（上限256）、中間なら据え置く。閾値判定には整数演算 `swaps * 4` と `cap * 3` / `cap` を使う（`engine/include/strata/program/batch_groups.hpp:26-29,51-59`、`engine/src/program/generate.cpp:18341-18345`）。

## ログと測定値

適用条件を満たす `--serve` 起動時、stderr に次のいずれかを出す。tier が無効なら括弧書きの補足が続く（`engine/src/program/generate.cpp:11818-11826`）。

- auto: `strata batch: STRATA_PIPE_ADAPT_EVERY=auto: the pipelined groups run an adaptive-tier round every %d to %d group windows, more often while the rounds find experts to move (the pipeline empties for each)%s`
- 正値: `strata batch: STRATA_PIPE_ADAPT_EVERY=%d: the pipelined groups run an adaptive-tier round every %d group windows (the pipeline empties for it)%s`

pipelined batch の timing 行には、有効値なら `; adaptive tier (STRATA_PIPE_ADAPT_EVERY%s): %lld rounds, %lld experts swapped in, %.0f ms%s` が追加される。`auto` の場合は末尾に現在の間隔が付く。0 相当では起動案内・timing 行の適応情報は出ない（`engine/src/program/generate.cpp:18360-18371`）。適応 refill 失敗時は stdout の `ERR an adaptive refill failed` で loop が失敗する（`18334-18339`）。

`docs/BATCHING.md:425-440` は同じ pipeline drain・prompt read 中の停止・`--adapt-async 1` との関係、および2x RTX 5090、layer split 25、Swift-Qwen3.8-Flash-Next IQ3_S、`--batch 6 --batch-groups 2`、resident experts、profile-filled cache、`--adapt-every 16`、6 streams × 1,024 greedy tokens、8 bursts、各設定2 fresh engines の測定表を記載する。これは資料上の条件付き測定であり、この調査で再測定していない。コードでは `auto` も実装されており、資料の `N` 表記より値判定の詳細は helper に従う。

## 根拠

- `engine/include/strata/program/batch_groups.hpp:26-39` — `auto`、`atoi`、既定値と固定間隔の判定。
- `engine/include/strata/program/batch_groups.hpp:51-76` — auto 間隔の調整規則と round 開始条件。
- `engine/src/program/generate.cpp:11813-11826` — 起動条件、環境読み取りと stderr 案内。
- `engine/src/program/generate.cpp:14932-15002` — adaptive tier の coverage / CLI 条件と usage 配列。
- `engine/src/program/generate.cpp:15349-15379` — 適応 refill と swap 選定。
- `engine/src/program/generate.cpp:17529-17533,18014-18027,18118-18120,18135-18138,18330-18347,18360-18371` — pipelined path、loop 内の値保持、適用・失敗・結果ログ。
- `docs/BATCHING.md:411-440` — 実装説明と条件付き測定資料。
