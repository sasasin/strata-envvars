# `STRATA_SLOT_READ_MAX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

上限を変えるのは、サーバー経由のバッチ生成で、保持中の会話の次ターンをその slot の pipelined MTP window で読む最適化が選ばれたときの「次ターンの新規 token 数」です。条件式は `n - rd_from <= slot_read_max` です。上限を超えるとこの最適化の条件を満たさず、後続の通常の prompt/admission 経路に進みます。変数自体は slot read を有効化せず、CLI 値から上書きもされません（`engine/src/program/generate.cpp:17451-17456, 19284-19301, 19404-19415`）。

エンジンは、slot read が実行可能な構成かを起動時に判定して `INFO ... slot_read=0|1` を出します。Python サーバーはこの情報と `STRATA_SLOT_READ` の値を使い、会話を slot で読む BGEN 要求に `slot_read=1` を付けます。`STRATA_SLOT_READ_MAX` はこのサーバー判定には使われず、エンジン側の turn 長判定にだけ使われます（`engine/src/program/generate.cpp:16065-16125`; `terminal/serve/server.py:1950-1952, 2186`）。

## 値と判定

エンジンのバッチ処理設定箇所で `std::getenv` を一度呼び、値が未設定または空文字なら 1024、それ以外は `std::atoll` で変換し、その結果を `std::max<int64_t>(1, ...)` で最低 1 にします。文字列全体の妥当性検査はありません。`atoll` が読む数値接頭辞が使われ、後続の文字は判定されません（`engine/src/program/generate.cpp:17452-17455`）。

| 入力 | 判定結果（上限） |
|---|---:|
| 未設定、空文字 | 1024 |
| `1`、`25` | 1、25 |
| `0`、`-2`、数値に変換できない文字列（例: `true`） | 1（`atoll` の結果 0 以下を最低 1 にする） |
| `12suffix` | 12（数値接頭辞を採用） |
| ` 12`、`+12` | 12（`atoll` の数値変換規則） |

この値は正の上限に変換された後、要求で `n - rd_from` が上限以下のときだけ最適化の条件を通します。上限に対する別の CLI 優先順位、設定ファイル、clamp 上限はありません（同上、`engine/src/program/generate.cpp:19300-19301`）。

## 有効になる条件

- エンジンの batch slot MTP drafter が使え、`--batch` が正、`--batch-groups` が 1 より大きく、layer split があり、pipelined MTP と deferred commit が有効であること。`STRATA_PIPED_MTP` は pipelined MTP の proposal 数を設定します（`engine/src/program/generate.cpp:7804-7814, 16069-16076`）。
- `STRATA_SLOT_READ` が未設定・空文字・`0...` ではないこと。加えて `STRATA_BATCH_DF2` が使われず、各 batch slot に MTP drafter があること。満たさなければ `slot_read_cap` は false です（`engine/src/program/generate.cpp:16069-16076`）。
- サーバーが起動時の `INFO slot_read=1` を受け、`STRATA_SLOT_READ` が文字列 `0` と完全一致しないこと。サーバーは複数の会話が所定の sticky window 内で動いている場合に、held slot と prefix が合う次ターンを slot に割り当て、BGEN に `slot_read=1` を付けます。エンジン側はキー値を `atoi != 0` で判定します（`terminal/serve/server.py:1950-1952, 1963-1971, 2186`; `engine/src/program/generate.cpp:18765-18768, 18821-18822`）。
- リクエストが GENI でなく、画像なし、logprobs なし（`req_logprobs < 0`）、pinned prefix なし（`req_pin == 0`）、割当 slot があり partial slot でないこと（`engine/src/program/generate.cpp:19284-19285`）。
- slot が prompt の最良の source であるか、所定の resume checkpoint を持つ cached slot で、開始位置 `rd_from` が 1 以上、他の parked conversation がより多くの token を保持しておらず、checkpoint stage 数が合うこと。さらに `n - rd_from <= STRATA_SLOT_READ_MAX` が必要です（`engine/src/program/generate.cpp:19289-19301`）。
- `STRATA_SLOT_READ_WIDE` と `STRATA_SLOT_READ_AHEAD` は読み取り幅・先行実行の別 opt-in です。上限値を変えません。両者は未設定・空文字・先頭文字が `0` の場合 off です（`engine/include/strata/program/batch_groups.hpp:41-48`; `engine/src/program/generate.cpp:7831-7847, 17456-17463`）。

## 実行時の詳細

上限値は `generate.cpp` の batch pipeline 設定箇所で即時実行 lambda により読み込まれ、そこから要求処理で参照されるローカル値です。関数内 static cache や要求ごとの再読込はありません（`engine/src/program/generate.cpp:17451-17500`）。

条件を通ると、必要なら slot の checkpoint をその slot の session と drafter に復元し、prompt の続きの token を `sl.rd` に設定します。slot が自分の windows で prompt rows を読み、通常は他 slot と並行して処理します。読み込み設定後に stderr に `strata batch: slot %d reads its conversation's next turn in its own windows: ...`、stdout に `DONE 0 ...` と `BADM %d 1` を出して、次の生成を slot に引き継ぎます（`engine/src/program/generate.cpp:19303-19321, 19329-19351, 19390-19402`）。上限条件を満たさない要求はこの早期分岐を通らず、後続の通常の会話 cache / prompt admission 処理へ進みます（`engine/src/program/generate.cpp:19404-19415`）。

この変数に固有の警告、無効値エラー、終了経路はありません。checkpoint 復元や drafter 状態の失敗など、最適化を実行した後に別のエラー経路があり、標準出力へ `ERR restoring a conversation checkpoint failed` 等を出して return しますが、上限値の不正を示すものではありません（`engine/src/program/generate.cpp:19304-19319`）。

## ログと測定値

slot read の機能が有効なとき、stderr の `strata generate: STRATA_SLOT_READ: ... (turns of up to %lld new tokens, where the server asks: slot_read=1)` に設定後の上限値が表示されます。起動時の stdout INFO 行には機能可否の `slot_read=0|1` が出ます。上限を超えた要求だけを示すログはありません（`engine/src/program/generate.cpp:16098-16125, 17464-17472`）。

ソースコメントには、この方式の測定説明がありますが、変数の一般的な性能効果としては扱いません。実装コメント記載の条件は 2x RTX 3090、178K-token conversations です（`engine/src/program/generate.cpp:17443-17450, 19272-19283`）。

## 根拠

- 候補名の実読み取りと値変換: `engine/src/program/generate.cpp:17451-17456`
- slot read の構成要件と INFO: `engine/src/program/generate.cpp:16065-16125, 17451-17472`
- サーバーの要求判定と BGEN フラグ: `terminal/serve/server.py:1950-1952, 1963-1971, 2186`
- 要求パラメーター解析と slot read の適用条件・処理: `engine/src/program/generate.cpp:18765-18768, 18821-18822, 19271-19415`
- 関連 opt-in switch の規則: `engine/include/strata/program/batch_groups.hpp:41-48`
