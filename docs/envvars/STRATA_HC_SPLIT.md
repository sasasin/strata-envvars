# `STRATA_HC_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA fused hyper-connection の複数 token read で、plain / split / staged のどの variant までを使うか指定します。`split` は norm を token・stream 単位に分け、down projection は plain kernel を使います。`staged` は split norm に加え、down projection の activation を tile ごとに先読みします。実装コメントでは、これらの read は plain read と演算順・出力 bit を保つ設計とされています。実行時にはカードごとの自己検査が variant を許可するか判断します。

## 値と判定

`env_variant()` は文字列全体や数値を parse せず、先頭文字だけを見ます。空文字は別扱いで staged を返します。

| 値 | variant 上限 |
|---|---|
| 未設定、空文字 | staged |
| 先頭文字が `0` | plain |
| 先頭文字が `1` | split |
| それ以外（`2`、`true`、`false`、空白など） | staged |

通常の CUDA verifier 経路では、`fused_gr_check()` がこの上限までの候補を自己検査し、通過した最も新しい variant を保存します。`0` の場合は検査をせず plain を選びます。`1` なら split のみを候補にし、`2` や未設定なら staged、split の順に検査結果を見ます。不合格または検査を実行できない場合は plain へ戻ります。

検査前に `fused_gr_variant()` が呼ばれた場合の fallback は少し異なります。値の先頭が `1` または `2` の場合だけ `env_variant()` の結果を返し、それ以外（未設定、空文字、`0`、`3` など）は plain です。したがって、たとえば `3` は検査後なら staged 上限ですが、未検査時には plain になります。

## 有効になる条件

- **CUDA backend:** `src/kernels/cuda/fused_gr.cu` の複数 token read 経路で使われます。通常の fused read は `launch_multi(..., fused_gr_variant(), ...)` に variant を渡します。
- 別の `STRATA_GR_V3` 経路が条件を満たして先に使われる場合は `fused_gr_variant()` を経由しません。CUDA では Q8 projection の `launch_q8()` も variant 選択前に return します。
- `fused_gr_check()` は `Verifier::init()` から呼ばれ、variant の状態はデバイスごとの `g_variant[64]` に保存されます。記録済みなら後続の検査呼び出しは戻るため、実行中に環境値を変えてもそのカードの選択は更新されません。

SYCL port にも同名の参照がありますが、該当ファイルは生成済みコードなので、この調査の実装根拠と挙動説明には含めていません。

## 実行時の詳細

通常 CUDA verifier 経路では、各カードの verifier 初期化時に plain と split / staged の出力を自己検査し、選択結果をカードごとに保存します。split と staged の比較に失敗した場合は `strata hc: CUDA%d: the %s read differs from the plain read on this card - not used: ...` を stderr に出し、plain に fallback し得ます。検査を実行できなければ `strata hc: CUDA%d: the check of split/staged could not run (...)` を出します。選択結果も `strata hc: CUDA%d: the hyper-connection read runs as ...` の形式で表示されます。plain を明示したときは `... runs as the plain one (STRATA_HC_SPLIT=0)` が出ます。

CUDA ソースの staged kernel は sm_80 より前、および HIP では `cp.async` を使わず通常コピーにする実装コメントがあります。したがって staged 指定を、全 GPU で非同期 copy が行われる指定と解釈できません。性能値については `docs/DETAILS.md` にこの変数の記載を確認できなかったため記載していません。

## 根拠

- `src/kernels/cuda/fused_gr.cu:654,1030-1051` — variant ID と variant に応じた norm / staged down dispatch。
- `src/kernels/cuda/fused_gr.cu:1121-1128` — 値の先頭文字による variant 上限判定。
- `src/kernels/cuda/fused_gr.cu:1830-1866,1930-1962` — Q8 / `STRATA_GR_V3` の先行経路と、通常経路の variant 選択。
- `src/kernels/cuda/fused_gr.cu:2127-2169` — 未検査時の fallback、カードごとの検査、結果と診断ログ。
- `src/core/verify.cpp:540-552` — `Verifier::init()` が `fused_gr_check()` を呼ぶ。
- `include/strata/kernels/fused_gr.hpp:64-75` — variant の意図と公開 API。
