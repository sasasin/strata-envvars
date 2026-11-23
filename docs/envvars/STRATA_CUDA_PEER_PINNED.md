# `STRATA_CUDA_PEER_PINNED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Ink CUDA の複数 GPU 経路で、GPU 間 P2P 転送を使わず pinned host memory 経由にするための選択スイッチです。`probe_p2p()` はこの変数が非ゼロなら GPU 能力確認や速度測定を始める前に `false` を返します。その戻り値が EP2 の P2P 使用可否、または layer-split の stage 間転送方式になります。単一 GPU の実行や、この probe を通らないロード経路には影響しません。`engine/src/inkling2/cuda/ink_runner.cuh:656-665, 835-885`。

## 値と判定

環境文字列を `std::getenv` で取得し、存在する場合に `std::atoi(env) != 0` を判定します。空文字・数値に変換できない文字列は `atoi` の結果が 0 なのでスイッチは働きません。数値全体の厳密な検証はなく、先頭の空白と符号を含む10進整数部分が変換され、後続の非数値文字は判定に使われません（例: `1junk` は非ゼロ、`0junk` はゼロ）。正負を問わず変換結果が非ゼロなら P2P を無効にします。`true` / `false` の文字列は整数に変換できないため無効です。`engine/src/inkling2/cuda/ink_runner.cuh:660-662`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Ink CUDA の `probe_p2p()` | この変数による抑止なし。後続の能力確認・測定で方式を決める | `1`, `-1`, `1junk` など `atoi` が非ゼロを返す値 | 空文字、`0`, `0junk`, `true`, `false`, 数字で始まらない文字列など `atoi` が 0 を返す値 |

## 有効になる条件

- Strata が Ink CUDA backend を含む構成であること。CUDA plugin は `STRATA_ENABLE_CUDA` が有効なとき追加され、Inkling CUDA target が Inkling executable に接続されます。`engine/src/inkling2/CMakeLists.txt:197-200`, `engine/src/inkling2/cuda/CMakeLists.txt:65-75, 96-104`。
- `InkCudaModel::load_from_model_file()` が複数 GPU の分岐に入り、少なくとも 2 GPU が選択されていること。CUDA backend は `--gpu` / `--gpus` / GPU ID リストから GPU を選びます。選択 GPU が 1 台だけなら probe は呼ばれません。`engine/src/inkling2/cuda/ink_cuda_backend.cu:112-131, 194-199`, `engine/src/inkling2/cuda/ink_runner.cuh:835-885`。
- 複数 GPU を選んでも、CLI の layer-split 選択によって probe の呼ばれ方が変わります。明示 layer-split、3〜4 GPU、GPU 世代差、総 VRAM の差が 15% 超、または Windows では先に layer-split を選び、その後 stage の組ごとに probe します。2 GPU でこれらに該当しない場合は probe を先に行い、P2P 不可なら `--layer-split off` / `none` / `ep2` で EP2 を強制していない限り layer-split に切り替えます。明示的な layer-split 値と `--layer-split auto` は `layer_split_spec` としてこの判定に渡されます。`engine/src/inkling2/cuda/ink_runner.cuh:835-885`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199`, `engine/src/inkling2/ink_main.cpp:472-473`。
- `STRATA_CUDA_PEER_P2P` との優先関係: `STRATA_CUDA_PEER_PINNED` の `atoi` 結果が非ゼロなら、後続で読む `STRATA_CUDA_PEER_P2P` を評価する前に `false` を返すため、P2P 強制指定より pinned 指定が優先します。対象変数が未設定または `atoi` 結果 0 なら、`STRATA_CUDA_PEER_P2P` の非ゼロ指定は P2P を強制します。`engine/src/inkling2/cuda/ink_runner.cuh:660-665, 757`。

## 実行時の詳細

この変数は `probe_p2p()` を呼ぶたびに読み直され、static cache はありません。読み取りは Ink CUDA モデルのロード中、複数 GPU 間の転送方式を決める時点です。通常はロード前に設定したプロセス環境値が使われますが、複数回の probe の間にプロセス環境自体が変更された場合、後続の probe は新しい値を読みます。ロード完了後に環境を変えても、既に設定された `ep2_p2p` / `stage_p2p` の値や実行中の転送方式は変わりません。probe は2 GPU EP の判定と layer-split stage の各組で呼ばれます。`engine/src/inkling2/cuda/ink_runner.cuh:660-665, 835-885`。

変数が非ゼロの場合、probe は CUDA API による P2P 能力確認、相互 P2P access の有効化、roundtrip 検証、P2P 対 pinned-host の時間比較を行わず `false` を返します。2 GPU EP を強制した経路では `ep2_active=true`、`ep2_p2p=false` となり、EP workspace に pinned host staging を確保します。推論中は入力・top-k index・重みを GPU から host staging に送り、peer GPU に転送し、peer 結果も host staging 経由で primary GPU に戻して加算します。`engine/src/inkling2/cuda/ink_runner.cuh:854-867, 2242-2259, 3164-3208`。

layer-split の場合は stage 間で `stage_p2p=false` となり、activation 等を pinned host bounce buffer に D2H / H2D で移します。コピーと event の順序付けは `copy_between_stages()` が行います。`engine/src/inkling2/cuda/ink_runner.cuh:880-885, 1823-1840`。

この変数が未設定またはゼロでも P2P が必ず有効になるわけではありません。双方向の `cudaDeviceCanAccessPeer` が成功しない場合、P2P access の有効化に失敗した場合、または転送検証に失敗した場合は probe が `false` になります。成功した通常判定では、roundtrip が正しいことに加えて P2P の平均時間が pinned-host 時間の 90% 未満かつ 500µs 未満の場合にだけ P2P を選びます。`STRATA_CUDA_PEER_P2P` が非ゼロならこの時間比較を飛ばし、検証成功時に P2P を選びます。`engine/src/inkling2/cuda/ink_runner.cuh:662-680, 699-708, 757-767`。

## ログと測定値

- 対象変数が非ゼロのため probe が冒頭で戻る場合、probe 自身は理由ログを出しません。2 GPU の自動選択で EP2 を強制していないと、呼び出し元は stderr に `[InkCUDA] Multi-GPU non-P2P detected: auto-selecting Pipeline Layer-Split (--layer-split auto, 6 handoffs/tok vs 48x EP sync)` を出します。`engine/src/inkling2/cuda/ink_runner.cuh:660-662, 858-863`。
- probe が通常の比較まで進み、roundtrip が成功した場合は stderr に `[InkCUDA] EP2 GPU%d<->GPU%d transport: %s (p2p=%.1f us vs pinned=%.1f us)` を出します。変数による早期 return、能力確認失敗、検証失敗、または `STRATA_CUDA_PEER_P2P` 強制時にはこのログ条件を満たしません。`engine/src/inkling2/cuda/ink_runner.cuh:763-766`。
- ロード完了時には EP2 経路で `ep2=%d, p2p=%d`、layer-split 経路で `[cuda-ls %d stages]` を含むログが出ます。EP2 の pinned staging 確保など `INK_CK` 対象の CUDA 呼び出しに失敗した場合は `strata-inkling CUDA error %d at %s:%d` を組み立てて device error 終了経路へ渡します。`engine/src/inkling2/cuda/ink_runner.cuh:1558-1572, 2254-2259`, `engine/src/inkling2/cuda/ink_cuda.cuh:32-40`。
- Strata の資料にこの環境変数の条件付き測定値は見つかりませんでした。ここでは測定値を記載していません。

## 根拠

- 読み取りと P2P probe: `engine/src/inkling2/cuda/ink_runner.cuh:656-767`
- GPU 数・CLI 選択を受けた EP2 / layer-split 決定と probe 呼び出し: `engine/src/inkling2/cuda/ink_runner.cuh:835-888`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:112-131, 194-199`, `engine/src/inkling2/ink_main.cpp:472-473`
- EP2 と layer-split の転送処理: `engine/src/inkling2/cuda/ink_runner.cuh:1823-1840, 2242-2259, 3164-3208`
- CUDA backend の build 条件とエラー報告: `engine/src/inkling2/CMakeLists.txt:197-200`, `engine/src/inkling2/cuda/CMakeLists.txt:65-104`, `engine/src/inkling2/cuda/ink_cuda.cuh:32-40`
