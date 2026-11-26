# `STRATA_TOPK_OLD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

QSA の block top-k 選択で、最適化された dispatch を通さず、参照実装 `qsa_block_topk_ref` を使わせる切り替えです。CUDA/HIP 実装と SYCL 移植実装の `qsa_block_topk` がこの変数を読み、設定されている場合は参照カーネルへ分岐します。API のコメントでは、参照カーネルは元の 256-thread 実装で、選択 ID は通常経路と同じとされています（`engine/src/kernels/cuda/qsa_select.cu:2449-2459`、`engine/include/strata/kernels/qsa_select.hpp:92-95`）。

設定時に変わるのは top-k の実装経路です。CUDA では cluster および split 経路も抑止され、CUDA の実験的 long-context verifier 経路では multi-CTA top-k を選ばず通常の `qsa_block_topk` に戻ります（`engine/src/kernels/cuda/qsa_select.cu:3020-3039,3230-3245`）。HIP には cluster / split 分岐がなく、SYCL 実装にも split 分岐はありませんが、いずれも通常の top-k 関数内で参照実装へ分岐します（`engine/src/kernels/cuda/qsa_select.cu:3060-3076`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2026,2046-2056`）。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` で設定有無だけを判定します。したがって値が空でも設定扱いになり、`0` や `false` も参照経路を有効にします。大文字小文字、空白、数値としての妥当性の検査はありません（`engine/src/kernels/cuda/qsa_select.cu:3020`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2016`、CUDA の long wrapper は `engine/src/kernels/cuda/qsa_select.cu:3234`）。

| 実装経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP `qsa_block_topk`、SYCL `qsa_block_topk` | `old=false`。条件に応じて最適化経路を選ぶ | `1`、`0`、`false`、空文字、任意の文字列。値の有無で `old=true` | なし。設定値の内容による無効値はない |
| CUDA `qsa_block_topk_long`（`STRATA_EXPERIMENTAL_SM60` ビルド） | 条件が合えば multi-CTA 経路を検討 | 上と同じ。設定ありなら multi-CTA 経路を迂回 | なし |

## 有効になる条件

- CUDA/HIP の `engine/src/kernels/cuda/qsa_select.cu` または Intel GPU 向け SYCL の `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp` にある QSA top-k 実装がビルドされ、その `qsa_block_topk` が呼ばれること。たとえば CUDA の QSA layer は fast-select 経路で block score 計算の後に呼び出します（`engine/src/core/layer.cpp:1273-1282`）。通常の QSA 選択を通らない処理には影響しません。
- CUDA の verifier long-context 経路で multi-CTA 版を抑止する効果は、`STRATA_EXPERIMENTAL_SM60` が定義された CUDA ビルドで `qsa_block_topk_long` が呼ばれる場合に限ります。同関数は `old` が false で、scratch・query 数・active count・geometry・capacity 条件を満たす場合だけ multi-CTA 版を試します（`engine/src/kernels/cuda/qsa_select.cu:3230-3245`）。
- 他の環境変数や CLI 引数が `STRATA_TOPK_OLD` の値を上書きする処理はありません。設定時は cluster / split / long multi-CTA の選択を抑止し、通常の関数内で参照カーネルへ進みます。未設定時に使われる最適化経路は、backend、GPU と入力形状など各 dispatch 条件に依存します（`engine/src/kernels/cuda/qsa_select.cu:3022-3076,3232-3245`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2018-2056`）。

## 実行時の詳細

判定は関数内 `static const bool` です。CUDA/HIP と SYCL の `qsa_block_topk` はそれぞれ最初の呼び出し時に一度読み、以後はその値を使います。プロセス実行中に環境を変更しても反映されません。CUDA の実験的 long wrapper にも別の `static` 判定があるため、そこでは同 wrapper の初回呼び出し時に独立して読みます（`engine/src/kernels/cuda/qsa_select.cu:3016-3021,3230-3235`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2017`）。

通常の `qsa_block_topk` では、CUDA は `old` が true だと cluster と split 分岐を飛ばし、HIP/CUDA 共通の後段で `qsa_block_topk_ref` を呼んで戻ります。SYCL でも cluster を試さず、同関数内の後段から参照実装に進みます。参照実装の ID 出力はその後の QSA KV 解決や attention に渡されます（`engine/src/kernels/cuda/qsa_select.cu:3029-3039,3069-3076`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2025-2026,2046-2056`、`engine/src/core/layer.cpp:1284-1290`）。

CUDA の `qsa_block_topk_long` はこの変数が設定されると multi-CTA 経路の条件を満たさず、通常の `qsa_block_topk` に委譲します。委譲先には別の関数-local cache があります（`engine/src/kernels/cuda/qsa_select.cu:3232-3245`）。

## ログと測定値

この変数を検出したこと自体を知らせるログはありません。CUDA/HIP の参照実装も geometry または capacity が未対応なら `qsa_block_topk: unsupported geometry or cap` を stderr に出して `exit(1)` し、kernel launch error の場合も `qsa_block_topk: <CUDA error>` を出して `exit(1)` します（`engine/src/kernels/cuda/qsa_select.cu:2449-2459`）。通常実装側にも同じ geometry エラー文言と launch error 終了経路があります（`engine/src/kernels/cuda/qsa_select.cu:3078-3080,3104-3105`）。この調査では build や実行をしておらず、性能値は測定していません。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:3016-3105` — CUDA/HIP の環境判定、dispatch 条件、参照実装への分岐とエラー経路。
- `engine/src/kernels/cuda/qsa_select.cu:2449-2459` — 参照実装の geometry 検査、kernel launch とエラー経路。
- `engine/src/kernels/cuda/qsa_select.cu:3230-3245` — CUDA 実験的 long-context wrapper の別 cache と multi-CTA 抑止。
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2059` — SYCL 実装の環境判定、dispatch と参照実装への分岐。
- `engine/include/strata/kernels/qsa_select.hpp:92-101` — 参照実装と long-context API の説明。
- `engine/src/core/layer.cpp:1273-1290` — QSA fast-select の呼び出しと選択 ID の後続処理。
- `engine/src/core/verify.cpp:2266-2276` — verifier の通常 / long-context top-k 呼び出し。
