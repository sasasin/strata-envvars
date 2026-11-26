# `STRATA_VERIFY_QDEDUP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

Verifier の native expert 経路で、同じ入力 `xm` の q8_1 量子化結果を shared expert と通常 expert が共有するための opt-in 設定。通常は shared expert が q8_1 を作り、native expert 側も後段で q8_1 を作る。設定が有効で条件を満たすと、shared expert より前に `xm` を `nat_xq_` へ量子化し、そのポインターを shared expert に渡す。shared expert は渡された画像を gate/up の計算に使い、後続の通常 expert は同じ `nat_xq_` を読む。これにより重複する入力量子化を避ける。CUDA/HIP 共通実装と SYCL 実装に同じ制御がある。[`engine/src/core/verify.cpp:190,2723-2750,2801-2824`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:133,1645-1671,1723-1753`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)、[`engine/src/kernels/cuda/shared_expert.cu:216-228`](../../../../Niko1221/Strata/engine/src/kernels/cuda/shared_expert.cu)

## 値と判定

両 verifier の `g_qdedup()` が初回呼び出し時に `std::getenv` で値を読み、`v != nullptr && std::atoi(v) != 0` を関数内 `static` に保存する。未設定は無効。空文字も `atoi` が 0 を返すため無効。文字列全体の妥当性検査や clamp はない。`atoi` が先頭の空白と符号付き十進数を変換し、数値でない先頭や 0 から始まる値は 0、非ゼロの整数で始まる値は有効となる（例: `1tail` は有効、`0tail` は無効）。したがって `true` は無効、`-1` は有効。範囲外の整数文字列に対する `atoi` の結果はこの実装で定義・検査されない。[`engine/src/core/verify.cpp:190`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:133`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)

| 実装 | unset | 有効例 | 無効例 |
|---|---|---|---|
| CUDA/HIP verifier、SYCL verifier | 無効 | `1`, `-1`, ` 2`, `1tail` | 空文字, `0`, `0tail`, `true` |

## 有効になる条件

- verifier の共有 expert 処理に到達し、`g_qdedup()` が有効であること。環境変数は `g_qdedup()` の初回評価後に変更しても反映されない。[`engine/src/core/verify.cpp:190,2723-2750`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:133,1645-1671`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)
- `sh_fork` が false であること。shared expert を別 stream/queue に fork する場合は、別バッファを使うためこの共有量子化を無効にする。[`engine/src/core/verify.cpp:2621-2624,2740`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:1567-1573,1661`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)
- `strata::kernels::cpu::expert_layout().native` が true であること。native でない expert layout は別の量子化形式を使い、q8_1 の共有分岐には入らない。[`engine/src/core/verify.cpp:2740,2761-2774,2808-2824`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:1661,1679-1692,1727-1754`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)
- shared expert の native weight と scratch 等が揃って `shared_expert_multi` の呼び出しが成立すること。`STRATA_QFUSE` 等の CLI 優先順位はなく、ただし FFN 入力画像がすでに利用可能な場合は追加の量子化呼び出しを省く。[`engine/src/core/verify.cpp:2735-2749`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:1657-1671`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)

## 実行時の詳細

1. FFN の gated residual read が `q8_ffn` を返す。QFUSE がその読み取り中に q8_1 画像を書いた場合は true となる。[`engine/src/core/verify.cpp:1796-1818,2613`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:1209-1229,1560`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)
2. shared expert 入力の準備時に `qdedup = g_qdedup() && !sh_fork && expert_layout().native` と判定する。有効で `q8_ffn` が false のときは `quantize_q8_1_rows(xm, ...)` で `nat_xq_` を先に作る。`q8_ffn` が true なら既存画像を使うため、この追加書き込みはしない。[`engine/src/core/verify.cpp:2735-2741`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:1653-1662`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)
3. `qdedup` が true なら `nat_xq_` のポインターを `shared_expert_multi` の `x_q8_1_ready` 引数へ渡す。関数はこの引数が非 null ならそれを選び、入力を改めて量子化しない。false なら null が渡り、関数は `nw.x_q8_1` を使い、それも null なら `native_quantize_q8_1` を行う。[`engine/src/core/verify.cpp:2747-2750`](../../../../Niko1221/Strata/engine/src/kernels/cuda/shared_expert.cu:216-228)、[`engine/sycl/src/core/verify.cpp:1668-1671`](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:315-326)
4. native expert の後続 grouped 計算も同じ `nat_xq_` を受け取る。folded gate/up 層では shared expert が読んだ後に回転後の入力から画像を作り直す。QFUSE 既存画像とこの変数で先行作成した画像はいずれも unrotated 入力なので、folded 層では上書きが必要になる。[`engine/src/core/verify.cpp:2761-2772,2808-2824`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/sycl/src/core/verify.cpp:1679-1690,1727-1750`](../../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp)

この変数専用のログはない。共有 expert 内の引数検査や呼び出しが例外を投げると verifier は `verify shared expert: ` に例外内容を付けてエラーを返すが、その経路はこの変数固有ではない。[`engine/src/core/verify.cpp:2747-2754`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/src/kernels/cuda/shared_expert.cu:220-221`](../../../../Niko1221/Strata/engine/src/kernels/cuda/shared_expert.cu)

## ログと測定値

対象変数が有効化されたことを示す専用ログ・終了コード・失敗経路はない。ソースコメントには同一 q8_1 バイトを共有する説明があるが、性能測定値は示されていない。[`engine/src/core/verify.cpp:2737-2741`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

## 根拠

- `engine/src/core/verify.cpp:190,2613-2624,2723-2774,2801-2824` — CUDA/HIP verifier の読み取り、fork 条件、量子化画像の共有と expert 側の使用。
- `engine/sycl/src/core/verify.cpp:133,1560-1573,1645-1692,1723-1754` — SYCL verifier の同等処理。
- `engine/src/kernels/cuda/shared_expert.cu:216-228`、`engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:315-326` — ready 画像を優先し、未提供なら内部量子化する shared expert。
