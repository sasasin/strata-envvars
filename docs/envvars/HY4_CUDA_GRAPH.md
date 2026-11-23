# `HY4_CUDA_GRAPH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の Hy4-Flash GPU runner で、decode と最大 8 行の verify に GPU graph capture/replay を使うかを選ぶ。`Runner::init` が設定を読み `cuda_graph_on` を決め、`forward_chunk` が条件に合う処理を graph 経路へ送る。CUDA では通常有効、HIP では既定無効であり、この変数は他の graph alias とともにその判定を上書きする。通常の eager 経路と比べて GPU 処理の投入方法を変えるもので、コード上、モデル選択や生成 token を変える設定ではない。`HY4_HAS_GRAPHS` が無効な build では読み取りも graph 経路もコンパイルされない（`engine/src/hy4flash/run/hy4_graph.hip.h:1712-1737, 3391-3398`; macro の既定定義は `engine/src/hy4flash/run/hy4_gpu.h:17-25, 324-334`）。

## 値と判定

`HY4_HAS_GRAPHS` が有効な build で、runner 初期化時に `getenv` で値を参照し、選ばれた値を `atoi` に渡す。優先順は `HY4_GPU_GRAPH`、`HY4_CUDA_GRAPH`、`HY4_HIP_GRAPH`。先行する変数が設定済み（空文字を含む）なら後続は参照されず、先行変数の文字列が採用される。従って `HY4_GPU_GRAPH` が設定済みなら `HY4_CUDA_GRAPH` は無視される（`engine/src/hy4flash/run/hy4_graph.hip.h:1712-1716, 1730`）。

`atoi` の結果が 0 なら無効、0 以外なら有効。文字列全体の検証はない。たとえば `1`、`-1`、`1tail` は有効、`0`、`0tail`、`true`、空文字は無効になる。先頭の空白や符号を含む数値接頭部は `atoi` の変換対象になる。数値接頭部がない文字列は 0 となる。unset の場合だけ build / GPU 条件別の既定値を使う。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `HY4_HAS_GRAPHS` 有効、CUDA build、Volta 制限なし | 既定 ON | `1`, `-1`, `1tail` | `0`, `0tail`, `true`, 空文字 |
| `HY4_HAS_GRAPHS` 有効、CUDA build、sm_70 かつ `volta_forever_active()` | 既定 OFF | 0 以外の整数接頭部 | `0`, `true`, 空文字 |
| `HY4_HAS_GRAPHS` 有効、HIP build | 既定 OFF | 0 以外の整数接頭部 | `0`, `true`, 空文字 |
| `HY4_HAS_GRAPHS` 無効 | 変数の読み取りなし | 該当なし | 該当なし |

「有効になる値」は優先順位上選ばれた変数の値を指す。より優先される alias が設定されていれば、この変数の値は判定に使われない。`atoi` が表現範囲外の数値に対して返す値はこのコードで検査されない（`engine/src/hy4flash/run/hy4_graph.hip.h:1712-1730`）。

## 有効になる条件

- build で `HY4_HAS_GRAPHS` が有効であること。CUDA / HIP の共通 GPU header は未定義時にこれを `1` とする（`engine/src/hy4flash/run/hy4_gpu.h:17-25, 324-334`）。
- graph が有効でも、runner の通常の forward は `T <= 8`、`dump`・`prof`・`prof2` が無効、かつ vision の修正処理が不要なときに限って graph 経路を呼ぶ。分散 expert と hybrid の組み合わせも graph 経路から除外される（`engine/src/hy4flash/run/hy4_graph.hip.h:3391-3398`）。
- DFly2 の graph 経路も `r.cuda_graph_on` を参照するが、draft 側の `isolate`、`skip`、profiling、dump 条件などで使われない場合がある（`engine/src/hy4flash/run/hy4_dfly2.hip.h:600-605, 1048-1055`）。
- `STRATA_HY4_DISTRIBUTED` build で `remote_experts` がある場合、`HY4_CUDA_GRAPH` と `HY4_GPU_GRAPH` の両方が unset なら、先の既定判定にかかわらず `cuda_graph_on` を OFF にする。ここは値の内容でなく設定有無を見るため、たとえば `HY4_CUDA_GRAPH=0` は OFF のままでもこの強制 OFF 分岐を避ける。`HY4_HIP_GRAPH` だけを設定してもこの分岐は避けない（`engine/src/hy4flash/run/hy4_graph.hip.h:1735-1737`）。
- CUDA の sm_70 で `strata::core::allow_1024_thread_cuda_graphs(...)` が false を返す場合は既定を OFF にするが、graph alias のいずれかに非ゼロ値が選ばれれば ON にできる（`engine/src/hy4flash/run/hy4_graph.hip.h:1718-1733`）。
- CLI による `cuda_graph_on` の上書き箇所は確認できない。`HY4_CUDA_GRAPH` 自体は `Runner::init` 中に評価されるため、その後の環境変更は runner の判定に反映されない（`engine/src/hy4flash/run/hy4_graph.hip.h:1437, 1712-1737`）。

## 実行時の詳細

読み取りは `Runner::init` の graph 初期化ブロックで行われ、結果は runner の `cuda_graph_on` メンバーに格納される。関数内 static やリクエストごとの読み直しではない。graph が有効なら `forward_chunk` は対象 chunk を `forward_chunk_graph` へ送り、捕捉した graph を launch/replay する。cache は chunk サイズなどのキーで graph executable を保持し、KV 領域の再配置・拡張などでは消去される（`engine/src/hy4flash/run/hy4_graph.hip.h:1195-1212, 2790-2793, 2852-2856, 2910-2940, 3391-3398`）。

初回 capture に失敗すると、コードは `[runner] GPU Graph capture ran low on VRAM (T=%d, peers=%zu); falling back cleanly to eager execution` を stderr に出し、graph cache を消去し、`cuda_graph_on` を OFF にして eager 経路を呼び直す。文言は VRAM 不足を示すが、同じフラグは capture 開始・終了または instantiate の失敗でも設定される。graph を有効にしたときの stderr は `[runner] CUDA Graph capture/replay enabled` または `[runner] HIP Graph capture/replay enabled`。Volta 既定無効時は `[runner] sm_70 under volta-forever: disabling 1024-thread CUDA Graph capture by default (HY4_CUDA_GRAPH=1 overrides)` が出る（`engine/src/hy4flash/run/hy4_graph.hip.h:1718-1733, 1751, 2913-2938, 3213-3219`）。

## ログと測定値

`docs/DGX_SPARK_LINUX.md` は分散例で `HY4_CUDA_GRAPH=1` を coordinator に設定し、decode と最大 8 行の verification window を capture すると記載する（`docs/DGX_SPARK_LINUX.md:183-185`）。ここでは測定値を記載していない。実装上は前述の分散条件・runner 条件に従う。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:1195-1212, 1437, 1712-1755` — runner 状態、読み取り、優先順、既定値、分散条件、起動ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2790-2793, 2852-2856, 2910-2940, 3213-3219, 3391-3398` — cache、capture 失敗時 fallback、graph 経路の適用条件。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:600-605, 1048-1055` — DFly2 が同じ runner flag を使う条件。
- `engine/src/hy4flash/run/hy4_gpu.h:17-25, 324-334` — CUDA / HIP build の graph macro 既定値。
- `docs/DGX_SPARK_LINUX.md:183-185` — 分散構成の設定例。
