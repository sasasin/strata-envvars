# `INK_HIP_PEER_PINNED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査対象リポジトリの作業状態は `## main...origin/main`。

## 役割

Ink HIP backend の二 GPU Expert Parallelism（EP2GPU）で、GPU 間 peer-to-peer (P2P) 転送の有効化と往復プローブを行わず、host-pinned memory を介する転送経路を選ぶための環境変数である。環境変数が有効でも EP2GPU 自体を有効にする設定ではなく、二 GPU 条件を満たした backend 初期化で EP2GPU が組まれた場合に P2P の使用を抑止する（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-629,681-682`）。

## 値と判定

`HipBackend::init()` の EP2GPU 初期化ブロックで `std::getenv` を一度呼び、値が存在し、かつ先頭バイトが文字 `'1'` の場合だけ P2P 判定をスキップする。文字列全体の比較・数値変換・空白除去はない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:628-630`）。

| 条件 | unset | P2P を抑止する値 | P2P プローブを試す値 |
|---|---|---|---|
| Ink HIP backend で EP2GPU の候補がある場合 | プローブを試す | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `true`, `True`, `01`, ` 1`（先頭が `1` でない） |
| EP2GPU 初期化ブロックに入らない場合 | 読み取りなし | 適用されない | 適用されない |

「プローブを試す」は P2P 使用を保証しない。二方向の `hipDeviceCanAccessPeer` が成功して両方向とも利用可能な場合に peer access を有効化し、16-byte データの GPU 間往復コピーと内容比較を行う。いずれかの条件に失敗すれば pinned-host fallback となる（同 `:628-680`）。この環境変数に対応する CLI 引数や別の Strata 環境変数による上書きは同 backend の実装にはない。

## 有効になる条件

- HIP backend が選択され、その `HipBackend::init()` が実行されること。CUDA・CPU 等の別 backend ではこの読み取り箇所を通らない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-560,628`）。
- `opts.gpus >= 2` または `opts.gpu_ids.size() >= 2` で、かつ `hipGetDeviceCount` が返す可視 HIP device 数が 2 以上であること。GPU 1 の選択と stream/event 初期化にも成功する必要がある（同 `:570-571,602-626`）。
- GPU 1 へ配置する expert がモデルの配置計画に少なくとも 1 件あること。計画が空なら `ep2_active_` が false に戻り、以降の peer MoE 経路は使われない（同 `:1064-1102`）。したがって環境変数が `1` 始まりでも、単一 GPU、device 不足、初期化失敗、peer 側配置なしでは pinned 転送経路は有効にならない。

## 実行時の詳細

読み取りは EP2GPU 候補の初期化中に毎回行われ、関数内 static cache はない。起動後に環境を変更しても初期化済み backend の判定は変わらない。backend を初期化する前に設定した値が判定に使われる（同 `:602-630`）。

先頭が `1` の場合、コードは `hipDeviceCanAccessPeer`、`hipDeviceEnablePeerAccess`、16-byte 往復プローブを含むブロック全体を飛ばす。`ep2_p2p_` は初期値 `false` のまま、GPU 1 に peer expert が配置され EP2GPU が残れば `ep2_active_` は true になる（同 `:578-580,628-682,5406-5407`）。これは Strata が peer access を無効化する処理ではなく、当該初期化で有効化を試みず、その後に P2P 転送経路を選ばない動作である。

`ep2_p2p_ == false` のとき `ensure_peer_scratch()` は必要なサイズに応じて `hipHostMalloc` で activation、expert id、weight、結果用の host buffer を確保する。peer MoE 入力は GPU 0 から host へコピーして stream を同期し、host から GPU 1 へコピーする。結果は GPU 1 から host へ戻し、event 同期後に GPU 0 へコピーして GPU 0 の MoE 出力へ加算する（同 `:2744-2787,2790-2824,2880-2908`）。従って変わるのは GPU 間データ転送経路であり、peer 側 MoE の計算自体は引き続き実行される。

## ログと測定値

EP2GPU が有効なら初期化時に stderr へ `[ink-hip] Dual-GPU EP2 active: ... | split=%.2f p2p=pinned` が出る。backend の device info にも `[EP-2GPU ... p2p=pinned ...]` と表示される（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:517-538,1324-1329`）。強制 pinned のときは P2P probe failure の警告は出ない。プローブ自体を実行して往復確認に失敗した場合は `[ink-hip] Hardware P2P roundtrip probe FAILED (GPU%d<->GPU%d); using pinned-host DMA fallback` が stderr に出る（同 `:667-680`）。

pinned buffer 確保や転送 API などが失敗すると、`hip_ok` は `[ink-hip] <処理名>: <HIP error string>` を `err` に設定して false を返す。peer scratch 確保・コピー・同期の失敗は呼び出し元へ伝播し、peer 処理を成功として完了しない（同 `:217-221,2755-2785,2800-2824,2880-2908`）。Strata の資料にこの変数による性能測定値は見つからなかった。

## 根拠

- 候補名の Strata ソース参照は `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:628` のみ。そこに `std::getenv` で直接読み取りがあり、動的 env helper 経由の読み取りはない。
- EP2GPU 条件・P2P プローブ・fallback 判定: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-682`。
- peer 側配置が空の場合の無効化: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1064-1102`。
- pinned-host buffer と転送経路: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2744-2787,2790-2824,2880-2908`。
- 初期化ログ・device info: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:517-538,1324-1329`。
