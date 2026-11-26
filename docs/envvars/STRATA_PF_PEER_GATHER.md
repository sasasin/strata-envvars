# `STRATA_PF_PEER_GATHER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の multi-GPU prompt peer が P2P を使えず、mapped host memory 経由の weighted sums を使う場合に、peer GPU 上で行う加算を「expert ごと」から「expert group ごと」の CUDA kernel launch に切り替える。group ごとに、その group の各 token に属する peer rows を一つの launch で `sum` に加える。値は転送形式、peer の expert 選択、routing weights、primary GPU 側の最終 combine を切り替えない。読み取りと設定は `Prefill::set_peer` の `PeerPrefill::gather` 初期化にある（`engine/src/prefill/prefill.cpp:3333-3339,3472-3485`）。

## 値と判定

`std::getenv` の返り値を `std::atoi` に渡し、結果が 0 以外なら有効とする。文字列全体の検証やエラー報告、clamp はない。`atoi` は数値の先頭部分を変換するので、例えば `1junk` と `-1` は非 0、`0anything` と `true` は 0 になる。空白や符号の後の数値も変換される。大文字小文字は数値判定に関係しない。数値範囲外の文字列について Strata 側に検査はない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `P.sums` が有効な CUDA/HIP peer prompt path | 有効（`getenv` が null なら `true`） | `1`, `2`, `-1`, `1junk` など `atoi` が非 0 にする値 | 空文字、`0`, `0anything`, `true`, `false` など `atoi` が 0 にする値 |
| P2P route、または `P.sums` 無効 | 読み取りなし。`gather` の値は使われない | 同左 | 同左 |

空文字は「未設定」ではなく設定済みの文字列であり、`atoi("") == 0` のため無効になる。`set_peer` 内で `STRATA_PF_PEER_GATHER` の fallback を選ぶ CLI 引数や別の環境変数はない。読み取り自体は `P.sums` が真のときだけ実行される（`engine/src/prefill/prefill.cpp:3467-3485`）。

## 有効になる条件

- `strata_prefill` の CUDA/HIP 実装で prompt peer path が組み込まれていること。`engine/src/prefill/prefill.cpp` は CUDA/HIP GPU engine の `strata_prefill` に含まれる（`engine/cmake/strata_gpu_engine.cmake:482-488`）。
- `strata generate --peer-device N` 等で有効な peer が開かれ、`--peer-prefill-rows` が `0` でないこと。未指定時の行数は `prefill_chunk * K / 2`。peer prompt helper を設定しない場合、この変数は読まれない（`engine/src/program/generate.cpp:4205,4209,13146-13150`）。
- peer 間で P2P が使われず、`STRATA_PF_PEER_SUMS` が未設定または `atoi` の結果が非 0 であること。`STRATA_PEER_NO_P2P=1` は peer 実装上 P2P を使わない経路にする。P2P が使える経路では sums mode に入らず、この変数は読まれない（`engine/src/core/peer_experts.cpp:208-218`; `engine/src/prefill/prefill.cpp:3467-3477`）。
- peer prompt path がモデル・build の適用条件を満たすこと。対象層に peer int8 または MMQ prompt path がない場合は拒否し、NVFP4 expert pack は拒否する。Hadamard-folded pack では診断を出して peer prompt を使わず、primary GPU に戻る。`STRATA_PF_OWN_ONLY` build では MMQ 対応層の条件に `pf_wmma()` も加わる（`engine/src/prefill/prefill.cpp:3340-3371`）。
- sums mode が有効なら peer 実装は compact path を使う。`STRATA_PF_PEER_COMPACT=0` でも P2P なしの場合は `!pp->p2p` により compact が強制される。`STRATA_PF_PEER_SUMS=0` なら sums mode 自体が無効になり、gather 設定は参照されない（`engine/src/prefill/prefill.cpp:3410-3417,3467-3485`）。

## 実行時の詳細

`Prefill::set_peer` が peer の状態・対応 layer を確認した後、P2P なしの compact path で `STRATA_PF_PEER_SUMS` を判定する。sums が有効な場合にこの変数を一度読み、group-table 用 device buffer と `tcur` を確保する。`set_peer` は prompt helper の設定・レイアウト時に呼ばれるため、prompt の各層や各 token ごとの読み直しではない。再レイアウトで helper を設定し直すと再評価される。既存 helper の実行中に環境を変更しても、その helper の `gather` には反映されない（`engine/src/program/generate.cpp:13143-13150`; `engine/src/prefill/prefill.cpp:3472-3485`）。

各 prompt chunk・layer で peer が担当する expert を group 化し、routing pair から group ごとの `[tokens | starts | rows]` テーブルを host 側で構成して peer GPU に転送する。`gather` が真なら、down projection の各 group の rows を `peer_gather_add` に渡し、token ごとに `wk[pair[r]]` を掛けて `sum` に加算する。kernel は token ごとの row list を順に処理する。偽なら group ごとの gather table を作らず、expert ごとに `peer_scatter_add` を呼んで同じ weighted sums を構成する（`engine/src/prefill/prefill.cpp:6665-6669,6704-6738,6883-6893`; `engine/src/prefill/kernels.cu:3433-3446,3468-3473`）。

いずれの分岐も最後は peer の `T x N` sums を mapped host memory に返し、primary GPU が自分の expert rows と combine する。変数はこの集約の launch 単位だけを選ぶ（`engine/src/prefill/prefill.cpp:6971-6980,7617-7629`）。

## ログと測定値

`STRATA_PF_PEER_GATHER` の値や gather/scatter の選択を示す専用ログはない。peer 設定成功時の共通ログは、P2P なし・sums 有効なら `strata prefill: peer GPU ... computes its experts' rows ...; no P2P: through mapped host memory, one weighted sum per token back`（FP16 の場合は `... in FP16, one weighted sum per token back`）と出すが、gather の値は表示しない（`engine/src/prefill/prefill.cpp:3537-3545`）。

gather table の構築結果が容量を超えると `prefill: the peer's group tables overflow` を返し、呼び出し側は `strata serve: ... - the prompt path stays on the primary GPU` と出して peer prompt を使わない。gather 用 buffer を含む peer buffer が確保できない場合は `prefill peer: the peer's buffers do not fit (raise --peer-reserve-mib or lower --peer-prefill-rows)` が設定エラーになる（`engine/src/prefill/prefill.cpp:3478-3482,3534-3537,6732-6736`; `engine/src/program/generate.cpp:13149-13152`）。Strata の資料にこの変数の測定値は確認できない。

## 根拠

- `engine/src/prefill/prefill.cpp:1387-1400` — sums と gather の役割を持つ状態。
- `engine/src/prefill/prefill.cpp:3333-3371` — peer path の entry、P2P 無効時の拒否、対応 layer と pack 条件。
- `engine/src/prefill/prefill.cpp:3410-3417,3467-3485` — compact/sums/gather の条件、`atoi` 判定、buffer 確保。
- `engine/src/prefill/prefill.cpp:6665-6738,6883-6893,6971-6980,7617-7629` — group table 構築、集約分岐、host 経由の戻りと primary 側 combine。
- `engine/src/prefill/kernels.cu:3433-3446,3468-3473` — group 単位の weighted sum kernel と起動。
- `engine/src/program/generate.cpp:4205,4209,13143-13150` — CLI と peer prompt helper の起動条件・再設定。
- `engine/src/core/peer_experts.cpp:208-218` — P2P 状態と `STRATA_PEER_NO_P2P` による host route。
- `engine/cmake/strata_gpu_engine.cmake:482-488` — CUDA/HIP GPU engine での prefill 実装の組み込み。
