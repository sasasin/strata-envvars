# `STRATA_SLOT_COPY_BATCHSYNC`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの内部動作は対象外。

## 役割

バッチ slot への会話状態の直接コピーで、個々の GPU コピー完了をその都度待たず、各デバイスでコピーをキューに積んでからデバイス単位で同期します。通常の経路では、コピーごとに private stream を同期します。この変数はコピーする状態やコピー先を変えるのではなく、待機のまとめ方を変えます。

この設定単独では効果がありません。`STRATA_SLOT_COPY_DIRECT` が有効で、`--batch` の admission、またはチェックポイント指定なしで slot の会話を再開する直接コピー経路に入った場合に参照されます。Strata の `docs/BATCHING.md` も `STRATA_SLOT_COPY_DIRECT` と併用する opt-in と説明しています。

## 値と判定

実装は文字列全体や数値を parse せず、値の先頭文字だけを検査します。

| 設定値 | 判定 |
|---|---|
| unset | OFF |
| 空文字 | ON（環境変数は設定済みで、先頭文字 `\0` は `0` ではない） |
| 先頭文字が `0`（例: `0`, `0abc`） | OFF |
| それ以外（例: `1`, `true`, `false`, `2`, 空白で始まる値） | ON |

大文字小文字、後続文字、数値としての妥当性は判定しません。関数内の `static const bool` に結果を保存し、最初に直接 slot コピーがこの判定を呼んだ後は再読込しません。プロセス実行中に環境変数を変更しても反映されません。

## 有効になる条件

- `--batch` による slot を使う serve 経路であること。主な適用箇所は新規リクエストの状態を slot に入れる admission です。
- `STRATA_SLOT_COPY_DIRECT` が有効であること。この別変数は未設定・空文字・先頭文字 `0` で無効、それ以外の設定値で有効になります。無効なら従来の host image を介した保存・復元経路を通り、この文書の変数は呼ばれません。
- slot からの再開では、保存済みチェックポイントを指定した場合は通常の checkpoint/K/V restore を使うため、直接コピー経路と本変数は適用されません。チェックポイントなしの再開は直接コピーの対象です。

`src/program/generate.cpp` の該当箇所には、この変数独自の OS、GPU 世代、CLI 上書き、警告ログを分ける条件はありません。実際に利用できる backend はこの CUDA runtime API を使うコピー実装を含むビルドに依存し、この分岐自体には backend guard がありません。

## 実行時の詳細

直接コピー関数は、対象デバイスを順に選び、コピー開始前に各デバイスを同期します。`STRATA_SLOT_COPY_BATCHSYNC` が ON の場合、実行状態（checkpoint）と各 QSA 層の K/V を private non-blocking stream に `cudaMemcpyAsync` でキューイングします。ストリーミング K/V 状態では、コピーの後に residency refresh を並べるため、private stream 上の event を legacy stream に待たせます。コピー完了後、関数末尾の device 同期で各デバイスの処理完了を待ってから成功を返します。OFF の場合は各コピー呼び出し内で private stream を同期し、その後に同じ device 単位の末尾同期も行います。

コピーまたは event の順序付けに失敗した場合は、途中まで積まれた処理を再度 device 同期して drain してから失敗を返します。開始前・末尾の device 同期が失敗した場合も直接コピーは失敗しますが、この drain 用の再同期はコピー途中の失敗時だけです。admission では stderr に `strata serve: batch admission failed: ...` を出し、その slot を cache として扱わず、batch 継続を取りやめます。slot からの再開時は stderr に `strata batch: restoring slot %d failed (%s); reading the prompt` を出し、会話の prompt を最初から読み直します。BYIELD の slot 保存で失敗した場合は `strata batch: BYIELD ... not taken ...` の行に理由を付けます。成功時に本変数専用のログはありません。

Strata の `docs/BATCHING.md` は有効時に「約116コピー」を各デバイス1回同期にまとめると記述しています。この数は同資料の説明であり、コードが固定回数を保証するものではありません。コピー数は session の状態や QSA 層数などに依存します。

## 根拠

- `src/program/generate.cpp:225-235`: 値判定、既定 OFF、初回判定結果の static cache。
- `src/program/generate.cpp:10741-10779`: `STRATA_SLOT_COPY_DIRECT` との関係、デバイスごとの前後同期、queued 引数を checkpoint/K/V コピーへ渡す箇所。
- `src/program/generate.cpp:10781-10805,10822-10830`: admission と slot 再開で直接コピーへ入る条件。
- `src/core/conversation_copy.hpp:17-21,38-49,100-118`: private stream 上の async copy、queued=false の stream 同期、legacy stream との event 順序付け。
- `src/core/conversation_state.cpp:218-246`: checkpoint コピーの各コピーに queued を伝える処理。
- `src/core/conversation_snapshot.cpp:223-252`: K/V コピー、queued 時の stream 順序付けと residency refresh。
- `src/program/generate.cpp:12822-12853,12105-12118,14630-14637`: BYIELD・slot 再開・admission の失敗時ログと fallback。
- `docs/BATCHING.md:110-118`: 各 switch が opt-in であること、および `STRATA_SLOT_COPY_DIRECT` との併用説明。
