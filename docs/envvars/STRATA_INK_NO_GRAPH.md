# `STRATA_INK_NO_GRAPH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 の CUDA backend で、通常の forward・tree verify・batched forward、および DSpark drafter が使う CUDA Graph を初期状態から無効にし、同じ処理の eager kernel launch 経路を選ばせる診断用スイッチです。グラフを有効にする設定ではありません。CUDA backend 初期化時に `InkCudaBackend::init` が `InkCudaRunner::use_cuda_graph` を決め、その後 `InkCudaRunner` と DSpark がこのフラグを参照します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:303-310`、`engine/src/inkling2/cuda/ink_runner.cuh:1910-1915`、`engine/src/inkling2/cuda/ink_dspark.cuh:1651-1689`）。

この環境変数を読むのは CUDA backend のみです。`make_default_backend` は `INKLING_ENABLE_CUDA` ビルドで CPU 強制指定がないときに CUDA backend を選び、HIP / Metal / SYCL / CPU の経路ではこの名前を読みません（`engine/src/inkling2/ink_backend.h:198-215`）。

## 値と判定

`std::getenv` の戻り値が非 null で、かつ値の**先頭 1 文字**が `'1'` の場合だけ有効です。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしません。未設定・空文字・先頭が `'1'` 以外なら、この変数による変更はありません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:305-310`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA Inkling backend で、CUDA Graph が初期状態で有効 | Graph は既定のまま有効 | `1`, `1abc`, `10`（先頭が `1`） | 空文字、`0`, `0anything`, `true`, ` 1` |
| CUDA Inkling backend で、CUDA Graph が初期状態で無効 | Graph は無効のまま | この変数だけでは追加の変化なし。先頭 `1` でも分岐に入らない | unset / 空文字 / 先頭が `1` 以外も変化なし |
| CPU・HIP・Metal・SYCL backend | この名前を読む実装なし | 該当なし | 該当なし |

無効な文字列に対するエラーや fallback はありません。先頭が `'1'` かどうかだけで判定します（同上）。

## 有効になる条件

- `INKLING_ENABLE_CUDA` を含むビルドで、実行時に CPU を強制せず Inkling CUDA backend を使用すること。CPU を強制した場合や別 backend の場合、このコードには読み取りがありません（`engine/src/inkling2/ink_backend.h:198-215`）。
- CUDA backend が Graph を初期状態で有効にすること。初期値は `vf_graph_ok && !model_.ep2_active && !model_.ls_active` です。Volta-forever が有効な sm_70 では `vf_graph_ok` が偽となり、また EP2 または layer-split が active なら Graph はこの時点ですでに無効なので、この環境変数は追加ログも出しません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:266-270,303-310`、`engine/include/strata/core/volta_forever.hpp:96-104`）。
- `STRATA_INK_PROF` が先頭 `'1'` または `'2'` の値なら、直後の処理も Graph を無効にします。NO_GRAPH が Graph を無効化した場合は両方の診断ログが出ます（Graph が初期有効である場合）。NO_GRAPH が unset/無効値でも PROF の処理は独立して働きます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:306-319`）。
- 値が有効でも、個々の forward 呼び出しには Graph 経路の追加条件があります。単一 forward は `M == 1`、slot 0、画像ステップなし、pass override なし、hybrid の eager 要求なし等、tree は slot 0・tree 上限内・host expert なし等、batched は batch 64 以下かつ host expert 条件等を満たすときだけ Graph を使います。条件外はもともと eager 経路です（`engine/src/inkling2/cuda/ink_runner.cuh:3663-3695,3783-3814,3834-3864`）。
- DSpark は `opts.enable_dspark` が真で、モデル manifest に DSpark drafter があり、layer-split でない場合に初期化されます。Runner の Graph フラグが false なら DSpark の draft graph capture も使わず、`emit_draft_block8` / `emit_draft_beam_tree` を直接呼びます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352`、`engine/src/inkling2/cuda/ink_dspark.cuh:1651-1689,1696-1735`）。

## 実行時の詳細

変数は `InkCudaBackend::init` が `runner_` を作り直すたびに評価されます。値を Runner に保存した後、各処理が `use_cuda_graph` を参照します。初期化後にプロセス環境を変更しても、その Runner には再評価されません。Runner は capture 成功後の graph exec を `graph_cache` に保持します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:303-310`、`engine/src/inkling2/cuda/ink_runner.cuh:1902-1912,3663-3689`）。

先頭文字が `'1'` で、かつ初期 Graph が有効なら `use_cuda_graph` を false にし、次を stderr に出します。

```text
[InkCUDA] STRATA_INK_NO_GRAPH=1: CUDA Graph capture off (eager launches)
```

以後、Graph 利用条件を満たす処理も `emit_48_visits` などの eager launch 経路を通ります。処理の演算列そのものをこの変数で変える分岐は見つかりませんでした（`engine/src/inkling2/cuda/ink_cuda_backend.cu:306-310`、`engine/src/inkling2/cuda/ink_runner.cuh:3663-3695,3783-3814,3834-3864`）。

CUDA Graph capture が別の理由で失敗した場合、通常・tree・batched forward はそれぞれ capture unavailable の stderr ログを出し、該当処理を eager 実行します。通常 forward の失敗は `use_cuda_graph` も false にして以後の capture を止めます（`engine/src/inkling2/cuda/ink_runner.cuh:3678-3684,3798-3804,3849-3855`）。これらは環境変数の無効値による失敗ではありません。

## ログと測定値

- NO_GRAPH のログは、値の先頭が `'1'` で、かつ `runner_->use_cuda_graph` が直前に true のときに限って stderr に出ます。unset・空文字・他の先頭文字、および CUDA Graph が元から無効な場合はこのログを出しません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:305-310`）。
- `STRATA_INK_PROF` が有効なら `[InkCUDA] STRATA_INK_PROF=1: eager launches, per-phase timing (runner phases every 50 batched steps, host phases every 32)` も出ます。`STRATA_INK_PROF=2` でも実装のログ文字列は `=1` です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:311-319`）。
- この変数単独での性能値や測定結果は、対象コード・関連する `docs/DETAILS.md` に記載がありません。性能差や出力同一性の測定値はここでは示しません。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:266-270,303-319,343-352` — Graph の初期条件、環境変数の読み取り、PROF による後続上書き、DSpark 初期化。
- `engine/src/inkling2/ink_backend.h:198-215` — ビルド backend と CPU 強制時の選択。
- `engine/include/strata/core/volta_forever.hpp:96-104` — sm_70 / Volta-forever 条件。
- `engine/src/inkling2/cuda/ink_runner.cuh:1902-1915,2363-2365,2437-2439,3663-3695,3783-3814,3834-3864` — Graph 状態、layer-split / EP2 無効化、実行時の適用条件と fallback。
- `engine/src/inkling2/cuda/ink_dspark.cuh:1651-1689,1696-1735` — DSpark の Graph / eager 分岐。
