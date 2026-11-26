# `FNX_PF_DMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Flash-Next split engine の prompt 経路で、カード間 ring の受信データを GPU kernel がホスト側スロットから直接読むか、copy engine でカードの device memory に転送してから kernel に渡すかを切り替える。`Engine::prefill_alloc()` が各カードの `PfRing::dma` に設定し、`pf_ring_run()` が受信・gather・出力の転送と kernel 入力先を選ぶ（`engine/src/split/src/prefill.cu:301-315, 854-860, 1201-1223`; `engine/src/split/src/pf_common.cuh:261-268, 325-368, 383-398`）。

## 値と判定

値は `fnx::env_int()` で整数として読み、0 以外なら DMA を有効にする。これは文字列全体を base 10 の `strtoll` で検査する: 先頭の `+` / `-` は許可され、少なくとも一桁が必要で、末尾まで数字でなければならず、`long long` の範囲外は拒否される。空文字、`true`、`1x`、`0anything`、先頭・末尾の空白は整数として受理されず、`FNX_PF_DMA: '<値>' is not a whole number` の例外になる。`-0` と `0` は無効、負数を含むその他の整数は有効。受理後の値域制限や clamp はない（`engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/prefill.cu:1209-1215`）。

| build 条件 | unset | DMA を有効にする値 | DMA を無効にする値 |
|---|---:|---|---|
| HIP (`FNX_HIP=1`) | `0` | `1`, `-1`, `+2` など 0 以外の整数 | `0`, `-0` |
| CUDA (`FNX_HIP` 未定義) | `1` | `1`, `-1`, `+2` など 0 以外の整数 | `0`, `-0` |

空文字や整数でない設定値は、どちらの build でも無効値として fallback せず例外になる。CLI 引数や別設定によるこの値の上書きはない。

## 有効になる条件

- 対象は `engine/src/split` の Flash-Next engine。CMake は CUDA split target に `FNX_HIP` を付けず、HIP split target に `FNX_HIP=1` を定義する（`engine/src/split/CMakeLists.txt:116-126, 138-143`）。他の Strata engine の環境変数動作を示す読み取り箇所は見つからなかった。
- `FNX_PF_DMA` は prompt buffer の確保時に読まれるが、効果が出るのは呼び出しが `pf_ring_run()` に到達する場合。`FNX_PF_RING_SM` が有効なら呼び出し側は SM ring に切り替わるため、この DMA 選択を使わない（`engine/src/split/src/prefill.cu:967-975, 1693-1699, 1762-1769`）。
- HIP で RCCL prompt sum が選択されている場合、`pf_ring()` は RCCL の all-reduce を実行して ring 処理を return するため、この設定によるコピー経路変更は使われない（`engine/src/split/src/prefill.cu:723-754`）。
- HIP の小 chunk all-to-all は、`p.a2a_rows > 0` かつ `C <= p.a2a_rows` かつ `own_out == false` のとき ring を迂回する。この条件では設定の効果はない。`own_out` が true の呼び出しはこの迂回条件から外れる（`engine/src/split/src/prefill.cu:744-754`）。
- `FNX_PF_GATHER` は ring plan を direct / ring のどちらにするか選ぶが、`FNX_PF_DMA` 自体の値は変更しない。HIP は `FNX_PF_GATHER=ring` 以外で direct、CUDA は `FNX_PF_GATHER=direct` のとき direct となる（`engine/src/split/src/prefill.cu:1201-1208, 1222-1223`）。
- 受信元スロットは HIP の `pf_peer_` 条件で peer device memory、その他で host memory に確保される。`FNX_PF_DMA` はこの確保方式を選ばず、選択済みスロットから ring kernel が使う device buffer への転送有無を決める（`engine/src/split/src/prefill.cu:977-998`; `engine/src/split/src/pf_common.cuh:325-368`）。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が呼ばれ、その中で各カードの ring 設定を組み立てる際に環境変数を読み込む。各カードで一度 `env_int()` を呼び、`PfRing::dma` に保存する。以後の prompt ring 実行では保存値を使い、処理中に環境を変更しても既存 Engine には反映されない（`engine/src/split/src/engine.cu:317-318`; `engine/src/split/src/prefill.cu:854-860, 1175-1180, 1209-1223`）。

DMA 有効時、ring の ADD / GADD 受信では `r.in` から `r.din` へ非同期コピーしてから add kernel を実行し、OUT では host gather buffer から `r.dag` へ転送して出力 kernel に渡す。direct gather を含む GADD では、DMA 有効時に device 側入力を読み、無効時は `r.in` を直接読む。DMA 無効時にはこの受信 buffer の device 転送を行わず、kernel が `r.in` を読む。転送 API が失敗したときは `ckc(..., "ring in" / "ring out" / "ring gather")` のエラー経路になる（`engine/src/split/src/pf_common.cuh:304-308, 325-368, 383-398`）。

`FNX_PF_DMA_CHECK` は DMA 有効時に転送元と device copy を比較する診断 kernel を追加する別設定であり、DMA の既定値や選択を変えない。`FNX_PF_DMA_BARRIER` は有効時に host-to-device copy 後の event record / wait を追加する（`engine/src/split/src/prefill.cu:1216-1221`; `engine/src/split/src/pf_common.cuh:283-289, 328-335, 354-360, 389-395`）。

## ログと測定値

`FNX_PF_DMA` の選択結果を通知する成功ログは見つからなかった。無効値は helper の例外となり、`fnx_run` では stderr に `fnx_run: <例外内容>` を出して終了コード 1、sFNX の fatal 経路では `ERR <例外内容>` を stdout、`sfnx: failed: <例外内容>` を stderr に出して終了コード 1 となる（`engine/src/split/tools/fnx_run.cpp:1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102`）。

HIP のコードコメントは gfx1201 で peer host stores に対する DMA read が常に完了しているとは限らず、結果が実行ごとに変わり、速くもなかったため opt-in にしたと説明する。ただし測定条件や数値は記載されていないため、一般的な性能・正確性の測定値としては扱えない（`engine/src/split/src/prefill.cu:1209-1210`）。

## 根拠

- `engine/src/split/src/env.hpp:15-21, 33-40` — 整数文字列全体の parse、unset 既定値、無効値の例外。
- `engine/src/split/src/prefill.cu:301-315, 854-860, 977-998, 1175-1223` — `PfRing` の設定、buffer 確保、全読み取り箇所、build 分岐と gather plan。
- `engine/src/split/src/pf_common.cuh:261-268, 283-289, 298-398` — 値によるコピー・kernel 入力・ring 処理の分岐。
- `engine/src/split/src/engine.cu:317-318`; `engine/src/split/CMakeLists.txt:116-126, 138-143` — Engine 初期化順と HIP/CUDA build macro。
- `engine/src/split/tools/fnx_run.cpp:1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102` — 例外の観測経路。
