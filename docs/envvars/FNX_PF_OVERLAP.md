# `FNX_PF_OVERLAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の prompt prefill で、chunk の attention / FFN 出力をカード間 ring で合算する処理を別 CUDA stream に投入し、次の chunk の計算と重ねるかを切り替える。未設定時は有効。無効にすると ring 合算は通常のカード stream 上で順に実行される。値は `Engine::prefill_alloc()` で `Pf::overlap` に格納され、`Engine::prefill()` の attention merge、FFN の待ち合わせ、ring の実行経路を変える。`engine.cu` から `prefill_alloc()` が呼ばれるため、Engine 初期化時に評価される（`engine/src/split/src/engine.cu:318`、`engine/src/split/src/prefill.cu:854-857,1063-1089,1300-1304`）。

## 値と判定

`env_int("FNX_PF_OVERLAP", 1)` は共通 helper `env_int` を通じて環境変数全体を符号付き base-10 `long long` として読み取る。未設定だけが既定値 `1` になる。値が `0` 以外なら真、`0` なら偽。正負の符号は許されるが、空白、空文字、数値以外、末尾の余分な文字、`long long` の範囲外は整数として受け付けず例外になる。値の範囲 clamp はない（`engine/src/split/src/env.hpp:15-21,33-40`、読み取り箇所 `engine/src/split/src/prefill.cu:1067,1080`）。

| 条件 | unset | overlap が有効になる値の例 | overlap が無効になる値の例 |
|---|---|---|---|
| split prefill、`FNX_PF_RING_SM` が 0（CUDA / HIP） | `1`（有効） | `1`, `-1`, `+2` | `0`, `+0`, `-0` |
| `FNX_PF_RING_SM` が非 0（CUDA / HIP） | overlap は無効 | なし（値にかかわらず `p->overlap` は false） | なし |

`true` / `false`、空文字、` 1`、`1 `、`0anything` は不正な整数として失敗する。helper は文字列全体を検査するため、先頭だけ読んで残りを無視することはない。無効文字列を受けた場合、helper は `FNX_PF_OVERLAP: '<値>' is not a whole number` という `std::runtime_error` を投げる（`engine/src/split/src/env.hpp:15-21,33-39`）。

## 有効になる条件

- split engine の prompt prefill が初期化されること。`FNX_PF_OVERLAP` は Engine 構築時の `prefill_alloc()` 内で読む。通常の `--prefill` やモデル生成中に毎回読む設定ではない（`engine/src/split/src/engine.cu:318`、`engine/src/split/src/prefill.cu:854-857,1063-1089`）。
- `FNX_PF_RING_SM` が 0 であること。同変数が非 0 の場合は GPU-thread ring 用の経路を選び、`p->overlap` は強制的に false となる（`engine/src/split/src/prefill.cu:967-974,1080-1088`）。
- CUDA / HIP 共通で `p->overlap` は判定されるが、hyper-connection split（HCSplit）は CUDA build のみ。HCSplit の候補化には `NCARD == 2`、`FNX_PF_RING_SM=0`、`FNX_PF_OVERLAP != 0`、`FNX_PF_HCSPLIT != 0` が必要（`engine/src/split/src/prefill.cu:1063-1069`）。実際の HCSplit も2カードかつ overlap 有効で、`FNX_PF_HCSPLIT` の mode が非 0 の場合に限る（`engine/src/split/src/prefill.cu:1090-1094`）。
- HCSplit の候補化が真なら、明示的な `FNX_PF_PASS` がない場合の pass 既定値は4 chunksになる（ExpertCache slots がある場合も4）。それ以外の既定値は2 chunks。明示した `FNX_PF_PASS` はこの候補に優先し、1〜`PF_PASS` 以外は別の設定エラーになる（`engine/src/split/src/prefill.cu:1063-1079`）。
- HCSplit の使用にはさらに、全カードで calibration が利用可能であることと、prefill pass が既定の最小 chunk 数（3）を満たし、各 chunk が512行以上であることなどが必要。満たさない場合は chunk 単位の HCSplit が実行されない（`engine/src/split/src/prefill.cu:1149-1159,1436-1444`）。

`FNX_PF_OVERLAP` 自体に対応する CLI 引数や他の優先設定はない。コードで確認できる相互作用は `FNX_PF_RING_SM`、CUDA の `FNX_PF_HCSPLIT`、および `FNX_PF_PASS` による pass 数選択である。

## 実行時の詳細

初期化では `FNX_PF_OVERLAP` を読む箇所が二つある。CUDA build の2カード HCSplit 候補判定で一度読み、続いて各カードの `p->overlap` 設定でも読み直す。各カードの値は同一プロセスの環境値から読むが、関数内 static cache ではない。実際には初期化処理中に読み切るため、Engine 初期化後の環境変更は既存 `Pf` の設定に反映されない（`engine/src/split/src/prefill.cu:1063-1080`）。

有効時は `ring_st` と ring 完了イベントを作成する。各 half の出力ができると `ring_async` が出力準備イベントを記録し、`ring_st` で待ってから `pf_ring()` を投入し、完了イベントを記録する。attention half の sum 完了を FFN 側が待つ経路や、FFN half の sum 完了を次の chunk 側が待つ経路もこのイベントを使う。コードコメント上も、一つの pass の次 chunk が計算している間に ring sum を進める構成である（`engine/src/split/src/prefill.cu:398-402,1515-1525,1630-1634,1694-1699,1703-1707,1762-1769`）。

無効時は overlap 用 stream / event を作らず、各 half の `pf_ring()` を通常 stream 上で呼ぶ。attention prefill merge も overlap 時の遅延 merge 経路を使わず同期的な `pf_attention()` 経路にする（`engine/src/split/src/prefill.cu:1080-1088,1684-1689,1694-1699,1762-1769`）。この設定が切り替えるのは prefill の実行スケジュールであり、ソース上に token 選択や生成設定を直接変える処理はない。

## ログと測定値

この変数の値や overlap の ON/OFF を直接表示するログはない。CUDA で HCSplit が候補になったものの全カードで calibration が成立しない場合は `fnx: prompt path: the hyper-connection read stays on both cards (no cublasLt algorithm that gives the same rows at 2048 and 4096 rows on this card)`、全カードで成立した場合は `fnx: prompt path: the hyper-connection read is split between the cards (...)` を stderr に出す。これは HCSplit の状態を示すログで、overlap 単独の状態表示ではない（`engine/src/split/src/prefill.cu:1149-1159`）。

整数でない値は例外になり、`fnx_run` の例外処理経路では stderr に `fnx_run: <例外文>` と表示して終了コード1を返す（`engine/src/split/src/env.hpp:33-39`、`engine/src/split/tools/fnx_run.cpp:1370-1372`）。ここで確認した `docs/DETAILS.md` には `FNX_PF_OVERLAP` の説明や同変数の測定値は見当たらないため、性能差は記載しない。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数の全体 parse、未設定時の fallback、不正値の例外。
- `engine/src/split/src/engine.cu:318` — Engine 初期化からの `prefill_alloc()` 呼び出し。
- `engine/src/split/src/prefill.cu:967-974,1063-1094` — ring mode、HCSplit 候補・pass の既定値、overlap 設定と stream / event 作成。
- `engine/src/split/src/prefill.cu:1149-1159,1436-1444` — HCSplit calibration の全カード判定、ログ、および実行条件。
- `engine/src/split/src/prefill.cu:1515-1525,1630-1634,1684-1689,1694-1707,1762-1769` — ring の非同期投入と通常 stream 経路、chunk 間の待ち合わせ。
- `engine/src/split/tools/fnx_run.cpp:1370-1372` — `fnx_run` の例外表示と終了経路。
