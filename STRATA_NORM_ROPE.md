# `STRATA_NORM_ROPE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP ビルドで QSA の RMSNorm と RoPE を一つの native kernel に融合する経路を opt-in で有効にします。環境変数を読むのは `native_norm_rope_usable()` です。CUDA ビルドではこの変数を読みません。CUDA は既定で同じ融合判定が有効で、止める場合は別変数 `STRATA_NO_NORM_ROPE` を使います。

この判定関数は融合 kernel の呼び出し可否に加えて、in-place の `native_rope_apply()` で使う launch 幅の選択にも使われます。したがって HIP でこの変数を有効にすると、条件を満たす幾何形状ではその launch 幅も変わります。

## 値と判定

両実装とも環境変数全体を parse せず、先頭文字を比較します。判定値 `on` は関数内の `static const bool` に保存され、プロセス中に最初に呼ばれたときだけ決まります。

| ビルド条件 | `STRATA_NORM_ROPE` の扱い | 関数の環境設定判定 |
|---|---|---|
| `__HIPCC__` が定義されたビルド | 読み取る | 設定済みで、先頭文字が NUL でも `0` でもなければ on。例: `1`, `true`, `2x`。unset、空文字、`0`, `0abc` は off |
| `__HIPCC__` が未定義のビルド | 読み取らない | off 変数による拒否がなければ on（後述） |

大文字小文字、空白、数値としての妥当性、文字列末尾は検査されません。HIP では `STRATA_NORM_ROPE=false` も先頭文字が `f` なので on です。設定後にプロセス環境を書き換えても、最初の判定結果は変わりません。

`STRATA_NO_NORM_ROPE` は両ビルドで先に評価されます。この別変数が設定済みで先頭文字が空でも `0` でもなければ、`STRATA_NORM_ROPE` の値に関係なく off になります。`STRATA_NO_NORM_ROPE=0` または空文字は拒否条件になりません。CUDA ではこれが融合を無効にする環境変数です。

根拠: `src/kernels/cuda/native_rope.cu:175-187`、同じ判定の SYCL 側実装 `sycl/src/kernels/cuda/native_rope.dp.cpp:229-241`。

## 有効になる条件

環境設定の判定が on でも、`native_norm_rope_usable(head_dim, n_rot)` が true を返すのは `head_dim` が 128 または 256 で、`n_rot == 64` の場合だけです。これ以外の寸法では環境変数を有効にしても fused kernel は選ばれません。

QSA verify 経路ではさらに `native_qsa_enabled()` と `native_rope_enabled()` の両方が必要です。MTP drafter の Q/K 経路では `native_rope_enabled()` が必要で、K の融合は `T == 1` のときだけです。条件を満たさない場合、verify は個別の RMSNorm と RoPE に進み、MTP の K 経路も個別処理に進みます。

## 実行時の詳細

融合対象の処理は per-head RMSNorm と RoPE を一つの kernel launch で実行します。verify の QSA 経路では、Q と K の正規化・回転で `norm_rope()` が判定し、MTP drafter では Q、単一 token 時の K が fused kernel を呼びます。引数検査に失敗した場合、kernel 関数は `std::invalid_argument` を投げます。判定関数自体はログを出しません。

別の影響として、`native_rope_apply()` は in-place 入力で `native_norm_rope_usable()` が true のとき launch 幅を 32 thread にし、それ以外は 128 thread にします。ここでも寸法と回転数の制限が適用されます。

HIP ビルドで既定 off になっている設計背景は AMD parity check が通るまで融合を opt-in にすることです。`rope_parity` はこの関数で check 6 を skip するか実行するかを決めます。ソースコメントには gfx1151 / Aurora / 0.1.40 で check が通らなかった記録がありますが、これは当該コメントの記載であり、本調査で GPU 実行や parity 測定はしていません。実行時に parity check のログを出すのは、この変数そのものではなく `rope_parity` 実行ファイルです。

## 文書との照合

`docs/DETAILS.md` と `README.md` では、この fused kernel や `STRATA_NORM_ROPE` の設定方法・条件に関する説明を確認できませんでした。動作説明はコードと parity check の実装を根拠にしています。

## 根拠

- `src/kernels/cuda/native_rope.cu:175-187`: HIP/CUDA の環境変数判定、既定値、寸法条件。
- `sycl/src/kernels/cuda/native_rope.dp.cpp:229-241`: 同じ判定を持つ SYCL 側コピー。
- `src/kernels/cuda/native_rope.cu:208-209`: in-place RoPE の 32/128 thread launch 選択。
- `src/core/verify.cpp:1196-1212`: QSA verify の fused/個別経路。
- `src/core/mtp.cpp:740-752,806-821`: MTP K/Q の融合条件と fallback。
- `src/kernels/rope_parity.cpp:438-446`: CUDA-side parity check の skip/run 判定とソースコメント上の AMD 状況。
- `sycl/src/kernels/rope_parity.cpp:610-620`: SYCL-side parity check の対応箇所。
