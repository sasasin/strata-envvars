# `HY4_HIP_GRAPH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。作業開始時の Strata の状態は `## main...origin/main`。

## 役割

`strata-hy4` の `Runner` が GPU Graph capture/replay を有効にするか選ぶ値の別名の一つです。これは runner の計算経路を切り替えます。初期値は CUDA では条件付きで ON、HIP では OFF ですが、`HY4_HIP_GRAPH` を含む環境変数で上書きできます。変数名に `HIP` が含まれますが、この読み取りは共通の HIP/CUDA 実装 `engine/src/hy4flash/run/hy4_graph.hip.h` にあり、CUDA build でも候補になります（同ファイル:1712-1730、`engine/src/hy4flash/run/hy4_gpu.h`:17-25,324-334）。

## 値と判定

`HY4_HAS_GRAPHS` が有効な build では、runner 初期化時に `getenv` で次の順に値を選び、最初に unset でない文字列を `atoi` に渡します: `HY4_GPU_GRAPH`、`HY4_CUDA_GRAPH`、`HY4_HIP_GRAPH`。従って上位の変数が空文字でも後続変数へ進まず、空文字は `atoi` により 0（OFF）になります。選択した値の判定は `atoi(value) != 0` です。`atoi` は先頭の空白と符号の後にある十進数字の先頭部分を変換し、数値として読めない文字列は 0 になります。全体一致や数値全体の妥当性検査はありません。たとえば `1`, `-1`, `2`, `1tail` は ON、`0`, `0tail`, `false`, 空文字は OFF です。`1tail` のように数字の後ろは判定に使われません。値の変換自体による警告はありません（`engine/src/hy4flash/run/hy4_graph.hip.h`:1712-1730）。

| build / 条件 | `HY4_HIP_GRAPH` を含む3変数がすべて unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `HY4_HAS_GRAPHS` が有効、CUDA、sm_70 で volta-forever が有効ではない（または他の CUDA device） | ON | 選択された文字列を `atoi` した値が非 0（例: `1`, `-1`, `1tail`） | 0（例: `0`, `false`, 空文字） |
| `HY4_HAS_GRAPHS` が有効、CUDA、sm_70 で volta-forever が有効 | OFF | 同上 | 同上 |
| `HY4_HAS_GRAPHS` が有効、HIP | OFF | 同上 | 同上 |
| `HY4_HAS_GRAPHS` が無効 | この環境変数は読み取られず、Graph 経路もこのコードでは利用されない | 該当なし | 該当なし |

CUDA の既定判定は `allow_1024_thread_cuda_graphs` の結果で、sm_70 かつ volta-forever 有効時のみ既定 OFF、それ以外は既定 ON です（`engine/src/hy4flash/run/hy4_graph.hip.h`:1717-1730、`engine/include/strata/core/volta_forever.hpp`:96-104）。この判定は後述の分散 build の強制 OFF 条件より先に行われます。

優先順位は `HY4_GPU_GRAPH` > `HY4_CUDA_GRAPH` > `HY4_HIP_GRAPH` です。たとえば `HY4_GPU_GRAPH=0` が設定されていれば、`HY4_HIP_GRAPH=1` は値選択に使われません。この runner 初期化では CLI 引数による別の設定値は参照されず、上記環境変数の選択と build/device による既定値で決まります（`engine/src/hy4flash/run/hy4_graph.hip.h`:1712-1730）。`atoi` が範囲外の数値文字列をどう扱うかは C の `atoi` の範囲外変換に依存し、Strata 側で検査・fallback していません。

## 有効になる条件

- Graph 関連コードが `#if HY4_HAS_GRAPHS` に含まれる必要があります。`engine/src/hy4flash/run/hy4_gpu.h`:24-25,332-334 では CUDA/HIP の両側で未定義時に `HY4_HAS_GRAPHS` を `1` としています。
- 分散 build (`STRATA_HY4_DISTRIBUTED`) で `remote_experts` を使う場合、`HY4_CUDA_GRAPH` と `HY4_GPU_GRAPH` の両方が unset なら `cuda_graph_on` を強制 OFF にします。この判定は値でなく設定有無を見るため、`HY4_HIP_GRAPH=1` だけでは強制 OFF を避けられません。一方、上位のどちらかが設定済みなら強制 OFF 条件を避けますが、実際の ON/OFF は優先順位と `atoi` 判定に従います（`engine/src/hy4flash/run/hy4_graph.hip.h`:1735-1737）。この build は CMake 上 Linux CUDA 用です（`engine/src/hy4flash/run/CMakeLists.txt`:4,56-64）。
- 通常の forward graph replay は `T <= 8` で、分散 remote experts と hybrid KV の組み合わせでなく、dump/profiling 中でなく、該当する vision fix 経路でない場合に限られます。条件外では `cuda_graph_on` が ON でも eager forward に進みます（`engine/src/hy4flash/run/hy4_graph.hip.h`:3391-3400）。
- DFly2 の draft/backbone 用 graph も同じ `cuda_graph_on` を参照しますが、isolate、skip、prof/prof2、dump の条件で使わない経路があります。評価 slot の graph は CUDA build でのみ参照されます（`engine/src/hy4flash/run/hy4_dfly2.hip.h`:600-602,855-856,1048-1049）。
- CUDA の sm_70 + volta-forever 条件では自動既定を OFF にし、ON にしない場合は `[runner] sm_70 under volta-forever: disabling 1024-thread CUDA Graph capture by default (HY4_CUDA_GRAPH=1 overrides)` を stderr に出します。これは警告というより既定判定の説明ログで、他の alias で上書きしても文面中の変数名は `HY4_CUDA_GRAPH` のままです（`engine/src/hy4flash/run/hy4_graph.hip.h`:1717-1733）。

## 実行時の詳細

値はオフライン CLI と serve のどちらも `Runner::init` 内で評価されます。オフライン実行は `r.init(...)` を呼び（`engine/src/hy4flash/run/hy4_main.hip.cpp`:692-705）、serve も Runner を作成して同じ初期化を行います（`engine/src/hy4flash/run/hy4_serve.hip.h`:307-317）。したがって値は Runner ごとに初期化時に読み込まれ、同じ Runner が動作中に環境を変更しても `cuda_graph_on` の値には反映されません。`cg_env` 自体を保持する static cache はありません。別 Runner の生成・初期化ではその時点の環境を再評価します（`engine/src/hy4flash/run/hy4_graph.hip.h`:1712-1737）。

ON の場合、対象 chunk について `forward_chunk_graph` を使い、入力状態に応じた `CgKey` ごとに capture 済み graph を `cg_cache` に保持します。キャッシュは最大 16 件で、上限時は先頭 entry を破棄します（`engine/src/hy4flash/run/hy4_graph.hip.h`:1198-1224,3050-3109,3391-3397）。DFly2 にも別の graph cache があり、上記条件下で同じフラグを参照します（`engine/src/hy4flash/run/hy4_dfly2.hip.h`:600-630,855-884）。

capture 開始・終了または instantiate に失敗したときは内部で失敗状態を立てます。runner は「GPU Graph capture ran low on VRAM」というログを出し、cache を消去して `cuda_graph_on` を OFF にし、その chunk を eager `forward_chunk` で再実行します（`engine/src/hy4flash/run/hy4_graph.hip.h`:2910-2939,3213-3219）。表示文言は低 VRAM としていますが、同じ失敗フラグは capture/instantiate の失敗全般で立つため、ログだけから原因を VRAM に限定できません。成功時は初期化時に `[runner] CUDA Graph capture/replay enabled` または `[runner] HIP Graph capture/replay enabled` を stderr に出します（同ファイル:1751）。

## ログと測定値

ソースコメントには `hipGraphInstantiate` による初回 verify capture の 80–150 ms stall の記述がありますが、測定条件はこのコメントに示されていません。これは実測の一般化に使わず、Strata の測定値としては扱いません（`engine/src/hy4flash/run/hy4_graph.hip.h`:1726-1728）。関連する `docs/DETAILS.md` にこの変数名または当該 graph の測定値の記載は見つかりませんでした。

## 根拠

- 値選択・変換・CUDA/HIP の既定値・sm_70 ログ: `engine/src/hy4flash/run/hy4_graph.hip.h:1712-1733`
- 分散時の強制 OFF: `engine/src/hy4flash/run/hy4_graph.hip.h:1735-1737`
- Graph build macro の既定: `engine/src/hy4flash/run/hy4_gpu.h:17-25,324-334`
- sm_70/volta-forever 既定条件: `engine/include/strata/core/volta_forever.hpp:96-104`
- Runner 初期化、通常 forward の適用条件・capture fallback: `engine/src/hy4flash/run/hy4_graph.hip.h:2910-2939,3213-3219,3391-3400`
- CLI / serve からの初期化: `engine/src/hy4flash/run/hy4_main.hip.cpp:692-705`; `engine/src/hy4flash/run/hy4_serve.hip.h:307-317`
- DFly2 graph の条件: `engine/src/hy4flash/run/hy4_dfly2.hip.h:600-602,855-856,1048-1049`
