# `STRATA_BATCH_MTP_SERIAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--batch-mtp` が有効で、layer split の batch slot を自動で複数 group に分ける条件では、この変数を有効にすると group 数を 1 にし、各 GPU stage を順に通る serial window で slot ごとの MTP proposal を検証する。MTP 自体を有効化する変数ではなく、通常の batch drafting の有無も変えない。実際の MTP 有効化は `--batch-mtp` または `STRATA_BATCH_MTP` などで決まり、その後にこの変数を使って group を解決する（`engine/src/program/generate.cpp:7803-7820, 7841-7865`; `engine/include/strata/program/batch_groups.hpp:122-145`）。

効くのは `--batch-groups` を指定せず、layer split があり、slot 数が 2 以上で、自動算出した group 数が 1 より大きく、かつ `--batch-mtp` が有効な場合に限る。自動 group 数を 1 にすると MTP は serial batch window で動く。変数を有効にしない場合は、通常は自動 pipeline が選ばれ、`STRATA_PIPED_MTP` が無効なら `--batch-mtp` は無効化される（`engine/include/strata/program/batch_groups.hpp:126-145`; `engine/src/program/generate.cpp:7857-7865`）。

Terminal 側の `batch_mtp_dropped` も環境を読み、drafting 状態の説明を組み立てる。ただし、これは engine の group 設定を行わず、起動前の判定結果を返す補助処理である（`terminal/strata_control/drafting.py:940-961, 1739-1743`; `terminal/strata_cli/drafting_cmd.py:131-136`; `terminal/strata_cli/launch/runner.py:2087-2092`）。

## 値と判定

Engine は `std::getenv` で値を読み、未設定でなく、空文字でなく、先頭文字が `0` でない場合を true とする。文字列全体の parse・trim・大文字小文字変換はしない。従って `1`, `true`, `yes`, ` 0` は有効、`0`, `00`, `0anything`, 空文字、未設定は無効（先頭が `0` なら後続文字にかかわらず無効）。末尾の文字は判定に影響しない場合がある（`engine/src/program/generate.cpp:7812`; `engine/include/strata/program/batch_groups.hpp:132`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Engine の `batch_groups_for` | false | `1`, `true`, `yes`, ` 0` | 空文字, `0`, `00`, `0anything` |
| Terminal の `batch_mtp_dropped` 表示判定 | `os.environ.get(..., "0")` が `"0"` | `1`, `true`, ` 0`, `00`, `0anything` | 空文字, `0` |

Terminal は値全体を `""` または `"0"` と比較するため、`0anything` などでは Engine と判定が異なる（`terminal/strata_control/drafting.py:959-960`）。

## 有効になる条件

- `--batch-groups` を省略すること。明示した `--batch-groups auto` も「指定あり」なので pipeline を要求し、この変数は serial に戻さない。明示した `--batch-groups 1` はこの変数とは独立して serial になる（`engine/src/program/generate.cpp:4044-4049`; `engine/include/strata/program/batch_groups.hpp:126-143`）。
- layer split であること（`later_stages > 0`）、batch slot が 2 以上であること、自動算出 group 数が 2 以上であること。自動 group 数は GPU stage 数を上限に、slot 数を割り切る最大の group 数（少なくとも 1）である（`engine/include/strata/program/batch_groups.hpp:113-120, 126-135`）。slot 調整後にも group 解決をやり直す（`engine/src/program/generate.cpp:8110-8112`）。
- `--batch-mtp` が実際に有効であること。この指定単独では有効化されない。engine は `--batch-mtp` または `STRATA_BATCH_MTP` 等から有効化を決め、その成立後に group 解決へ渡す（`engine/src/program/generate.cpp:7841-7848, 7803-7812`）。
- MTP 有効化には少なくとも `--batch >= 2`、`--mtp`（または slot DFlash2）、`--spec T`（`T >= 2`）、`--serve` が必要で、layer split の各 stage が別 GPU にある必要がある。Metal build では batch window が draft row を扱えないため、他の条件を満たしても slot drafts は無効化される（`engine/src/program/generate.cpp:7843-7855`）。helper expert cache を使う layer split でも無効化される（`engine/src/program/generate.cpp:7866-7872`）。
- `STRATA_PIPED_MTP` は pipelined group 内の drafts を許可する別スイッチ。明示された group 数が複数でも有効なら pipeline 上で MTP drafts を行う経路があり、この変数の用途（自動 group を serial にする）とは異なる（`engine/src/program/generate.cpp:7819-7820, 7857-7865`; `engine/include/strata/program/batch_groups.hpp:139-145`）。
- `--adapt-async 1` も未指定 group の自動値を 1 にするが、この場合は `--batch-mtp` の有無にかかわらない。`STRATA_BATCH_MTP_SERIAL` の分岐が優先される条件では MTP 用の serial 理由になる（`engine/include/strata/program/batch_groups.hpp:131-135`）。

## 実行時の詳細

Engine は `batch_groups_for` lambda の呼び出しごとに `getenv` し、値を static cache しない。初期 group 解決に加え、実際に確保できた slot 数が確定した後にも解決するため、設定は起動処理中に評価される（`engine/src/program/generate.cpp:7803-7820, 7975-7994, 8110-8112`）。通常のプロセス環境は起動時に定まるため、その環境で起動した Engine に対する実用上の設定時点はプロセス起動前である。Terminal の補助判定は `batch_mtp_dropped` が呼ばれるたび `os.environ` を読む（`terminal/strata_control/drafting.py:940-960`）。

group 数が 1 になった場合、slot window は GPU stage を順番に通る serial path となり、batch MTP slot drafter は slot ごとに最大 1 proposal を設定される。slot drafter は solo drafter の重みを共有し、個別 K/V state と buffer を持つ（`engine/src/program/generate.cpp:8368-8378, 17529-17542`）。この変数は proposal の採否規則や token の選択を直接変更する処理ではなく、group 解決とそれに続く serial/pipelined 実行経路を選ぶ。

## ログと測定値

自動 group が本来 2 以上で、この変数により MTP serial へ切り替わる場合、stderr に `strata generate: --batch-groups auto: 1 group of ... - --batch-mtp does not run in pipelined groups; --batch-groups ... would pipeline them and turn it off` の形式で理由を出す（`engine/src/program/generate.cpp:7982-7989`）。有効化条件を満たさない `--batch-mtp` は別の理由つき `WARNING` で off になる。MTP drafter が割り当てられれば `strata generate: --batch-mtp: ... slot drafters on CUDA...` を出す（`engine/src/program/generate.cpp:7843-7872, 8373-8378`）。この変数単独の速度向上を示す現行測定値は記載しない。`docs/BATCHING.md:44-54, 97` には serial と pipeline の選択理由および別条件の測定説明があるが、特定の hardware・モデル・負荷に結びついた値であり一般化できない。

## 根拠

- 候補名の実装参照: `engine/src/program/generate.cpp:7812`; `terminal/strata_control/drafting.py:959`。
- Engine の読み取り・group 解決への入力: `engine/src/program/generate.cpp:7803-7820`。
- 値が group 数を変える条件・優先順位: `engine/include/strata/program/batch_groups.hpp:122-145`。
- MTP 条件と fallback warning: `engine/src/program/generate.cpp:7841-7872`。
- 起動ログ、slot drafter、実行経路: `engine/src/program/generate.cpp:7975-7994, 8368-8378, 17529-17547`。
- Terminal 側の判定と利用箇所: `terminal/strata_control/drafting.py:940-961, 1739-1743`; `terminal/strata_cli/drafting_cmd.py:131-136`; `terminal/strata_cli/launch/runner.py:2087-2092`。
- 関連資料: `docs/BATCHING.md:44-54, 96-97`。
