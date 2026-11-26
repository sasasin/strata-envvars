# `STRATA_PF_PEER_HOST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`Prefill::set_peer` が、peer GPU 間で P2P を使えない場合にも peer に prompt の expert rows を計算させるための、mapped host memory 経由の経路を許すか決める。未設定または数値として非 0 ならこの経路を許し、数値として 0 なら peer の prompt 利用を断り、server はその prompt を primary GPU のみで処理する。P2P が利用できる場合、この値は読まれるものの分岐結果には使われない。`engine/src/prefill/prefill.cpp:3333-3339`

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば `std::atoi(v) != 0` で判定する。文字列全体の妥当性検査や範囲制限はない。`atoi` が先頭から数値として変換できない場合は 0 となるため、空文字、`false`、`true`、`0anything`、`anything` は拒否側、`1`、`-1`、`2tail`、` 1` は許可側になる。大文字小文字は真偽語の比較には使われず、空白や符号は `atoi` の数値変換規則に従う。`engine/src/prefill/prefill.cpp:3338-3339`

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `Prefill::set_peer` が呼ばれる peer prompt 経路 | ホスト経由を許可 | `atoi` の結果が非 0（例: `1`, `-1`, `2tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0anything`, `true`, `false`, `anything`） |

## 有効になる条件

- server が有効な peer GPU を開いていること。`--peer-device N` は `--expert-profile` と expert cache を必要とする。`engine/src/program/generate.cpp:1426-1433, 10211-10227`
- `--peer-prefill-rows` が 0 でないこと。既定の `-1` は chunk × top-k の半分を rows 上限にし、正数は指定数を使う。0 の場合は `set_peer` 自体を呼ばず、prompt は primary 上に残る。`engine/src/program/generate.cpp:13146-13153`
- この変数が拒否判定に影響するのは `peer->p2p()` が false の場合だけ。P2P 不可は、能力照会、`STRATA_PEER_NO_P2P` による強制、または peer copy の検証後に決まる。`STRATA_PEER_NO_P2P` を非 0 にすると peer open 側で P2P を無効化する。`engine/src/core/peer_experts.cpp:208-234`; `engine/src/prefill/prefill.cpp:3337-3339`
- prompt の peer 側で少なくとも一つの layer が MMQ または int8 prompt path に対応し、NVFP4 expert tail がなく、他の setup 条件を満たす必要がある。これらの条件は本変数では変わらず、満たさなければ別の理由で peer prompt が断られる。`engine/src/prefill/prefill.cpp:3340-3367`
- Metal target も `engine/src/prefill/prefill.cpp` を host source として含む一方、SYCL は別実装 `engine/sycl/src/prefill/prefill.cpp` で、この名前の読み取りがない。`engine/metal/CMakeLists.txt:135-145`; `engine/sycl/CMakeLists.txt:304-308`。変数名の一致する読取箇所だけでは、各 target で有効な peer GPU の構成までは確定できない。

## 実行時の詳細

候補名の全参照を調べたところ、環境から値を読む実装は `Prefill::set_peer` 内の 1 箇所。helper 経由や動的な名前渡しによる別の読み取りは見つからなかった。peer が null または無効なら読み取り前に戻る。そうでなければ `set_peer` 呼び出しごとに一度 lambda を評価し、結果を関数内で使う。関数 static やプロセス単位の cache はない。server は prompt path の設定時、および再レイアウト後の再設定時に `set_peer` を呼ぶため、その呼び出し時点の環境値を読む。`engine/src/prefill/prefill.cpp:3333-3339`; `engine/src/program/generate.cpp:13143-13169`

P2P がない状態で値が 0 扱いなら `set_peer` は `false` を返し、`err` に `prefill peer: the two GPUs cannot access each other (no P2P)` を設定する。server 呼び出し側は `strata serve: %s - the prompt path stays on the primary GPU` を stderr に出してエラーを消し、処理を続ける。拒否されず setup が完了すると、mapped pinned host buffers を確保し、peer 用 buffer allocation の失敗時は `set_peer` が別のエラーを返す。許可されたホスト経路では primary から mapped host buffer へ activation をコピーし、peer がそれを読み、結果 rows（または sums）を host memory 経由で戻す。`engine/src/prefill/prefill.cpp:3501-3537, 6613-6647, 7617-7625`; `engine/src/program/generate.cpp:13146-13153`

## ログと測定値

本変数を 0 扱いにして P2P 不可のため拒否された場合、server は上記の `strata serve: ... - the prompt path stays on the primary GPU` を stderr に出す。許可されて peer setup が通ると `strata prefill: peer GPU ...` の行が出て、P2P なしの場合は `no P2P: through mapped host memory`、sums 使用時には weighted sum に関する追加説明を含む。pinned host buffer が RAM に収まらない場合は `prefill peer: the host route's pinned buffers (...) do not fit in RAM`、peer buffer が確保できない場合は `prefill peer: the peer's buffers do not fit (raise --peer-reserve-mib or lower --peer-prefill-rows)` が server の stderr に渡る。`engine/src/prefill/prefill.cpp:3527-3545`; `engine/src/program/generate.cpp:13149-13153`

`docs/SECOND_GPU.md:70-86` は peer prompt の activation と結果が P2P 経由と説明し、`STRATA_PEER_NO_P2P=1` による host route を記すが、現行コードでは P2P がない場合も既定で mapped host route を許す。`STRATA_PF_PEER_HOST=0` でその経路を拒否する。ここでは本変数の比較測定値は見つからないため記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:3333-3339` — 環境読み取り、既定値、非 P2P 時の拒否条件。
- `engine/src/core/peer_experts.cpp:208-234` — P2P 判定と `STRATA_PEER_NO_P2P` による無効化。
- `engine/src/program/generate.cpp:1426-1433, 10211-10227, 13143-13169` — peer CLI 条件、server での setup、拒否後の primary fallback。
- `engine/src/prefill/prefill.cpp:3501-3545, 6613-6647, 7617-7625` — mapped host buffer 確保、setup ログ、転送と rows/sums の取り込み。
- `docs/SECOND_GPU.md:70-86` — peer prompt と P2P/host-route に関する文書との照合。
