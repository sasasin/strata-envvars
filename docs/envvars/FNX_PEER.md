# `FNX_PEER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査範囲は Strata 所有ソース。外部ライブラリ・driver の挙動は含めない。

## 役割

AMD HIP 版の all-cards split engine（`strata-split-N`）が、カード間の window sum と attention merge の交換に peer push を使うかを決めます。peer push は送信側の kernel が相手カードの device memory に書き込む経路です。`FNX_PEER` を読む本番箇所は `src/split/src/engine.cu` の HIP 条件ブロック内だけです。CUDA 版ではこの環境変数は読まれません（`src/split/src/engine.cu:86-94`、`src/split/CMakeLists.txt:97-109`）。

## 値と判定

`peer_decide()` は値全体を文字列比較し、数値変換はしません。`FNX_PEER` の未設定と設定値は次のように判定されます。

| 値 | 判定 |
| --- | --- |
| 未設定 | `PEER_DEFAULT_ON` を使う。現 commit では `true` なので peer probe を行う |
| `0`（文字列がちょうど `0`） | peer push を無効化し、probe とこの変数由来のログを出さない |
| その他の設定値 | peer push を要求して probe する。空文字、`00`、`false`、` 0` も含む |

大文字小文字・前後空白の除去や数値としての妥当性検査はありません。CLI 引数による `FNX_PEER` の上書きもありません。`--split-engine` / `STRATA_SPLIT_ENGINE` は split engine 自体を選ぶ launcher 側の設定であり、engine 起動後の peer 判定とは別です（`strata_control/split_engine.py:356-374`）。

## 有効になる条件

- HIP でコンパイルされた split engine が起動すること。ビルド設定は Linux の CUDA/HIP split engine を対象にし、HIP target は `FNX_HIP=1` でコンパイルされます（`src/split/CMakeLists.txt:1-5,97-109`）。
- launcher が all-cards split engine を選ぶこと。モデル・GPU・起動設定などにより launcher が通常の layer split を選んだ場合、この engine 内の `FNX_PEER` 判定には到達しません（`strata_control/split_engine.py:372-389`、`strata_cli/launch/runner.py:1630-1647`）。
- 未設定または `0` 以外の値で peer push を要求した場合、engine 起動時に全カード間の全 directed pair の probe が成功すること。peer 可否確認、peer access の有効化、書き込み・比較・read-back・flag round-trip のどれかが失敗すれば、peer push は全 run で使わず host-memory exchange にします（`src/split/src/hip/peer.h:58-80,81-145`）。

`FNX_PEER_PARTS` は peer が有効なときに window sums（bit 1）と attention merge（bit 2）のどちらに peer memory を使うかを選びます。既定値は `3`（両方）です。この値は `FNX_PEER` の on/off 判定を変えません（`src/split/src/engine.cu:90-94,244-250`）。window sum は `FNX_ONEHOP` が非 0、fp16 ring、`T <= MAXT` の場合に専用 peer-push kernel を選び、各カードが自分の値を他カードの mailbox に書き、各カードが自分の mailbox から他カードの値を読みます。それ以外はこの専用 peer-push kernel を使いません（`src/split/src/engine.cu:266-270`、`src/split/src/kernels.cu:976-1004,1568-1598`）。attention merge 側では bit 2 が ring buffer を fine-grained device memory に確保し、one-hop 経路は各カードの buffer に書いて他カードの buffer を読みます（`src/split/src/engine.cu:243-250,258-268`、`src/split/src/kernels.cu:952-973`）。

## 実行時の詳細

環境値は `Engine` の構築中、カード一覧を作った直後に一度読みます。`FNX_PEER` 自体は `static` cache されませんが、この判定結果 `peer_on` は engine instance の初期化中に決まり、既に作成済み engine に対する環境変更を再読する経路はありません（`src/split/src/engine.cu:31,84-94`）。

peer push が要求され、probe が成功した場合、stderr に `fnx: Peer push between the cards is on (...)` と probe 結果を出し、続けて有効な部位を示す `fnx: peer push: ... pushed into the peers' memory` を出します。失敗した場合は `fnx: The cards cannot push into each other's memory here (...): using the host exchange for this run.` を出し、peer push 用 buffer を確保しません。`FNX_PEER=0` なら `peer_decide()` は空のログと無効判定を返します（`src/split/src/hip/peer_policy.hpp:20-40`、`src/split/src/engine.cu:90-94,245-247`）。

`FNX_PEER_PROBE_FAIL=1` は要求された probe を意図的に失敗扱いにします。`FNX_PEER=0` のときは probe に進まないため、この設定は判定に影響しません（`src/split/src/hip/peer_policy.hpp:32-36`）。peer 成功後の fine-grained device buffer 確保に失敗すると、engine は `FNX_PEER: fine-grained device allocation of ... KiB failed` の例外で初期化に失敗します（`src/split/src/engine.cu:106-111`）。

## 根拠

- 唯一の本番読み取りと判定呼び出し: `src/split/src/engine.cu:84-94`。
- 既定値、完全一致の `0` 判定、fallback とログ文言: `src/split/src/hip/peer_policy.hpp:17-40`。
- probe のカード間可否・有効化・データ比較・round-trip 判定: `src/split/src/hip/peer.h:58-145`。
- peer memory buffer の割り当てと例外: `src/split/src/engine.cu:106-111,244-250`。
- all-cards split engine の HIP build 条件: `src/split/CMakeLists.txt:1-5,97-109`。
- 候補一覧との照合: `docs/envvars/000_envvers.md` に `FNX_PEER` の項目があり、今回の調査では Strata 所有ソースに実際の読み取りを確認した。

なお、`src/split/src/hip/peer_policy.hpp:17` のコメントには「既定は off」とありますが、同じファイルの実コードは `PEER_DEFAULT_ON = true`（18 行）です。本書は実行分岐を根拠に現 commit の既定を記載しています。
