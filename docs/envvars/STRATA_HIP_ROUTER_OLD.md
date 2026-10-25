# `STRATA_HIP_ROUTER_OLD`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

wave32 AMD HIP backend の MoE router (`router_top10`) で、既定の fast kernel を使わず、従来の portable kernel を選ぶための切り替えです。fast kernel は softmax の指数和の一部を並列化し、選択を wave 0 上で行います。portable kernel は block 内の並列処理と選択ごとの block barrier を使います。ソースコメントと `docs/AMD_HIP.md` は、fast kernel が同じ expert ID と weight を bit 単位で返すこと、および `STRATA_HIP_ROUTER_OLD=1` で portable kernel を実行することを説明しています。

## 値と判定

この変数の値は parse されず、`std::getenv("STRATA_HIP_ROUTER_OLD") != nullptr` だけで判定されます（`src/kernels/cuda/router_top10.cu:430-434`）。

| 状態 | wave32 HIP backend での判定 |
|---|---|
| 未設定 | `old == false`。fast kernel を使える入力形状では fast kernel を選ぶ |
| 空文字を含む何らかの値が設定済み | `old == true`。portable kernel を選ぶ |

したがって `0` や `false` も設定されていれば portable kernel になります。設定値を数値・真偽値として解釈したり、大文字小文字を比較したりはしません。判定は `router_top10()` 内の関数ローカル `static const bool` に保存されるため、最初の同関数呼び出し時に評価され、その後プロセス内で環境を書き換えても再評価されません。

## 有効になる条件

- この分岐は `__HIPCC__` が定義されたビルドにだけ含まれます。Strata の CMake では `STRATA_ENABLE_HIP` が wave32 AMD backend（gfx1100/gfx1201 等）を選び、`src/kernels/cuda/router_top10.cu` を `strata_kernels` に含めます（`CMakeLists.txt:71-72,344-353`）。CUDA build ではこの環境変数を読む分岐はコンパイルされません。
- `STRATA_HIP_GFX906` の gfx906/wave64 compat build では別分岐になり、この変数は参照されません。同 backend は `STRATA_HIP_ROUTER_FAST` の未設定有無で選択します（`src/kernels/cuda/router_top10.cu:426-432`）。
- wave32 HIP で変数が未設定でも、fast kernel が使われるのは `n_tokens > 0`, `65 <= n_expert <= 512`, `1 <= k <= 32` の入力に限られます。それ以外は通常の入力検査後に portable `router_top10_kernel` へ進みます（同 `:433-434,451-482`）。
- MoE 経路が `router_top10()` を呼び出した場合に適用されます。例えば layer の通常 router は、native 512 expert × top-10 router を使わない場合にこの関数へ進みます（`src/core/layer.cpp:371-376`）。native router を選ぶ経路はこの切り替えの対象外です。

## 実行時の詳細

fast kernel が選ばれると `launch_generic(..., mode=1)` が `router_top10_fast_kernel<false>` を起動します。環境変数が存在する場合、または fast kernel の対象形状に合わない場合は、通常の portable kernel 起動へ進みます。fast kernel 起動後の `cudaGetLastError()` が失敗すると `router_top10 launch: ...` を stderr に出し、プロセスを終了します。デフォルト stream (`stream == nullptr`) では同期も行い、失敗時は `router_top10: ...` を stderr に出して終了します。環境変数による portable 選択自体はログを出しません（同 `:385-403,433-449,481-494`）。

portable kernel は expert 全体の softmax 用 exponentials を計算し、top-k を選び、選択 weight の和を `2**-14` で下限 clamp して再正規化します。fast kernel も同じ router の出力意味を保つ実装として記述されています（同 `:7-17,87-187,266-383`）。

`docs/AMD_HIP.md` は、対象機材で fast router が portable kernel と同じ IDs/weights を返した検証、および測定時の速度を記載しています。そこでの計測は R9700 / RX 9070 XT と Coder IQ1_M pack 等の条件付きであり、一般的な性能保証ではありません（`docs/AMD_HIP.md:330-336`）。

## 根拠

- 環境変数の有無による選択、fast path の入力範囲、fallback、エラー処理: `src/kernels/cuda/router_top10.cu:422-495`
- portable kernel の router 計算: `src/kernels/cuda/router_top10.cu:69-187`
- fast kernel の実装と portable kernel との同一性に関するソース注釈: `src/kernels/cuda/router_top10.cu:266-383`
- HIP backend の説明と portable kernel への切り替え記述: `docs/AMD_HIP.md:330-336`
- backend option と router source の build 登録: `CMakeLists.txt:71-72,344-353`
- 通常 layer router からの呼び出し条件: `src/core/layer.cpp:371-376`
