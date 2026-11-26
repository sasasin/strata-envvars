# `FNX_PF_A2A_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

AMD HIP の split engine で、prompt chunk のカード間和を peer device memory の all-to-all と各カード上の和で処理する対象 chunk の最大行数を決める。既定値は 256 行で、値はモデルの prompt chunk 上限 `pf_c_` に切り詰められる。上限が 0 ならこの経路の mailbox は確保されず、chunk 和は ring に進む。CUDA ビルドにはこの読み取りと経路がない（`engine/src/split/src/prefill.cu:994-1010`; `engine/src/split/src/prefill.cu:744-755`）。

## 値と判定

`fnx::env_int("FNX_PF_A2A_ROWS", 256)` が環境変数を取得する。未設定の場合に限って 256。設定値は符号付き base-10 整数として文字列全体を `strtoll` で parse し、`long long` の範囲外、空文字、空白、数字以外、末尾の余分な文字は例外になる。先頭の `+` / `-` は受け付ける。例えば `256`、`+3`、`-1` は parse され、`true`、`0anything`、空文字は parse エラー。大文字小文字や真偽値としての解釈はない。parse 結果 `ar` は `max(ar, 0)` の後 `min(..., pf_c_)` で制限されるため、`0` と負数は 0、`pf_c_` 以上は `pf_c_` になる（`engine/src/split/src/env.hpp:15-21,33-40`; `engine/src/split/src/prefill.cu:1000-1009`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP で peer prompt 和を初期化 | `256` 行 | parse 可能な整数。正数は `1..pf_c_` に clamp | `0`、負数は parse 自体は有効だが 0 行となり all-to-all 無効。空文字、`true`、`0anything`、範囲外整数は parse エラー |
| CUDA、または peer prompt 和を使わない経路 | 読み取りなし | 該当なし | 該当なし |

## 有効になる条件

- split engine が HIP (`FNX_HIP`) でビルドされていること。対象 CMake は split engine の `prefill.cu` を HIP としてコンパイルし、`FNX_HIP=1` を定義する（`engine/src/split/CMakeLists.txt:21-24,79-91,123-129`）。
- エンジン初期化で peer access の判定が有効 (`peer_on`) になり、`FNX_PF_PEER` の整数値が 0 以外で、かつ RCCL prompt 和が選ばれていないこと。未設定 `FNX_PF_PEER` は 1。peer が使えない場合や `FNX_PF_PEER=0` の場合は `pf_peer_` が false となり、この変数の読み取り自体が行われない（`engine/src/split/src/engine.cu:123-146`）。
- `FNX_PF_A2A_ROWS` の clamp 後の値が正であること。正なら peer mailbox と flag を確保し、全カードの mailbox pointer を設定する（`engine/src/split/src/prefill.cu:1000-1009,1182-1190`）。
- 実際の chunk 和で `C <= a2a_rows` かつ `own_out` が false であること。そうでなければ通常の ring に進む。RCCL が有効な場合は `pf_ring` が先に RCCL all-reduce を実行して戻るため、all-to-all 分岐には到達しない（`engine/src/split/src/prefill.cu:723-755`）。

## 実行時の詳細

`Engine::prefill_alloc()` がカードごとの prefill workspace を作るとき、HIP かつ `pf_peer_` の場合だけ値を読み、カードごとに `p->a2a_rows` を設定する。static cache はなく、リクエストごとの読み取りでもない。読み取り後にプロセス環境を書き換えても、既に作成された `Pf` の上限は変わらない（`engine/src/split/src/prefill.cu:854-870,994-1009`）。

上限が正のとき、small chunk は `k_pfa_push` で他カードの mailbox に float32 addend を送り、`k_pfa_sum` で各カードが和を作る。その条件に当てはまらない chunk は `pf_ring_run` の ring 経路へ進む。環境変数は chunk 分割や `C` 自体を変えず、この和の実装選択だけを変える。コメントでは small-chunk sum は ring と bit-identical とされる（`engine/src/split/src/prefill.cu:721-755`; `engine/src/split/src/pf_common.cuh:151-190`）。

## ログと測定値

この変数の値や上限を示す専用ログはない。HIP peer prompt 経路が有効ならエンジンは `fnx: peer push: the prompt chunk sums are pushed into the peers' device memory` を stderr に出すが、これはこの上限が正か、特定 chunk が all-to-all を使ったかを示さない（`engine/src/split/src/engine.cu:144-146`）。

不正な整数文字列は `FNX_PF_A2A_ROWS: '<値>' is not a whole number` の例外になる。`sfnx` のエンジン初期化中の例外は `ERR <例外文>` を出力し、stderr に `sfnx: failed: <例外文>` を出して exit status 1 で終了する（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/tools/sfnx.cpp:1097-1103,1123-1135`）。`docs/DETAILS.md` と `docs/SPLIT_ENGINE.md` にこの変数の閾値や測定値の記載は見つからないため、性能値は記載しない。

## 根拠

- 変数参照・clamp・mailbox 確保: `engine/src/split/src/prefill.cu:994-1010`
- 値の parse: `engine/src/split/src/env.hpp:15-21,33-40`
- 適用条件と peer/RCCL 判定: `engine/src/split/src/engine.cu:123-146`
- small-chunk all-to-all と ring fallback: `engine/src/split/src/prefill.cu:721-755`
- 初期化と pointer 設定: `engine/src/split/src/prefill.cu:854-870,1182-1190`
- エラー出力と終了: `engine/src/split/tools/sfnx.cpp:1097-1103,1123-1135`
