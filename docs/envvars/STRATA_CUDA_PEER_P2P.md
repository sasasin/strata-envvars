# `STRATA_CUDA_PEER_P2P`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling 2 の CUDA runner が複数 GPU 間の通信方式を調べるとき、検証済み P2P を自動選択の基準にかかわらず使うよう要求する環境変数です。対象は `engine/src/inkling2/cuda/ink_runner.cuh` の `InkCudaRunner::probe_p2p` で、値が非ゼロなら P2P と pinned-host 経由の時間比較を省略し、P2P を選びます。ただし peer access の可否確認・有効化と双方向コピーの検証は省略しません。検証が通らない場合は P2P を選びません（同ファイル:660-705, 707-767）。

値が未設定または `atoi` の結果が 0 なら、検証後に P2P と portable pinned-host bounce を測定し、P2P が pinned-host より 10% 超速く、かつ 500 µs 未満の場合に限って P2P を選びます（`engine/src/inkling2/cuda/ink_runner.cuh:707-767`）。これは Inkling CUDA の複数 GPU transport 選択に限られ、他の Strata CUDA 実行経路にある P2P 転送を一括して有効化する設定ではありません。`docs/SETTINGS.md:50` は NVIDIA と AMD の両方を対象として記載していますが、確認できた読取箇所は CUDA runner のみです。ビルド設定でも CUDA と HIP は別 backend として追加されています（`engine/src/inkling2/CMakeLists.txt:152-202`）。

## 値と判定

`std::getenv` で取得し、`std::atoi(env) != 0` で判定します。文字列全体の厳密な数値検証ではなく、C の `atoi` による十進整数変換です。未設定は false、設定された空文字も `atoi("") == 0` で false です。先頭空白や符号の後の数値部分は変換され、数値の後ろに文字があっても数値部分で判定します。数値として変換できない先頭なら 0 です。したがって `1`、`-1`、`2`、` 1tail` は有効、`0`、`0anything`、`true`、`false`、空文字は無効です。大文字小文字は文字列として比較されません（`engine/src/inkling2/cuda/ink_runner.cuh:662-665`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Inkling 2 CUDA runner の P2P probe | 時間比較で選択 | `atoi` の結果が非ゼロ（例: `1`, `-1`, ` 1tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0anything`, `true`） |

## 有効になる条件

- CUDA backend を含む Inkling 2 の実行であること。ビルド構成では `STRATA_ENABLE_CUDA` が有効なとき CUDA plugin を追加します。HIP/SYCL/Metal backend は別に構成されます（`engine/src/inkling2/CMakeLists.txt:152-208`）。
- 読み込むモデルで複数 GPU が選ばれ、loader が `probe_p2p` を呼び出すこと。単一 GPU の `.strata` fast path は probe より前に返ります（`engine/src/inkling2/cuda/ink_runner.cuh:789-794, 835-888`）。2 GPU EP2 選択時の判定、および Layer-Split の各 GPU pair 検査で呼ばれます（同:853-885）。
- 双方向の `cudaDeviceCanAccessPeer` が成功して両方向とも利用可能であり、peer access の有効化、メモリ割り当て、双方向コピー、コピー内容の照合が通ること。失敗すればこの変数が非ゼロでも probe は false を返します（同:667-705）。
- `STRATA_CUDA_PEER_PINNED` が設定され、その `atoi` 結果が非ゼロなら、そちらを先に判定して直ちに false を返すため、この変数の値は読まれず P2P probe は不採用になります（同:660-665）。
- `--layer-split` などの CLI 指定や GPU 構成は probe を行う経路を決めます。2 GPU で `--layer-split off` / `none` / `ep2` が指定された場合、probe が false でも EP2 自体は選択され、`ep2_p2p` は false となって pinned-host 経由になります。自動選択では probe が false なら Layer-Split に切り替わります（同:835-870, 3167-3190）。

## 実行時の詳細

CUDA backend の model loader は `load_from_model_file` を呼び、選択 GPU を集めた後で multi-GPU mode を決めます。単一 GPU の `.strata` fast path では probe を行いません。複数 GPU のうち2 GPUを EP2 として扱う経路では pair を1回 probe し、P2P が選ばれれば `ep2_p2p` に保存します。Layer-Split では異なる各 GPU pair を probe し、その結果を `stage_p2p` に保存します（`engine/src/inkling2/cuda/ink_runner.cuh:789-888`）。

この環境変数は `probe_p2p` の呼び出しごとに読み直され、関数内やプロセス全体に値を cache するコードはありません。したがってプロセス実行中に環境を変更すれば、後続 probe の読み取りには反映されますが、すでに決定済みの `ep2_p2p` / `stage_p2p` は再計算されません（同:660-665, 853-885）。

非ゼロ設定でも、probe はまず両 GPU で peer access を有効にし、9,216 byte のパターンを往復転送して一致を確認します。成功後、非ゼロ設定なら性能比較を行わず P2P を選択し、false の場合に有効化した peer access を無効化します（同:667-705, 707-767）。採用された EP2 P2P では expert 入力・top-k 情報・出力を `cudaMemcpyPeerAsync` で転送し、不採用時は pinned host buffer を介して転送します（同:3167-3190）。

## ログと測定値

環境変数自体に対する専用の有効・無効ログはありません。probe がコピー検証まで成功し、P2P 強制ではない場合に限り、stderr に `[InkCUDA] EP2 GPU%d<->GPU%d transport: %s (p2p=%.1f us vs pinned=%.1f us)` を出します。非ゼロ設定では時間比較を省略するため、このログは出ません（`engine/src/inkling2/cuda/ink_runner.cuh:707-767`）。

自動選択で2 GPU probe が false になると、`--layer-split` が EP2 強制でない場合、stderr に `[InkCUDA] Multi-GPU non-P2P detected: auto-selecting Pipeline Layer-Split (--layer-split auto, 6 handoffs/tok vs 48x EP sync)` を出します（同:853-870）。環境変数だけを理由にした警告やエラー終了経路はありません。peer access・コピー等の失敗時は probe が false を返し、呼び出し側の選択に委ねます（同:667-705, 853-870）。

## 根拠

- `engine/src/inkling2/cuda/ink_runner.cuh:656-767` — 値の読み取り、`atoi` 判定、P2P 可否・コピー検証、強制選択と時間比較、ログ。
- `engine/src/inkling2/cuda/ink_runner.cuh:789-888` — 単一 GPU fast path、multi-GPU mode 分岐と probe 呼び出し。
- `engine/src/inkling2/cuda/ink_runner.cuh:3167-3190` — EP2 の P2P / pinned-host 転送分岐。
- `engine/src/inkling2/CMakeLists.txt:152-208` — CUDA と HIP/SYCL/Metal backend の構成分岐。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199` — CUDA backend から model loader を呼ぶ箇所。
