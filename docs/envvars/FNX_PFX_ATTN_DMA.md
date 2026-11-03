# `FNX_PFX_ATTN_DMA`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`sFNX` の split prompt attention で、他カードから受信した attention partial を、マップされたホスト受信バッファから merge kernel が直接読む代わりに、copy engine で device memory へ移してから merge するかを選びます。Strata 側の読み取りは `src/split/src/prefill.cu` にあり、一般の Strata decode 経路や外部ライブラリが読む設定ではありません。

## 値と判定

`fnx::env_int` が値全体を 10 進の `long long` として読み、結果が `0` 以外なら ON とします。符号付き整数を受け付け、数値の後ろの文字・空白は許容しません。`long long` の範囲外、空文字、数字以外、末尾に余分な文字がある値は whole number として不正です。値域の clamp はありません。

| ビルド | 未設定 | 設定値 |
| --- | --- | --- |
| HIP (`FNX_HIP`) | `0`（OFF） | whole number が `0` 以外なら ON。`0`, `+0`, `-0` は OFF |
| 非 HIP（CUDA） | `1`（ON） | whole number が `0` 以外なら ON。`0`, `+0`, `-0` は OFF |

不正値は `env_int` が `std::runtime_error`（`FNX_PFX_ATTN_DMA: '<値>' is not a whole number`）を送出します。たとえば空文字や `1x` は ON/OFF に丸めずエラーになります。整数として正しい任意の非ゼロ値（負値を含む）は ON です。

根拠: `src/split/src/env.hpp:15-21,33-40`、`src/split/src/prefill.cu:789-795`。

## 有効になる条件

- sFNX split build の `Engine::prefill_alloc()` が各カード用の prompt 状態を初期化するときに評価されます。split の対応カード数は 2 以上で、attention exchange は他カードからの partial を受け取る構成です。
- HIP build は明示的な非ゼロ値が必要です。CUDA build は既定で ON です。CLI 引数や別環境変数による上書きは、この設定の読み取り箇所にはありません。
- 設定値が ON なら `arecv_dev` の領域、各 parity 用の受信・merge event、`st3` の nonblocking stream を確保します。OFF ならそれらを確保せず、後述の従来経路で merge します。
- `FNX_PF_DMA` は別の ring receive/gather 用設定です。この attention partial 経路の `attn_dma` 判定と混同されず、それぞれ別のフィールドとして設定されます。

根拠: `src/split/src/card_split.hpp:8-13`、`src/split/src/engine.cu:274-275`、`src/split/src/prefill.cu:625-627,789-805,891-898`。

## 実行時の詳細

設定は `prefill_alloc()` 中にカードごとの `Pf` に読み込まれ、`p->attn_dma` に保存されます。したがって既に初期化済みの `Engine` では、環境変数を後から変更してもその `Pf` の動作は切り替わりません。別の `Engine` を初期化すると、その初期化時の値を読みます。

ON の場合、attention exchange の各 piece について `st3` が対応する受信 flag を待ち、host receive buffer から `arecv_dev` へ `cudaMemcpyAsync` します。受信 copy 完了 event と送信完了 event を待ってから `attn_prompt_merge` を `arecv_dev` に対して実行し、merge 完了 event を記録します。OFF の場合は merge stream 上で全受信 flag と送信完了 event を待ち、`arecv`（host receive buffer）を入力にして merge します。

設定値自体についてのログ出力は確認できません。無効な整数は初期化中の例外になります。`fnx_run` の通常実行では `std::exception` を `stderr` に `fnx_run: <例外内容>` の形式で出し、終了コード 1 を返します。ON 経路での CUDA 操作失敗は `ckc` / `cud` を通じて処理され、`attn recv reuse`、`attn wait (dma)`、`attn recv copy` など操作箇所のラベルが渡されます。

根拠: `src/split/src/prefill.cu:541-596,789-805`、`src/split/tools/fnx_run.cpp:1365-1373`。
