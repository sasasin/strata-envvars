# `STRATA_SLOT_READ_AHEAD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

slot が会話の次の turn を読んでいる最中、その slot の直前の read window が layer-split pipeline を通過中でも、別の group が idle なら次の read window をその group の行に載せる opt-in スイッチである。対象は `engine/src/program/generate.cpp` の pipelined MTP / slot-read 経路であり、通常の token decode window を先行実行する設定ではない。先行するのは既知の prompt rows で、各 stage は window の launch 時に行を commit する（`engine/src/program/generate.cpp:17457-17463`, `18046-18069`, `18138-18144`, `18191-18197`）。

## 値と判定

`batch_groups::switch_on` は null、空文字列、先頭文字が `0` の値を OFF、それ以外を ON とする。全体の数値変換や真偽文字列の解釈はしない（`engine/include/strata/program/batch_groups.hpp:41-43`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_SLOT_READ_AHEAD` の判定 | OFF | `1`, `true`, `False`, ` 1`, `2anything` | 空文字、`0`, `0anything`, `00` |

この判定は先頭 1 文字だけを見るため、大文字小文字・後続文字・空白・数値としての妥当性は検査しない。したがって `false` や空白だけの値も先頭文字が `0` でなく空でもないため ON になる。`0anything` は文字列全体が数値でなくても先頭が `0` なので OFF である（`engine/include/strata/program/batch_groups.hpp:43`）。

## 有効になる条件

- この値だけでは slot-read を有効化しない。`STRATA_SLOT_READ` が unset / 空 / `0` 始まりでなく、`STRATA_SLOT_READ_WIDE` も unset / 空 / `0` 始まりでない必要がある。`STRATA_SLOT_READ_WIDE` は `STRATA_SLOT_READ` に依存し、read-ahead は wide-read に依存する（`engine/include/strata/program/batch_groups.hpp:44-48`; `engine/src/program/generate.cpp:7838-7842`, `17456-17463`）。
- engine 側では `--batch` が正、`--batch-groups` が 1 より大きく、layer split の stage があり、`--batch-mtp` と `STRATA_PIPED_MTP` による pipelined MTP および deferred commit が有効で、batch slot 数・行数が verifier の容量内であることが必要である。`STRATA_BATCH_DF2` 経路や slot drafter 数が batch slot 数と合わない場合も slot-read が無効になる（`engine/src/program/generate.cpp:7804-7813`, `16065-16076`, `17425-17456`）。
- 実際の turn read は server request の `slot_read=1` が指定され、会話の既存 slot を選べる場合に限る。標準 server は複数会話の slot 状態と prompt prefix を確認してから BGEN に `slot_read=1` を付ける（`terminal/serve/server.py:1951-1971`, `2185-2188`; `engine/src/program/generate.cpp:18765-18768`, `18821`, `19284-19301`）。画像、logprobs、pinned prefix、partial slot などの request はこの slot-read 条件から除外される（`engine/src/program/generate.cpp:19284-19285`）。
- Ahead window はさらに「読み込み中の slot が自分の group で唯一 active」「その slot に未完の read window が flight 中」「別 group が idle」「次の read window が group の全容量に一致し、draft chain の準備もできている」場合だけ送られる。該当しなければ通常の slot-read の scheduling に戻る（`engine/src/program/generate.cpp:18035-18069`）。

## 実行時の詳細

engine の serve 初期化時に環境値を読み、`slot_read_ahead` の bool に保持する。関数内 static ではないが、この初期化後にプロセス環境を書き換えても既存 engine の値は更新されない。CLI 引数や設定ファイルでこの bool を上書きする経路はない（`engine/src/program/generate.cpp:17425-17463`）。

通常の pipelined read は、slot が自身の prompt rows を含む window を処理し終えてから次の window を開始する。read-ahead が有効で上記条件を満たすと、進行中 window が `forced` として扱われ、次の prompt window を idle group の rows として送る。prompt rows はすべて保持され、stage ごとに launch 後 commit される。これは slot-read の window 処理と GPU stage 間の重なり方を変えるもので、CLI の生成長や sampling 値をこの変数から設定する処理はない（`engine/src/program/generate.cpp:18046-18069`, `18073-18095`, `18138-18144`, `18191-18197`）。

## ログと測定値

slot-read 自体が有効なら stderr に `strata generate: STRATA_SLOT_READ: an idle slot reads the next turn ...` が出る。wide-read が有効な場合はこの行に `(STRATA_SLOT_READ_WIDE)` が追加され、対象変数も有効なら `, a window ahead through a group that stands idle (STRATA_SLOT_READ_AHEAD)` が追加される。この表示は設定 gate を示し、実際に ahead window が発生したことを保証しない（`engine/src/program/generate.cpp:17464-17472`）。

slot read の prompt rows があった batch の timing 行には ` (read in the slots: %lld prompt tokens, %lld turns, %lld windows ahead)` が stderr に付く。最後の値は実際に idle group へ送った ahead window 数である（`engine/src/program/generate.cpp:18092-18095`, `18254-18274`）。launch / commit の失敗時は通常の batch error として stdout に `ERR %s` が出て pipeline 処理が失敗する。read-ahead 専用の警告文や fallback 理由ログは見当たらない（`engine/src/program/generate.cpp:18185-18197`）。この変数に結びつく測定値は、調査したソースコードと `docs/DETAILS.md` に見当たらなかった。

## 根拠

- 値の判定と依存 helper: `engine/include/strata/program/batch_groups.hpp:41-48`
- master slot-read 条件、engine の batch / MTP 条件、INFO 表示: `engine/src/program/generate.cpp:16065-16076`, `16122-16125`, `17425-17472`
- read-ahead の scheduling と window commit: `engine/src/program/generate.cpp:18035-18095`, `18138-18144`, `18185-18197`
- server request の slot-read 選択と制約: `terminal/serve/server.py:1951-1971`, `2185-2188`; `engine/src/program/generate.cpp:18765-18821`, `19272-19301`
- ahead window の実行数ログ: `engine/src/program/generate.cpp:18254-18274`
