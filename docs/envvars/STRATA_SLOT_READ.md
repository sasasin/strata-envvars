# `STRATA_SLOT_READ`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

この変数は、対応する pipelined MTP バッチ実行で、サーバーが保持している会話の次ターンを、その会話のスロット内で読む機能を有効にする opt-in スイッチです。通常の admission は会話の K/V を main sessions へ移して prompt path で読みますが、この経路ではスロットの状態から次ターンを読み、他スロットを止めずにスロット自身の window で処理します。適用条件を満たさない要求は通常の経路に進みます（`engine/src/program/generate.cpp:16065-16075,19272-19283,19300-19304`）。

この変数だけでは機能は動きません。エンジンが起動時に `INFO ... slot_read=1` を出せる構成であり、サーバーが次ターンと認識した BGEN 要求に `slot_read=1` を付け、さらにエンジン側の会話・要求条件を満たす必要があります（`engine/src/program/generate.cpp:16069-16075,16122-16125`; `terminal/serve/server.py:1950-1952,1963-1971,2185-2188`）。

## 値と判定

C++ の主スイッチ判定は環境変数全体を parse せず、`getenv` が返す文字列の先頭だけを見ます。未設定、空文字、先頭が `0` の値は無効です。先頭が `0` 以外なら有効で、文字列 `1` に限定されません。したがって `1`、`true`、`false`、先頭空白の ` 0` は C++ では有効、`0`、`0anything`、`00` は無効です。大文字小文字や後続文字、数値としての妥当性は検査しません（`engine/include/strata/program/batch_groups.hpp:41-48`; `engine/src/program/generate.cpp:16069-16072`）。

| 読み取り箇所 | 未設定 | 設定値の判定 | 用途 |
|---|---|---|---|
| Engine の capability 判定 | 無効 | 空でなく、先頭文字が `0` 以外なら有効 | 起動時の `slot_read_cap` と INFO 表示 |
| `STRATA_SLOT_READ_WIDE` との組み合わせ | 無効 | 対象変数と `WIDE` の両方が上記判定で有効 | 単独稼働スロットの window 拡張 |
| Serve の判定 | INFO capability が false なら無効 | INFO が true で、サーバープロセスの値が文字列ちょうど `0` でなければ有効 | BGEN に `slot_read=1` を付けるか |

最後の行は C++ と値の判定が異なります。サーバー側では未設定・空文字・`00`・`false` も `!= "0"` を満たしますが、engine の起動時 capability が false なら有効化できません。engine の capability が true のときは、サーバー側で値をちょうど `0` にすると要求ごとの指定を止められます（`terminal/serve/server.py:1950-1952,2185-2188`）。

## 有効になる条件

- Engine の `slot_read_cap` は、`--batch` 相当の `o.batch > 0`、複数の batch groups、layer-split stages が存在すること、`STRATA_PIPED_MTP` による pipelined MTP、deferred commit が有効であることを要求します。さらに `--batch-mtp` / `STRATA_BATCH_DF2` の DFlash2 構成ではなく、各 batch slot に slot MTP drafter があり、slot の window が `batch_max_t()` に収まる必要があります。条件不足なら capability は false です（`engine/src/program/generate.cpp:16069-16075`）。
- この capability は起動時に INFO の `slot_read=0|1` として出ます。`--batch` がない場合、該当 INFO 行には batch 関連の値自体が付きません（`engine/src/program/generate.cpp:16122-16125`）。
- サーバーは、engine INFO が capability を示し、`STRATA_SLOT_READ` が文字列ちょうど `0` でない場合だけ、通常の BGEN に `slot_read=1` を追加します。embedding 入力の BGENI には付けません（`terminal/serve/server.py:1950-1952,2185-2188`）。
- サーバーがその要求をスロット内で読む候補にするには、複数会話が `STRATA_PARALLEL_STICKY_S` の期間内に動いていること、空きスロットが会話の prompt prefix を少なくとも 512 token 保持していることが必要です。`STRATA_PARALLEL_STICKY_S` は既定 20 秒で、0 以下なら複数会話状態になりません（`terminal/serve/server.py:1941-1948,1954-1971,2426`）。
- Engine 側では、要求の `slot_read=1` に加えて、非 GENI、画像なし、logprobs 無効、pin 指定なし、slot の状態が partial でないことが必要です。対象 slot 自身が最適な会話 source であるか、main sessions に保持され slot に貸し出された checkpoint が対象 slot 用にあること、parked conversation の prefix が slot の保持位置を超えていないこと、stage checkpoint 数が一致することも要求します（`engine/src/program/generate.cpp:19284-19301`）。
- 読み直す新規 token 数は `STRATA_SLOT_READ_MAX` 以下である必要があります。同変数が未設定または空なら 1024、設定時は `atoll` 変換後の値を最低 1 に clamp します。長い turn など条件に合わない要求は通常の admission 経路に進みます（`engine/src/program/generate.cpp:17452-17455,19300-19301,19405-19415`）。
- `STRATA_SLOT_READ_WIDE` は対象変数とともに有効な場合、slot が group 内で唯一稼働しているときの window を広げます。`STRATA_SLOT_READ_AHEAD` はさらに両方を前提として、別 group が idle のとき次 window を先行させます。どちらも主機能の必須条件ではありません（`engine/include/strata/program/batch_groups.hpp:43-48`; `engine/src/program/generate.cpp:7831-7847,17456-17463`）。
- 対象変数を切り替える CLI 引数はありません。`--batch`、`--batch-groups` 等の起動引数は上記の適用条件を左右しますが、環境変数による opt-in を置き換えません（`engine/src/program/generate.cpp:16069-16075`）。

## 実行時の詳細

Serve は起動時に engine の INFO 行を読み、`slot_read` capability を `self.info` に保存します。エンジンの起動時に `STRATA_SLOT_READ` を読むため、engine 側の capability はプロセス起動後の変更では更新されません。一方で Serve の `slot_read` property は `os.environ` をその都度参照するので、サーバープロセス内で値をちょうど `0` にすれば要求指定を停止でき、別値に戻せば起動時 capability が true の場合に再び許可されます。起動時 capability が false だった engine を、サーバー側の変更だけで有効にすることはできません（`engine/src/program/generate.cpp:16069-16075,16122-16125`; `terminal/serve/server.py:1229,1950-1952`）。

`STRATA_SLOT_READ_WIDE` と `STRATA_SLOT_READ_AHEAD` は engine の batch/window 構成時にローカル値として判定され、その構成中に再読しません。対象変数の C++ 判定箇所には OS ごとの分岐はありません。実際に利用可能かは、上記の engine batch・pipeline 条件で決まります（`engine/src/program/generate.cpp:7838-7847,17451-17463`）。

Engine の起動環境はサーバーが組み立てた env として子プロセスへ渡されます（`terminal/serve/server.py:827-829`）。CLI の直接要求は `req_slot_read` の既定値が false で、サーバーの BGEN プロトコルが `slot_read=1` を渡した場合にのみ候補になります（`engine/src/program/generate.cpp:18765-18768,18821`）。

実際に slot read を選ぶと、必要なら slot checkpoint を復元し、slot の MTP drafter を idle にして prompt 長を設定します。スロットの状態を prompt の先頭位置に戻して新しい token を window ごとに読む準備をし、会話境界 checkpoint を取ります。通常経路で行う会話全体の K/V 移送を避け、他 slot の処理と並べて読みます。ここでの失敗経路として、checkpoint 復元失敗は標準出力に `ERR restoring a conversation checkpoint failed` を出して `return 1`、slot drafter が idle にならない場合は `ERR <理由>` を出して `return 1` します（`engine/src/program/generate.cpp:19304-19327,19336-19372`）。

## ログと測定値

有効時、engine は stderr に `strata generate: STRATA_SLOT_READ: an idle slot reads the next turn of the conversation it holds in its own windows, ...` と出し、window token 数と上限を表示します。`WIDE` / `AHEAD` が実際に成立する場合はその旨も同じ行に追記します。無効時にはこの有効ログは出ません（`engine/src/program/generate.cpp:17464-17472`）。起動時 capability は stdout の INFO 行に `slot_read=0` または `slot_read=1` として現れます（`engine/src/program/generate.cpp:16122-16125`）。

個々の turn が slot read 経路に選ばれると stderr に `strata batch: slot %d reads its conversation's next turn in its own windows: ...` が出て、token 数、保持済み token 数、checkpoint の有無、setup 時間を示します。admission は `DONE 0 ...` と `BADM %d 1` で返し、その後の BDONE は `read=<ms>` を含みます。通常経路へ fallback した要求には、この slot-read の setup ログは出ません（`engine/src/program/generate.cpp:19390-19402`; `terminal/serve/server.py:1622-1635`）。

`docs/DETAILS.md` にこの変数の記載は見つかりませんでした。測定値は記載していません。

## 根拠

上記各節の記述箇所に Strata ソースの相対パスと行番号を併記しました。
