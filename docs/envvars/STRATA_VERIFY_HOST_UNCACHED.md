# `STRATA_VERIFY_HOST_UNCACHED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier の verify window 用 mapped staging buffer を uncached host allocation 経由にするかを選ぶ。さらに stepped verify の segmented capture では、window の payload publish を通常 store に強制するかにも使われる。`STRATA_VERIFY_STEPPED` が無効なら、この変数の値にかかわらず uncached 側が選ばれるため、主に stepped verify の A/B 用設定である（`engine/sycl/src/core/verify.cpp:194,315-318,328-330,2051-2057`）。

## 値と判定

`env_on(name)` は `std::getenv` の結果が null でなく、先頭文字が NUL（空文字）でも `'0'` でもない場合に true とする。文字列全体や数値は parse しない（`engine/sycl/src/core/verify.cpp:151-154`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_VERIFY_STEPPED` が有効 | `window_host_uncached()` は true | 空文字以外で先頭が `0` 以外でも、結果は常に true | 同左 |
| stepped verify が有効 | false（通常の stepped 経路では uncached を外す） | `1`, `true`, `yes`, `2`, ` 1`（先頭が `0` 以外） | 空文字、`0`, `0anything` |

大文字小文字、後続文字、数値としての妥当性は検査しない。設定値は `window_host_uncached()` 内の関数ローカル `static` に初回評価時に保存される。実行中に環境を変更しても値は更新されない。なお `g_stepped` 自体も初期化時に `STRATA_VERIFY_STEPPED` を同じ helper で一度読み取る（`engine/sycl/src/core/verify.cpp:151-154,194,315-317`）。

## 有効になる条件

- 対象の読み取りと効果は `engine/sycl` の verifier 実装にある。CUDA/HIP の verifier 経路がこの名前を読む箇所はない（同ファイル `:315-318`）。
- `STRATA_VERIFY_STEPPED` が無効なら本変数では切り替えられず、`window_host_uncached()` は true を返す。
- stepped verify で false になった場合、staging buffer は `sycl::malloc_host` に進み、segmented capture の payload に通常 store を強制する（`engine/sycl/src/core/verify.cpp:315-318,328-330,2051-2057`）。
- `STRATA_VERIFY_STEPPED` が有効でこの変数も有効でも、実際に uncached host allocation を得られるかは `strata::host_malloc_polled` の条件次第。ビルドに Level Zero headers があり (`STRATA_HAVE_ZE`)、queue backend が Level Zero で、かつ `STRATA_HOST_UNCACHED` が先頭 `0` でないときに Level Zero host allocation を試す。それ以外や allocation が失敗した場合は `sycl::malloc_host` に fallback する（`engine/sycl/include/strata/sycl_queue.hpp:64-78`）。従ってこの変数単独では uncached allocation を保証しない。
- segmented capture 内の payload store 切替は `g_stepped && !ar_on() && STRATA_VERIFY_EAGER 未設定` の経路に限られる。`STRATA_VERIFY_EAGER` が設定されている場合は segmented capture に入らない（値が空でも「設定あり」）ため、この変数による PlainPayload guard は適用されない（`engine/sycl/src/core/verify.cpp:2098-2105`）。
- `STRATA_DOORBELL_PLAIN` は publish の plain/atomic store 選択に別途作用する。guard が通常 store を強制しなくても、この別設定または既定判定が plain store を選ぶ場合がある（`engine/sycl/include/strata/sycl_doorbell.hpp:101-113`, `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:638-645,745-750`）。

## 実行時の詳細

`window_host_uncached()` の static 値を `mapped()` が参照し、verify window の token、flag、plan、payload などの mapped staging を `strata::host_malloc_polled` または `sycl::malloc_host` で確保する。成功時はゼロ初期化し、同じ host pointer を device 側 pointer に設定する。主要 staging の確保失敗は `verify: mapped staging allocation failed`、plan buffer は `verify: mapped plan allocation failed` として caller に返る（`engine/sycl/src/core/verify.cpp:320-332,691-730`）。

stepped の segmented capture では RAII guard が window 中 `doorbell_plain_payload(!window_host_uncached())` を設定し、終了時に false に戻す。従って変数が有効ならこの guard は通常 store を強制せず、無効なら通常 store を選ぶ。doorbell publish はこの状態と `STRATA_DOORBELL_PLAIN` の設定を参照する。payload store の選択は verify の token 選択・受理条件を変更する設定としては実装されていない（`engine/sycl/src/core/verify.cpp:2051-2057`, `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:638-645,745-750`）。

## ログと測定値

この変数自体について値や分岐を表示するログはない。関連する SYCL allocation exception は `exc.what()` と `Exception caught at file:...` を stderr に出して `exit(1)` する経路がある（`engine/sycl/src/core/verify.cpp:334-337`）。

実装コメントには Arc A770、xe、Coder IQ1_M、8K prompt の条件で、uncached の有無による GPU wait と decode throughput の値が記載されている（`engine/sycl/src/core/verify.cpp:309-314`）。測定回数、詳細な実行環境や測定方法はそのコメントにないため、再現性や他機種への一般化は確認できない。`docs/DETAILS.md` にこの変数の説明は見当たらず、同文書にある別の I/O uncached 機能とは別の実装である。

## 根拠

- `engine/sycl/src/core/verify.cpp:151-154,188-194` — flag 判定 helper と stepped mode の読み取り。
- `engine/sycl/src/core/verify.cpp:309-318,320-337` — 既定条件、対象 allocation、allocation 失敗時の処理。
- `engine/sycl/src/core/verify.cpp:691-730,2051-2057,2098-2105` — mapped buffer の利用、payload guard、segmented capture 条件。
- `engine/sycl/include/strata/sycl_queue.hpp:64-78` — uncached host allocation の build/backend/別環境変数条件と fallback。
- `engine/sycl/include/strata/sycl_doorbell.hpp:101-113`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:638-645,745-750` — payload store 選択。
