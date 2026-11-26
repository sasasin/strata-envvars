# `STRATA_SLOT_CKPT_KV_DIRECT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

バッチ slot に保存された turn checkpoint から会話を再開するとき、checkpoint の実行状態に加えて K/V を slot の state pool から main session へ直接コピーする経路を選ぶ。対象は `engine/src/program/generate.cpp` の `copy_from_slot` で、既定の host image 経由を使う経路から切り替わる。これはコピー経路の選択であり、値だけでは有効にならず、`STRATA_SLOT_COPY_DIRECT` も有効でなければならない（`engine/src/program/generate.cpp:16868-16872, 16967-16993`）。

## 値と判定

`copy_from_slot` 内の関数ローカル `static const bool` が、最初にその経路へ到達したとき `std::getenv` で読み取る。未設定 (`nullptr`) と空文字は無効。設定されている場合は先頭文字だけを見て、`'0'` 以外なら有効とする。文字列全体の parse、数値変換、大文字小文字変換、空白除去はない（`engine/src/program/generate.cpp:16973-16976`）。

| 実行経路 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| Metal 以外の slot checkpoint restore | 無効 | `1`, `true`, ` 0`, `00x` | 空文字, `0`, `0anything` |
| Metal の slot restore | この変数を読まない | 該当なし | 該当なし |

Metal の場合は `copy_from_slot` がこの環境変数を読む箇所より前に `window_slot_copy_main` を呼んで戻る（`engine/src/program/generate.cpp:16958-16976`）。

## 有効になる条件

- サーバーのバッチ slot から prompt-cache state を再利用し、その slot の turn checkpoint (`at != nullptr`) を使う必要がある。slot source の候補選択は `--prompt-cache` が有効で、画像入力がなく、control vector が一致する経路に限られる。idle slot は cached であること、active slot は未 tainted で `STRATA_SLOT_CKPT_MOVE` が有効であることなどの条件もある（`engine/src/program/generate.cpp:19310-19341`）。
- `STRATA_SLOT_COPY_DIRECT` も有効であること。これは同じく未設定・空文字・先頭が `0` の値を無効、それ以外の設定値を有効とする（`engine/src/program/generate.cpp:16868-16872`）。どちらかが無効なら checkpoint の実行状態と K/V は従来の save/restore image 経由でコピーされる（`engine/src/program/generate.cpp:16977-17017`）。
- slot の最後の状態 (`at == nullptr`) を戻す場合、この変数は経路選択に関与しない。`STRATA_SLOT_COPY_DIRECT` が有効なら `direct_slot_copy`、そうでなければ image 経由になる（`engine/src/program/generate.cpp:16977-16993`）。
- Metal では専用の `window_slot_copy_main` 経路を通るため、この変数の判定は使われない（`engine/src/program/generate.cpp:16963-16965`）。
- CLI 引数や別設定がこの値を上書きする処理はない。`STRATA_SLOT_COPY_DIRECT` は追加の必須条件である。

## 実行時の詳細

有効な checkpoint restore では、各 stage について slot session の checkpoint state を main session に復元し、続けて各 QSA state の K/V を checkpoint の token 数 (`upto`) まで `conversation_kv_copy` でコピーする。コピー元は slot の pool、コピー先は main session の pool。core 側では両者の layout を検証し、K/V の data・scale・pooled buffer と residency state をコピーまたは更新する（`engine/src/program/generate.cpp:16979-16992`; `engine/src/core/conversation_snapshot.cpp:625-661`）。checkpoint の state 復元は `conversation_checkpoint_restore` が行う（`engine/src/core/conversation_state.cpp:417-465`）。

環境変数の値は関数ローカル `static` に保存され、最初に `copy_from_slot` が非-Metal の該当箇所へ到達した後はプロセス内で再評価されない。実行中に環境を書き換えても反映されない。子プロセスへの転送・上書き処理はこの読み取り箇所にはない（`engine/src/program/generate.cpp:16973-16976`）。

同期、checkpoint 復元、K/V copy のいずれかが失敗すると `copy_from_slot` は失敗を返す。呼び出し側は `strata batch: restoring slot %d failed (%s); reading the prompt` を stderr に出し、状態をクリアして prompt を先頭から読み直す（`engine/src/program/generate.cpp:19863-19875`）。成功時は後続で `strata batch: slot %d gave back %lld tokens of this conversation (%s) in %.1f ms` を stderr に出し、checkpoint から戻した場合は `its turn checkpoint` と表示する（`engine/src/program/generate.cpp:19932-19949`）。対象変数の有効・無効を直接示すログはない。

## 根拠

- `engine/src/program/generate.cpp:16957-16993` — slot restore、Metal 分岐、環境変数判定、直接コピーと image 経路。
- `engine/src/program/generate.cpp:19310-19341` — slot と turn checkpoint の候補条件。
- `engine/src/program/generate.cpp:19863-19875, 19932-19949` — 失敗時の prompt 再読込と成功時のログ。
- `engine/src/core/conversation_state.cpp:417-465` — checkpoint state の復元。
- `engine/src/core/conversation_snapshot.cpp:625-661` — K/V と residency の直接 copy。
- `docs/BATCHING.md:115-123` — batching のコピー系 opt-in switch の説明。対象変数固有の条件は上記実装に基づく。
