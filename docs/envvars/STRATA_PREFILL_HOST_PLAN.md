# `STRATA_PREFILL_HOST_PLAN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--prefill auto` が GPU expert cache に合わせて選んだ prompt chunk と staging ring を、RAM copy・page cache・model file からの読み込み量も見積もって再評価する機能の停止スイッチです。計画器は chunk と ring の候補を比較し、予測時間が十分短くなる候補があれば選びます。重みや expert の選択は変えず、prompt の chunking と ring の形を調整します（`engine/src/program/generate.cpp:11417-11431,11468-11518`、`engine/include/strata/program/prefill_plan.hpp:10-24,106-127`）。

この変数は `host_plan_chunk` 内で直接 `std::getenv` されます。サーバーの prefill 設定経路と、通常の prompt 処理経路の両方から呼ばれます（`engine/src/program/generate.cpp:11432-11441,12629-12663,23990-24024`）。

## 値と判定

値全体を parse したり真偽文字列を比較したりせず、`getenv` が返す文字列の先頭文字だけを見ます。未設定、空文字、先頭文字が `0` 以外の値では停止しません。先頭文字が `0` なら、後続文字列に関係なく計画器を呼び出し元の chunk のまま返します（`engine/src/program/generate.cpp:11438-11441`）。

| 条件 | unset | 設定時に計画器を止める値 | 計画器を止めない値 |
|---|---|---|---|
| `host_plan_chunk` が呼ばれた場合 | 有効扱い | 先頭が `0`：`0`、`0anything`、`00` | 空文字、`1`、`true`、`false`、`anything`、先頭が空白の ` 0` |

数値変換・数値妥当性の確認・大文字小文字の比較はありません。したがって `false` も有効扱いで、`0false` は停止値です。表の判定は計画器に入ったときのもので、下記の実行条件を満たさない経路では値に関係なく計画は行われません（`engine/src/program/generate.cpp:11438-11441`）。

## 有効になる条件

- `--prefill auto` などにより `o.prefill_auto` が真で、入力 chunk が正であること。固定値の `--prefill N` では計画器を通りません（`engine/src/program/generate.cpp:11439-11441,23994-24010`）。
- `srcp == &src` であること（`engine/src/program/generate.cpp:11439-11441`）。
- `STRATA_RING_BYTES` が未設定、または先頭文字が `0` 以外であること。この変数が先頭 `0` なら ring byte budgeting 自体が無効になり、host plan も早期 return します（`engine/src/prefill/prefill.cpp:833-835`、`engine/src/program/generate.cpp:11439-11441`）。
- GPU cache が全 expert を保持していないこと。全 expert が cache に入る場合は追加計画なしで元の chunk を返します（`engine/src/program/generate.cpp:11442-11447`）。
- `sample_host_memory()` が値を返すこと。メモリ情報を取得できなければ元の chunk のままです。実装には Windows、Linux、macOS の取得分岐があります（`engine/src/core/conversation_memory.cpp:411-440`）。
- 通常の prompt 処理では、prefill borrow が許可され、host residency table と device residency table があり、元の lend scan が正の slot 数を返し、対象 prompt が 1,024 token を超えることも必要です（`engine/src/program/generate.cpp:23990-24010`）。
- サーバー側では prefill borrow と device residency table が使える経路で、auto chunk と ring-byte の scan が行われる必要があります（`engine/src/program/generate.cpp:12449-12455,12621-12657`）。

候補比較で baseline から chunk または ring が変わっても、予測時間の改善が baseline の 5% 以上かつ 2 秒以上でなければ元の候補を維持します（`engine/include/strata/program/prefill_plan.hpp:106-127`）。

## 実行時の詳細

この環境変数は `host_plan_chunk` の呼び出しごとに `std::getenv` で読み、結果を static 変数などに cache しません（`engine/src/program/generate.cpp:11432-11441`）。通常の prompt 経路では、borrow slot の算出後、1,024 token 超の prompt を処理するときに呼び出します（`engine/src/program/generate.cpp:23990-24010`）。サーバー経路では expert cache / ring の自動 scan 中に呼び、必要なら選んだ plan chunk を `pf_plan_chunk` に分けて保持します（`engine/src/program/generate.cpp:12629-12663`）。

計画器は GPU cache の容量と lend 量、RAM copy が保持する領域、page cache に残る容量、PCIe と drive の速度を使って chunk × ring の候補を採点します。入力値の `compute_tok_s` は既定で 1,200 token/s で、`STRATA_PREFILL_PLAN_TOKS` の `atof` 結果が正ならその値に置き換わります。drive 速度は既定推定を使い、`STRATA_SSD_GBPS` の `atof` 結果が正なら上書きします（`engine/src/program/generate.cpp:11446-11467,1891-1905`、`engine/include/strata/program/prefill_plan.hpp:34-39,81-99`）。

選ばれた chunk が現在の chunk より小さく、prompt が現在の chunk 1 個に収まらないとき、通常経路は prompt を等分に近い chunk に分けます。1 chunk に収まる prompt は既存の 1 回読み込みを維持します（`engine/src/program/generate.cpp:24011-24024`、`engine/include/strata/program/prefill_plan.hpp:130-149`）。サーバー経路でも host plan が縮小を選んだ場合、より長い prompt に対する chunk を別途保持し、ログにその上限を出します（`engine/src/program/generate.cpp:12659-12663,12747-12760`）。

明示した `--prefill N` は自動計画を通らず、`STRATA_PREFILL_RING` は ring slot 数の決定で plan budget より優先されます。そのため明示 ring は選択可能な ring の効果を制限しますが、環境変数自体が chunk の再評価を停止する条件ではありません（`engine/src/program/generate.cpp:11425-11426`、`engine/src/prefill/prefill.cpp:843-878`）。

## ログと測定値

早期 return した場合、この変数に関するログは出ません。計画器が実行されると、候補が変わらない場合も `stderr` に `strata: prefill plan: ... kept: ...` の行と `strata: prefill plan inputs: ...` の行を出します。候補を変える場合の行は `strata: prefill plan: chunk ... -> ..., ring ... -> ...: ...` で、続けて同じ inputs 行を出します。変更理由・推定読み込み量は `prefill_plan::describe` が整形します（`engine/src/program/generate.cpp:11504-11512`、`engine/include/strata/program/prefill_plan.hpp:151-173`）。サーバーでは追加で `strata serve: prompt chunk auto: ...` と、plan chunk が別にある場合 `strata serve: prompts longer than ... read in equal chunks of at most ... (the host-aware plan); shorter ones in one chunk` を出します（`engine/src/program/generate.cpp:12747-12760`）。

`STRATA_PREFILL_HOST_PLAN` 自体による専用の警告、終了、失敗経路はありません。条件不足や無効化時は元の chunk を返します（`engine/src/program/generate.cpp:11438-11447`）。測定値は記載しません。`docs/DETAILS.md` と release note には Linux の file tier を対象にした説明・測定が載っていますが、現行の `host_plan_chunk` に Linux 限定の分岐はなく、host memory helper には Windows / Linux / macOS の分岐があります。これらの資料上の測定値を他 OS に一般化できる根拠はありません（`docs/DETAILS.md:346-351`、`docs/release-notes-0.2.0.md:61`、`engine/src/program/generate.cpp:11432-11447`、`engine/src/core/conversation_memory.cpp:411-440`）。

## 根拠

- `engine/src/program/generate.cpp:11432-11467` — getenv 判定、early return 条件、モデル・host 計画入力。
- `engine/src/program/generate.cpp:11468-11518` — 候補作成、採点、stderr 出力、リング状態と chunk の適用。
- `engine/src/program/generate.cpp:12629-12663,12747-12760,23990-24024` — サーバーおよび prompt 処理からの呼び出しと chunk 適用。
- `engine/include/strata/program/prefill_plan.hpp:81-149` — 候補の予測、改善閾値、長い prompt の chunking。
- `engine/include/strata/program/prefill_plan.hpp:151-173` — planner のログ文面。
- `engine/src/prefill/prefill.cpp:833-878` — ring-byte gate と `STRATA_PREFILL_RING` の優先。
- `engine/src/core/conversation_memory.cpp:411-440` — host memory の OS 別取得。
- `engine/src/program/generate.cpp:1891-1905` — drive 速度の既定推定と `STRATA_SSD_GBPS`。
- `docs/DETAILS.md:346-351`、`docs/release-notes-0.2.0.md:61` — 設計資料・測定記述との照合。
