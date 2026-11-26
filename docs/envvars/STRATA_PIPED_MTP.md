# `STRATA_PIPED_MTP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

レイヤー分割したサーバーのバッチ処理で、通常は draft を行わないパイプライン slot group にも `--batch-mtp` の MTP 提案生成を有効にする。変数は opt-in で、単独ではバッチ MTP を有効にしない。バッチ MTP が成立したとき、group ごとにその slot の token と MTP 提案を含めた window を各段で処理し、最終段の判定後に保存しておいた行を各段で commit する。提案数はこの変数の数値部分と `--spec`、Verifier の狭い window 上限で決まる（`engine/src/program/generate.cpp:7819-7820, 7841-7848, 7875-7885, 17529-17542`; `engine/include/strata/program/batch_groups.hpp:122-145`; `engine/include/strata/core/verify.hpp:280-287`).

候補一覧の `docs/SETTINGS.md` は値を「on / off」と記すが、実装は真偽文字列を比較せず、先頭文字で有効性を決めた後に `atoi` で提案数を読む。したがって `true` は有効で提案数 1、`false` も先頭が `f` なので有効で提案数 1 になる。`STRATA_PIPED_MTP=0` はオフ、`=2` は最大 2 提案である（`docs/SETTINGS.md:239`; `engine/src/program/generate.cpp:7819, 7882-7885`）。

## 値と判定

エンジンは `batch_groups_for()` が呼ばれる初期化中に `getenv` し、値が存在し、空でなく、先頭文字が `0` でなければ `mtp_piped` とする。設定値全体の比較や空白除去はない。パイプ化が成立した後、同じ値を `atoi` に渡し、結果を `[1, max(1, min(--spec - 1, kVerifyNarrowT - 1))]` に clamp する。非数値は `atoi` が 0 を返すため 1 になり、符号付き負数も 1 になる。数値の後ろにある文字は `atoi` が解釈しない。未設定・空文字・先頭が `0` の値は機能オフであり、このとき提案数の parse は行わない（`engine/src/program/generate.cpp:7803-7820, 7881-7885`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| エンジンの group 判定 | オフ | `1`, `2`, `true`, `false`, ` 2`, `abc`, `-2`（先頭が `0` 以外） | 空文字、`0`, `00`, `0anything` |
| 提案数（有効な group 判定かつパイプ MTP 条件成立時） | ― | `2` → 2（上限以内の場合）、`2tail` → 2 | `abc`, `false`, `-2`, `0` → 1 に clamp。ただし `0` は先頭判定で機能オフとなり、parse されない |
| Python の設定説明判定 | `batch_mtp_dropped` 内では未設定時 `""` 扱い | 空でも `"0"` でもない文字列を「piped MTP あり」と判定 | `""` と文字列全体が厳密に `"0"` の場合 |

Python の `terminal/strata_control/drafting.py:940-961` にも参照があるが、これは `batch_mtp_dropped()` が設定時の draft 選択理由を説明するための分類であり、engine の値 parse や動作制御ではない。Python は `"00"` や `"0anything"` を有効扱いする一方、engine は先頭 `0` で無効にするため、異なる値では説明判定が engine と一致しない。呼び出し箇所は `terminal/strata_control/drafting.py:1737-1743`。

## 有効になる条件

- Engine が `--serve` で起動し、`--batch` が 2 以上であること。`--batch-mtp`、または `STRATA_BATCH_MTP`（空でなく先頭が `0` 以外）が必要。MTP draft layer を使う場合は `--mtp` が必要で、`--spec` は 2 以上。これらを満たさないと `--batch-mtp` が off になり、この変数だけでは slot draft は動かない（`engine/src/program/generate.cpp:7841-7848, 7878`）。
- レイヤー分割を行い、各段が別 GPU であること。Metal build は batch MTP を無効にする。engine の共通 group 解決は `STRATA_USE_HIP` で NVIDIA 専用の二枚 GPU default 判定を分けるが、`STRATA_PIPED_MTP` の判定自体は共通コードにある（`engine/src/program/generate.cpp:7803-7820, 7849-7859`）。
- 解決後の `--batch-groups` が 2 以上であること。未指定なら layer split で slot を割り切れる最大 group 数（GPU 段数以下）が default になる。明示した数または `auto` も使えるが、1 group なら serial path なのでこの機能は使わない。未指定の場合 `STRATA_BATCH_MTP_SERIAL` または `--adapt-async 1` が serial group を選ぶことがある。明示 `--batch-groups` の場合は指定が優先される（`engine/include/strata/program/batch_groups.hpp:113-145`; `engine/src/program/generate.cpp:7803-7820, 7971-7999`）。
- slot 数が最終確定した後も group 数が 2 以上であること。`STRATA_BATCH_SELF_COMMIT` が設定され空でなく先頭文字が `0` 以外なら併用不可。また group あたりの行数 `slots/group × (1 + proposal数)` が `kVerifyNarrowT` を超えると無効になる（通常の狭い verifier window は 8 行）。無効時は piped MTP のみ off となり、成立可能な `--batch-mtp` は通常の扱いに戻る（`engine/src/program/generate.cpp:8120-8146, 17537-17547`）。
- layer split の helper expert cache がある場合、batch MTP は現状 off になる（`engine/src/program/generate.cpp:7866-7872`）。

## 実行時の詳細

環境変数はリクエストごとには読まれない。初期化中の `batch_groups_for()` 呼び出しで group の選択に参照され、slots/groups が最終決定した後に piped MTP 可否と提案数が確定する。その後はローカル状態 `piped_mtp`、`pm_drafts` として window 処理に使われる。実行中に環境変数を変更しても、確定済みの engine 設定は変わらない（`engine/src/program/generate.cpp:7803-7820, 7878-7885, 8120-8146`）。

各 slot は token に加え、最大 `pm_drafts` 個の draft proposal を持つ。最初の提案は常に使い、後続の提案は直前の draft の確率が `--spec-min-p` 以上の場合に追加する。Verifier の最終段が受理行を決めるまで、各段の次 window が scratch を再利用できるよう保存し、判定後に各段で受理行を commit する。draft chain は非同期に進み、必要な slot 状態を次に読む前に pipeline と commit を drain する（`engine/src/program/generate.cpp:7879-7885, 17534-17542, 17635-17657, 17985-17999`; `engine/include/strata/core/verify.hpp:280-287`; `engine/src/core/verify.cpp:4823-4855`）。

CLI や別環境変数との関係では、`--batch-mtp` / `STRATA_BATCH_MTP` が slot draft の土台であり、`--batch-groups` が serial/pipeline を決める。`STRATA_BATCH_MTP_SERIAL` は group 未指定時に serial を選び得る。`STRATA_BATCH_SELF_COMMIT` は piped MTP を止める。`STRATA_PIPED_LOOKUP` は `--suffix-draft` と併用時に proposal 元を prompt lookup に切り替える追加設定で、piped MTP 自体の有効条件ではない（`engine/src/program/generate.cpp:7812, 7841-7842, 7886-7895, 8125-8137`）。

## ログと測定値

起動時、piped MTP が無効になると理由を含む `strata generate: WARNING: STRATA_PIPED_MTP is off: ...`、有効なら group 数・slots/group・最大 proposal 数を含む `strata generate: STRATA_PIPED_MTP: ...` を stderr に出す（`engine/src/program/generate.cpp:8138-8145`）。Verifier の deferred commit 初期化が成功すると `strata verify: pipelined batch windows commit after the verdict ...` を stderr に出す。確保・初期化に失敗すると `strata serve: STRATA_PIPED_MTP, stage ...` を出して engine start が失敗する（`engine/src/core/verify.cpp:4836-4855`; `engine/src/program/generate.cpp:13663-13679`）。proposal chain や commit の実行時失敗は stdout の `ERR batch MTP slot ...` または `ERR a pipelined commit failed on stage ...` として処理される（`engine/src/program/generate.cpp:17635-17642, 17987-17999`）。

`docs/BATCHING.md` は 2x RTX A6000 48 GB、Qwen3.8-Flash-Next IQ3_S、全 expert が VRAM 常駐、`--batch 4 --batch-groups auto`（2 group × 2 slots）、256 tokens/request、reasoning off の測定で、2 streams の total output tok/s を no-draft 125.7、`=1` 146.3（+16.0%）、`=2` 145.1（+15.4%）、4 streams を 171.4、188.8（+10.2%）、179.5（+4.7%）と報告する。これは文書記載の測定結果であり、別条件への一般化はできない（`docs/BATCHING.md:518-533`）。同文書は、1 stream は全設定で solo path となり変化しなかったと報告する。また release note は、2x RTX A6000 の測定で各 slot の token 列が単独実行と一致したと記録する（`docs/BATCHING.md:531-533`; `docs/release-notes-0.2.7.md:41`）。

## 根拠

- 読み取り・値判定・clamp: `engine/src/program/generate.cpp:7803-7820, 7881-7885`
- batch MTP の前提と Metal 制限: `engine/src/program/generate.cpp:7841-7878`
- group 解決と piped MTP 判定: `engine/include/strata/program/batch_groups.hpp:113-145`
- 最終条件・警告と有効ログ: `engine/src/program/generate.cpp:8120-8146`
- Python の説明用参照: `terminal/strata_control/drafting.py:940-961, 1737-1743`
- proposal chain と deferred commit: `engine/src/program/generate.cpp:17529-17547, 17635-17657, 17985-17999`; `engine/include/strata/core/verify.hpp:280-287`; `engine/src/core/verify.cpp:4823-4855`
