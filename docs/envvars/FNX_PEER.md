# `FNX_PEER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP 版の Flash-Next 全カード split engine で、カード間の window sum と attention merge に peer device memory への送信を使うかを決める。`FNX_PEER` が未設定ならビルド定数 `PEER_DEFAULT_ON=true` により peer push を試し、値が完全一致で `"0"` なら host mailbox 経路を選ぶ。peer push を試す場合は engine の構築時に全カード間を probe し、どれかが失敗すれば実行全体のデータ交換を host mailbox 経路にする。CUDA ビルドにはこの環境読み取りがなく、同じ名前を設定してもこの engine の分岐は変わらない。根拠: `engine/src/split/src/engine.cu:120-132`, `engine/src/split/src/hip/peer_policy.hpp:17-40`, `engine/src/split/CMakeLists.txt:121-140`。

## 値と判定

`Engine::Engine` が HIP ビルド時に `std::getenv("FNX_PEER")` を呼び、helper `peer_decide` は値全体を `std::strcmp` で文字列 `"0"` と比較する。数値変換・空白除去・大文字小文字変換はない。未設定は `PEER_DEFAULT_ON`（現在 `true`）、設定値が厳密に `"0"` の場合だけ OFF、それ以外の設定値はすべて ON を要求する。

| ビルド・値 | 判定 | 結果 |
|---|---|---|
| HIP、unset | 既定 `true` | peer push を試す |
| HIP、`0` | `strcmp(env, "0") == 0` | host mailbox を選ぶ。peer probe を呼ばず、policy の行も出さない |
| HIP、`1` | `"0"` 以外 | peer push を試す |
| HIP、空文字 `""`、`00`、`0x`、`false`、`TRUE`、` 0` | いずれも `"0"` 以外 | peer push を試す |
| CUDA | `#if FNX_HIP` の外 | `FNX_PEER` を読まない |

根拠: `engine/src/split/src/hip/peer_policy.hpp:17-30`, `engine/src/split/src/engine.cu:125-132`, `engine/src/split/CMakeLists.txt:121-140`。

## 有効になる条件

- `FNX_PEER` の読み取りは `FNX_HIP` ビルドだけにあり、対象は `engine.cu` の Flash-Next `Engine`。CUDA 版と、別の通常 layer split 経路ではこの読み取りは行われない。HIP の split target は `FNX_27B=0` でビルドされる。根拠: `engine/src/split/src/engine.cu:1-2,125-132`, `engine/src/split/CMakeLists.txt:121-140`。
- launcher が all-cards split engine を実際に起動する必要がある。CLI / server が通常の layer split を選んだ場合、この変数を読む engine には到達しない。選択条件には OS、GPU 数・種類、モデル形式、engine package の有無などがある。根拠: `terminal/strata_control/split_engine.py:193-220,602-625`。
- `FNX_PEER` 未設定または `"0"` 以外の値では、HIP runtime が各向きのカード対を peer access 可能と報告し、peer access を有効化し、送信・全語比較・read-back・flag round trip の probe がすべて成功する必要がある。probe が失敗すると `peer_on=false` となり host mailbox 経路を使う。根拠: `engine/src/split/src/hip/peer.h:56-80,81-146`, `engine/src/split/src/hip/peer_policy.hpp:25-40`。
- `FNX_PEER_PARTS` は peer push が使える場合の対象を bit で選ぶ。既定 `3` は window sum（bit 1）と attention merge（bit 2）の両方、`1` は window sum、`2` は attention merge、両 bit がなければどちらの専用 mailbox も割り当てない。この変数は `FNX_PEER=0` の場合も HIP build で読み取られ、完全な 10 進整数でない値は `env_int` が例外にする。根拠: `engine/src/split/src/engine.cu:129-133,286-292`, `engine/src/split/src/env.hpp:15-21,33-40`。
- window sum の peer kernel にはさらに one-hop が必要で、`FNX_ONEHOP=0` では `ring.peer` が false になり、window sum は peer push kernel を選ばない。通常は 3 枚以上のカード、または `peer_on` で one-hop が選ばれるが、float32 ring では one-hop が無効。attention merge は `FNX_PEER_PARTS` の bit 2 によって受信 buffer の割り当て先が決まり、one-hop / ring の実装を選ぶ。根拠: `engine/src/split/src/engine.cu:308-316`, `engine/src/split/src/kernels.cu:1582-1614,1385-1421`。
- prompt chunk sum は別の分岐で、`FNX_PEER=0` なら peer 経路を使わない。peer が有効な場合でも `FNX_PF_PEER=0` なら host exchange を保ち、`FNX_PF_RCCL` が RCCL 利用を選ぶとその sum は RCCL が担当する。根拠: `engine/src/split/src/engine.cu:134-146`。
- `FNX_PEER_PROBE_FAIL=1` は peer を試す分岐で probe を意図的に失敗させる helper 入力。`FNX_PEER=0` のときは probe 自体を通らないため影響しない。根拠: `engine/src/split/src/hip/peer_policy.hpp:28-36`。

## 実行時の詳細

値は `Engine::Engine` の初期化中に一度だけ読み、`PeerDecision` の `use` を engine 構築時の `peer_on` に保存する。変数を読み直すループや request ごとの評価はないため、起動後の環境変更は既存 engine に反映されない。各 GPU の buffer 割当てで `FNX_PEER_PARTS` に応じた mailbox を作り、window sum は `ring.peer` のとき `k_ring_a2a_push` を選ぶ。同 kernel は各カードの addend を相手の device memory に書き、各カードは自分の mailbox から読み取って合計する。attention merge も peer mailbox を割り当てた場合、カード間 partial を所有カードへ送る。prompt chunk sum は `FNX_PF_PEER` と `FNX_PF_RCCL` も評価して別に決める。根拠: `engine/src/split/src/engine.cu:125-146,286-313`, `engine/src/split/src/kernels.cu:973-1001,696-744,1582-1614`。

probe は全 directed pair ごとに実施され、4 MiB の書込み値を receiver と sender の両方で比較し、200 回の flag round trip を確認する。probe のどの段階でも失敗すると `peer_decide` は `use=false` を返し、その run の交換経路を host mailbox にする。すでに probe の途中までに有効化された runtime peer access を無効化する処理はこの経路にはない。根拠: `engine/src/split/src/hip/peer.h:56-80,81-146`, `engine/src/split/src/hip/peer_policy.hpp:31-40`。

## ログと測定値

- peer probe 成功時は stderr に `fnx: Peer push between the cards is on (<probe summary>).`、続けて `FNX_PEER_PARTS` に応じた `fnx: peer push: ... pushed into the peers' memory` を出す。`FNX_PEER=0` は policy の行を出さない。probe 失敗時は stderr に `fnx: The cards cannot push into each other's memory here (<reason>): using the host exchange for this run.` を出す。根拠: `engine/src/split/src/hip/peer_policy.hpp:34-40`, `engine/src/split/src/engine.cu:129-146`。
- engine は buffer 割当ての後に `fnx: HOSTRING build: the cards exchange through page-locked host memory; peer access is never enabled, no peer probe, IOMMU and BAR1 checks skipped` も無条件に出す（`engine/src/split/src/engine.cu:296-299`）。これは同じ HIP 経路で先に peer probe・割当てを行う現行コード（`engine/src/split/src/engine.cu:125-151,286-292`）と整合しない文字列であり、この行の説明を実際の peer 分岐の根拠にはできない。
- `docs/SPLIT_ENGINE.md:77-80` は `FNX_PEER=0` でも fallback の plain line が出ると記述するが、現行 policy は厳密な `"0"` で空の `PeerDecision` を返し、policy line を出さない（`engine/src/split/src/hip/peer_policy.hpp:28-30`, `engine/src/split/src/engine.cu:129-130`）。また `docs/DETAILS.md` にこの変数の追加説明は見つからなかった。性能値は記載しない。
- peer mailbox の HIP allocation が失敗した場合は `FNX_PEER: fine-grained device allocation of <KiB> KiB failed` の例外になる。Engine 構築中の失敗は `ERR <error>` を出力し、stderr に `sfnx: failed: <error>` を出して `_Exit(1)` する。根拠: `engine/src/split/src/engine.cu:148-152`, `engine/src/split/tools/sfnx.cpp:1094-1103,1122-1136`。

## 根拠

- 読み取りと判定、既定値: `engine/src/split/src/engine.cu:125-132`; `engine/src/split/src/hip/peer_policy.hpp:17-40`
- HIP / CUDA build 条件: `engine/src/split/CMakeLists.txt:121-140`
- peer access と probe: `engine/src/split/src/hip/peer.h:56-146`
- buffer と one-hop 条件: `engine/src/split/src/engine.cu:286-313`; `engine/src/split/src/kernels.cu:1582-1614`
- window sum と attention merge: `engine/src/split/src/kernels.cu:696-744,973-1001`
- 関連する launcher 条件: `terminal/strata_control/split_engine.py:193-220,602-625`
