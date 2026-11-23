# `HY4_GPU_GRAPH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash GPU runner の decode（1 行）および verify（最大 8 行）の処理で GPU Graph capture/replay を使うかを設定する。グラフ有効時も、`forward_chunk` が `T <= 8` などの条件を満たす呼び出しだけがグラフ経路に入り、それ以外は通常の eager 経路を使う。CPU 実装にはこの設定読み取りはない。読み取りとフラグ設定は `Runner::init` 内、capture/replay の選択は `Runner::forward_chunk` 内にある（`engine/src/hy4flash/run/hy4_graph.hip.h:1437-1438, 1712-1736, 3384-3398`）。

## 値と判定

`HY4_HAS_GRAPHS` が有効なビルドで `getenv("HY4_GPU_GRAPH")` を読み、設定されていれば `atoi` の結果が 0 以外のとき ON とする。整数全体の検証や文字列比較はしない。したがって `1`, `-1`, `1anything`, ` 1` は ON、`0`, `0anything`, 空文字, `true`, `false`, 数字で始まらない文字列は `atoi` が 0 を返すため OFF。前後空白を取り除く処理もない。数値変換の範囲外入力の扱いはこのコードで検査していない（同ファイル `:1714-1716, 1730`）。

| 条件 | `HY4_GPU_GRAPH` 未設定 | 設定値 |
|---|---|---|
| 通常の `HY4_HAS_GRAPHS` ビルド | `HY4_CUDA` が真なら CUDA デバイス条件に応じて既定 ON/OFF。HIP なら既定 OFF | `atoi(value) != 0` なら ON、0 なら OFF |
| 分散ビルドで remote experts を使う Runner | 上記の後、`HY4_CUDA_GRAPH` と `HY4_GPU_GRAPH` のどちらも未設定なら強制 OFF | この変数が設定されていれば、remote-expert 用の追加強制 OFF は適用されない（値が空または `0` でも同様） |

設定名の優先順位は「`HY4_GPU_GRAPH` が設定済みならその値、そうでなければ `HY4_CUDA_GRAPH`、さらに未設定なら `HY4_HIP_GRAPH`」。上位名が空文字でも下位名へは進まず、空文字は OFF と判定される。別名は同じ `atoi != 0` 判定に入る（同ファイル `:1714-1716, 1730`）。

## 有効になる条件

- `HY4_HAS_GRAPHS` を有効にした Hy4-Flash の CUDA または HIP GPU build が必要。`engine/src/hy4flash/run/hy4_gpu.h:17-25, 324-334` では両方の backend で既定値を 1 としているが、build 側から上書きできる。
- `HY4_GPU_GRAPH` の非ゼロ値は backend の既定値を上書きする。CUDA では `cudaGetDevice` / `hipGetDeviceProperties` から対象デバイスを調べ、`allow_1024_thread_cuda_graphs(...)` が false（Volta-forever 条件）なら既定 OFF。HIP の既定値は OFF（`engine/src/hy4flash/run/hy4_graph.hip.h:1718-1730`）。
- `STRATA_HY4_DISTRIBUTED` build で `remote_experts` があると、`HY4_CUDA_GRAPH` と `HY4_GPU_GRAPH` の両方が未設定の場合はグラフを強制 OFF にする。`HY4_HIP_GRAPH` だけを設定してもこの追加 gate は解除されない（同ファイル `:1735-1736`）。
- フラグ ON でも各 `forward_chunk` が `T <= 8`、dump/profiling なし、分散 remote-expert hybrid ではなく、かつ tree 呼び出しであるか非 tree 呼び出しで vision fix-up が不要な場合に限り graph 経路を使う（同ファイル `:3391-3398`）。
- CLI 引数による同フラグの上書きは読み取り箇所にない。単発 runner と server runner はどちらも `Runner::init` を呼ぶ（`engine/src/hy4flash/run/hy4_main.hip.cpp:692-703`; `engine/src/hy4flash/run/hy4_serve.hip.h:307-315`）。

## 実行時の詳細

設定は `Runner::init` の graph 初期化ブロックで読み、`cuda_graph_on` に保存する。プロセス中の環境変更を監視する仕組みはなく、このフラグは runner ごとの初期化時に決まる。分散 build では同じ初期化ブロック内で `HY4_CUDA_GRAPH` / `HY4_GPU_GRAPH` の有無をもう一度確認して追加 gate を適用する（`engine/src/hy4flash/run/hy4_graph.hip.h:1712-1736`）。

適格な `forward_chunk` は `forward_chunk_graph` に進み、処理状態を含む `CgKey` で runner 内の graph cache を探す。未登録なら capture/instantiate して保存し、その後の該当状態で再利用する。通常・Engram・multi-GPU・hybrid の状態に応じて一括または分割した graph を構成する（同ファイル `:3050-3112, 3133-3205`）。通常の decode/verify 自体が常に graph 化されるわけではなく、前節の eligibility 条件を外れた場合は eager 経路へ進む。

capture 開始・終了または instantiate に失敗すると、capture helper は失敗フラグを立てる。runner は `[runner] GPU Graph capture ran low on VRAM (T=%d, peers=%zu); falling back cleanly to eager execution` を stderr に出し、graph cache を消去してフラグを OFF にし、同じ chunk を eager 経路で再実行する（同ファイル `:2913-2938, 3213-3219`）。ログ文面は VRAM 不足と表現しているが、helper は各 API の失敗をまとめてこのフラグにしており、コードだけでは失敗理由を VRAM 不足に限定できない。

## ログと測定値

フラグが有効なら初期化時に stderr へ `[runner] CUDA Graph capture/replay enabled` または `[runner] HIP Graph capture/replay enabled` を出す。無効時は通常この有効ログは出ない。CUDA の Volta-forever 条件で無効なら `[runner] sm_70 under volta-forever: disabling 1024-thread CUDA Graph capture by default (HY4_CUDA_GRAPH=1 overrides)` を出す。capture 失敗時の fallback ログは前節のとおり（`engine/src/hy4flash/run/hy4_graph.hip.h:1731-1732, 1751, 3214-3219`）。

同ファイルのコメントは AMD HIP について、42-layer MoE graph の初回 verify capture に `80-150ms` の停止があると記すが、機種・計測条件・測定方法は示されていないため、一般的な実測値としては扱えない（同ファイル `:1726-1728`）。`docs/DGX_SPARK_LINUX.md:183-185` は分散 coordinator で `HY4_CUDA_GRAPH=1` を設定する運用例を記載している。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:1712-1736` — build guard、別名優先順位、backend 既定値、分散時の gate。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1738-1752` — 初期化時のログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:3050-3112, 3133-3219, 3384-3398` — graph cache/capture、失敗時 fallback、呼び出し条件。
- `engine/src/hy4flash/run/hy4_gpu.h:17-25, 324-334` — CUDA/HIP build における `HY4_HAS_GRAPHS` の既定値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:692-703`; `engine/src/hy4flash/run/hy4_serve.hip.h:307-315` — 単発・server runner の初期化呼び出し。
- `docs/DGX_SPARK_LINUX.md:183-185` — 分散運用での関連別名の説明。
