# `STRATA_CKPT_REREAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバーが保存済み会話 checkpoint から再開するとき、checkpoint の状態を復元する代わりに、checkpoint までの prompt token を位置 0 からもう一度読む診断用スイッチです。CUDA/HIP 系と SYCL 系の `generate.cpp` に実装されています。checkpoint がない新規 prompt や live session の継続自体を常に再読する設定ではありません。再読区間では checkpoint を復元せず、K/V の状態を作り直します（`engine/src/program/generate.cpp:20086-20120, 20187-20214`; `engine/sycl/src/program/generate.cpp:11065-11096, 11119-11126`）。

## 値と判定

両 backend の生成処理と会話 snapshot 交換処理は `std::getenv(...) != nullptr` 相当の有無判定をします。値を数値や文字列として parse しません。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP 系・SYCL 系の serve 経路 | reread 無効。checkpoint を通常どおり復元 | 空文字、`0`、`1`、`true`、その他どの文字列でも有効 | なし。無効にする値表現はない |

したがって `0` や `false` も無効化値ではなく「設定あり」です。大文字小文字、空白、数値妥当性、境界値の検査はありません。CLI 引数や設定ファイルによる値の上書きもありません（`engine/src/program/generate.cpp:20095, 20230`; `engine/sycl/src/program/generate.cpp:11069, 11142`; `engine/src/core/conversation_state.cpp:787-790`）。

## 有効になる条件

- サーバーの会話処理で、既存の live session ではなく checkpoint から再開する分岐に入ること（`resume > 0` かつ `from_live == false`）。新規 prompt (`resume == 0`) は session をゼロ化する通常経路です（`engine/src/program/generate.cpp:20077-20086`; `engine/sycl/src/program/generate.cpp:11055-11065`）。
- `resume` と一致する checkpoint が見つかること。設定されていても checkpoint が見つからなければ復元失敗経路に入り、stdout に `ERR restoring a conversation checkpoint failed` を出してリクエスト処理を `return 1` します（`engine/src/program/generate.cpp:20087-20120`; `engine/sycl/src/program/generate.cpp:11066-11096`）。
- 値はプロセス全体で有効です。会話 K/V snapshot の交換候補が `conversation_snapshot_swap_prepare` に到達した場合、この変数が設定されているだけで交換準備を拒否します。他の条件でその交換候補にならなければ、この抑止分岐は呼ばれません（`engine/src/program/generate.cpp:19759-19774`; `engine/src/core/conversation_state.cpp:779-796`）。
- CUDA/HIP 系では、再読 checkpoint が `--prefill-pipe` の計画 chunk 内にある場合、元の計画が位置 0 から始まっていれば元の chunking を使って `[0, resume)` を読み直します。chunk が位置 0 以外から始まっていた場合はその旨を stderr に出し、この特別な計画は適用しません（`engine/src/program/generate.cpp:20138-20158`）。SYCL 側にはこの chunk 計画の分岐がありません。
- `STRATA_KVA` などの別設定が併用されても、本変数自体は再読を行います。Strata の `docs/KVA.md` は KVA 有効時に復元と再読で状態が異なり得ると説明していますが、これはこのスイッチが checkpoint と同じ状態を保証するという意味ではありません（資料: `docs/KVA.md:90-93`）。

## 実行時の詳細

checkpoint 再開分岐で `reread` を関数内 `static const bool` として初回評価し、値が設定済みで checkpoint があれば、CUDA/HIP 系では main session と各 stage をゼロ化して stream を同期し、SYCL 系では同様にゼロ化して stream を wait します。その後 `reread_to = resume` とし、stderr に `strata serve: STRATA_CKPT_REREAD: reading %lld tokens again instead of restoring` を出します（`engine/src/program/generate.cpp:20095-20111`; `engine/sycl/src/program/generate.cpp:11069-11085`）。

再読時は読み始めを 0 にし、`[0, resume)` を再読区間として後続の prompt 区間から分けます。MTP の K/V restore は行わず、CUDA/HIP 系で有効な MTP cell floor は 0 にします。また DFlash2 の request 開始位置も 0 にします。再読中は周期 checkpoint と tail checkpoint の保存を止めます（`engine/src/program/generate.cpp:20162-20174, 20187-20214`; `engine/sycl/src/program/generate.cpp:11100-11126`）。

別の `static const bool no_short` も同じ有無判定で初回評価されます。設定されていると `windows_ok` が常に false になり、短い prompt 区間も verify-window 経路にせず batched read にします。この判定は checkpoint 再読が実際に起きたかどうかとは独立しており、当該 serve 処理の prompt 読み取りに適用されます（`engine/src/program/generate.cpp:20229-20243`; `engine/sycl/src/program/generate.cpp:11141-11149`）。両方とも `static` 初期化後にプロセス環境を変更しても再評価されません。

## ログと測定値

checkpoint を再読する場合の stderr ログは `strata serve: STRATA_CKPT_REREAD: reading %lld tokens again instead of restoring` です。CUDA/HIP 系で checkpoint が位置 0 以外から始まる planned segment 内にある場合は、`strata serve: STRATA_CKPT_REREAD: the checkpoint is inside a segment that started at %lld, so a read from 0 has other chunks` も出ます（`engine/src/program/generate.cpp:20110-20111, 20154-20156`）。通常の checkpoint restore が失敗した場合は前節記載の stdout エラーになります。設定値が存在することだけを知らせる起動ログは確認できません。

Strata の設計資料は再読と復元が KVA 有効時に異なり得ると記していますが、この変数による性能値や一般的な正確性保証は記載しません（`docs/KVA.md:90-93`）。

## 根拠

- `engine/src/program/generate.cpp:20076-20120` — CUDA/HIP 系の checkpoint 選択、再読、復元失敗。
- `engine/src/program/generate.cpp:20138-20158, 20162-20214, 20229-20243` — planned segment、再読位置・補助状態、checkpoint 保存抑止、短区間の batched 化。
- `engine/sycl/src/program/generate.cpp:11055-11126, 11141-11149` — SYCL 系の同等経路。
- `engine/src/core/conversation_state.cpp:779-796` — snapshot K/V 交換を拒否する条件。
- `engine/src/program/generate.cpp:19759-19774` — snapshot 交換準備の呼び出し条件。
- `docs/KVA.md:90-93` — 再読と復元の差に関する Strata 資料。
