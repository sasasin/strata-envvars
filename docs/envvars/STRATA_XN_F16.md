# `STRATA_XN_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Hyper-connection の正規化出力 `xn16` を、BF16 値ではなく FP16 GEMM が読む FP16 イメージとして生成する最適化を許可する。通常はこの変換が有効で、`STRATA_XN_F16` が `0` で始まると無効になる。初期化時の条件がそろうと、`gr_norm` / `gr_norm_rs` が `xn16` を書き、down / inject 投影の BF16 GEMM が同じ FP16 表現を再変換せず読む。Hyper-connection の他の処理を切り替える変数ではない。[`engine/src/prefill/prefill.cpp:2732-2735`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/prefill.cpp:5101-5106`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/gemm.cu:1241-1249`](../../../../Niko1221/Strata/engine/src/prefill/gemm.cu)

## 値と判定

`std::getenv` で値を取得し、未設定か、先頭文字が `'0'` かだけを判定する。空文字は未設定ではなく「先頭が `0` ではない」ため有効側になる。文字列全体の parse、数値検証、空白除去、大文字小文字変換は行わない。[`engine/src/prefill/prefill.cpp:2734-2735`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 読み取り箇所に到達した場合 | 有効 | 空文字、`1`、`true`、`false`、` 0` など先頭文字が `0` 以外の値 | `0`、`0 `、`0anything`、`00` |

「無効」はこの最適化を許可しないという意味であり、初期化失敗ではない。設定値は `Prefill::init` 内の関数ローカル `static` に保存されるため、プロセス内で最初にその箇所へ到達した時点の値が後続の初期化にも使われる。[`engine/src/prefill/prefill.cpp:2443-2446`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/prefill.cpp:2734-2735`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

## 有効になる条件

- Metal の `Prefill::init` は Metal 固有の初期化を行って先に戻るため、この CUDA 系実装のフラグ設定には到達しない。[`engine/src/prefill/prefill.cpp:2443-2454`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)
- `m.f16_io` が false であること。HIP の prompt FP16 I/O が選択される経路では `m.xn_f16` は false になる。[`engine/src/prefill/prefill.cpp:2724-2735`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)
- `Gemm::bf16_converts_x()` が true であること。CUDA では `STRATA_EXPERIMENTAL_SM60` ビルドを除き、BF16 GEMM が FP16 経路を選ぶ場合に true になる。`STRATA_BF16_TC` がこの経路を左右し、未設定時は compute capability 7.0–7.4 で既定有効、7.5 では既定無効、8.0 以上では通常無効（`STRATA_BF16_TC=2` のテスト経路を除く）。6.x は FP32 経路となる。したがって通常の 7.5 GPU では `STRATA_BF16_TC` による有効化が必要。[`engine/src/prefill/gemm.cu:947-958`](../../../../Niko1221/Strata/engine/src/prefill/gemm.cu) [`engine/src/prefill/gemm.cu:1143-1148`](../../../../Niko1221/Strata/engine/src/prefill/gemm.cu)
- HIP は `Gemm::bf16_converts_x()` が常に false を返す。SYCL 実装も false を返すため、これらでは `STRATA_XN_F16` の値で実際の処理は有効にならない。[`engine/src/prefill/gemm.cu:1143-1148`](../../../../Niko1221/Strata/engine/src/prefill/gemm.cu) [`engine/sycl/src/prefill/gemm.dp.cpp:842-843`](../../../../Niko1221/Strata/engine/sycl/src/prefill/gemm.dp.cpp)
- さらに各 Hyper-connection 投影で `xn16_lo` がなく、`ldx == D` の場合に限り `xf16` が true となる。そうでなければ writer/reader は通常の BF16 または対応する別レイアウトを使う。[`engine/src/prefill/prefill.cpp:5101-5106`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

Strata の `docs/DETAILS.md` は `STRATA_BF16_TC=1` と本変数を組み合わせて記載している。[`docs/DETAILS.md:1338-1346`](../../../../Niko1221/Strata/docs/DETAILS.md) 一方、`docs/SETTINGS.md` の表は本変数の対象を「NVIDIA and AMD」とするが、現行の HIP 実装では `bf16_converts_x()` が false のため、その表記はコード上の有効条件を正確には表していない。[`docs/SETTINGS.md:487`](../../../../Niko1221/Strata/docs/SETTINGS.md) [`engine/src/prefill/gemm.cu:1143-1148`](../../../../Niko1221/Strata/engine/src/prefill/gemm.cu)

## 実行時の詳細

`Prefill::init` が GEMM scratch を初期化した後に環境変数を評価し、`m.xn_f16` に条件判定の結果を保持する。環境変数の読み取りは関数ローカル `static` によりプロセス内で一度だけで、実行中に環境を変更しても再評価されない。一方、GPU 経路の条件は各 `Prefill` インスタンスの初期化時に評価される。[`engine/src/prefill/prefill.cpp:2722-2735`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

実行時は `xf16 = m.xn_f16 && !m.xn16_lo && ldx == D` を down / inject 投影に渡す。FP16 イメージとして書かれた `xn16` を FP16 Tensor Core GEMM が直接読む場合、GEMM 内の BF16→FP16 活性変換を省く。フラグが false の場合は通常の BF16 イメージを使い、FP16 GEMM 経路では GEMM 側が入力を変換する。[`engine/src/prefill/prefill.cpp:5101-5106`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/prefill.cpp:5124-5124`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/prefill.cpp:5157-5157`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/gemm.cu:1241-1249`](../../../../Niko1221/Strata/engine/src/prefill/gemm.cu)

## ログと測定値

この変数の読み取りや有効化を知らせるログはない。値が最適化を無効にしても、それ自体による警告・エラー・終了経路はない。別条件のため `xf16` が使われない理由を本変数専用に出力するログもない。[`engine/src/prefill/prefill.cpp:2732-2735`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp) [`engine/src/prefill/prefill.cpp:5101-5106`](../../../../Niko1221/Strata/engine/src/prefill/prefill.cpp)

## 根拠

- `engine/src/prefill/prefill.cpp:2443-2454` — 初期化経路と Metal の早期 return。
- `engine/src/prefill/prefill.cpp:2722-2735` — GEMM 条件、prompt FP16 状態、環境変数の評価と `m.xn_f16` の設定。
- `engine/src/prefill/prefill.cpp:5101-5106,5124,5157` — `xf16` の追加条件、hyper-connection writer と投影への適用。
- `engine/src/prefill/gemm.cu:947-958,1143-1148,1241-1249` — CUDA の BF16 経路選択、backend 判定、FP16 入力イメージを直接読む分岐。
- `engine/sycl/src/prefill/gemm.dp.cpp:842-843` — SYCL では BF16 入力変換最適化を報告しない実装。
- `docs/DETAILS.md:1338-1346`, `docs/SETTINGS.md:487` — 資料との照合。SETTINGS の対象 backend 表記と実装条件に差がある。
