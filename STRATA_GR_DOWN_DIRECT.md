# `STRATA_GR_DOWN_DIRECT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の SYCL ポートが複数 token の fused hyper-connection read を行うとき、down projection のカーネルを直接読み込み方式にするか、共有ローカルメモリにタイルする従来方式にするかを選びます。直接方式のカーネルは activation `xn` を global memory から読み、タイル方式は work-group ごとに activation を local memory にステージします（`sycl/src/kernels/cuda/fused_gr.dp.cpp:479-484,499-512`）。

この変数単独では通常の既定経路は変わりません。`STRATA_GR_DOWN_SLICED` が未設定なら sliced 方式が先に選ばれ、`STRATA_GR_DOWN_DIRECT` は判定されません。sliced 方式を無効にした場合に、この変数が direct と tiled の選択に使われます（同 `:582-584,596-599,1793-1812`）。

## 値と判定

値は `std::atoi()` で整数変換し、0 かどうかで判定します。文字列全体の妥当性検査はありません。空文字、数字で始まらない文字列は通常 0 となり、`1tail` は 1、`-1` は -1 に変換されて有効になります。先頭の空白と符号も `atoi` の規則で扱われます。

| 環境変数の状態 | 判定値 | `STRATA_GR_DOWN_SLICED=0` のとき |
|---|---:|---|
| 未設定 | 有効（既定） | 直接読み込みカーネル |
| `0`、空文字、非数値文字列 | 無効 | タイルカーネル |
| 0 以外に変換される値（例: `1`, `2`, `-1`, `1tail`） | 有効 | 直接読み込みカーネル |

結果は helper 内の `static const bool` に保存され、最初に必要になった後はプロセス内で再評価されません（同 `:596-599`）。

## 有効になる条件

- 対象は Strata の SYCL ポート (`sycl/`) です。調査したソースでは、この名前の読み取りは `sycl/src/kernels/cuda/fused_gr.dp.cpp` にのみあります。CUDA/HIP の実装をこの変数が切り替えるコードは確認できません。
- fused GR read が呼ばれる必要があります。SYCL 側では `fused_gr_read_multi()` の down projection の選択に使われます。また単一 read の `fused_gr_read()` は sliced、norm split、direct のいずれかが有効なら multi read を1 tokenで呼びます（同 `:1607-1610,1892-1915`）。
- direct/tiled の選択で実際に参照されるのは `STRATA_GR_DOWN_SLICED=0` の場合だけです。sliced が未設定または `atoi` 結果が非0なら sliced kernel と reduce kernel が選択され、本変数の値は down projection の分岐に影響しません（同 `:582-584,1793-1807`）。
- sliced が無効で、本変数が有効なら direct kernel、無効なら tiled kernel が選択されます（同 `:1808-1812`）。

## 実行時の詳細

SYCL の `fused_gr_read_multi()` は、sliced 経路でなければ本変数を評価し、direct の場合は `gr_down_multi_direct_kernel` を launch します。direct kernel は各 token の activation を読みながら down projection の部分和を作ります。無効の場合は tiled kernel 側に進み、デバイスの local memory 容量から得た chunk 数を使って launch します（同 `:1777-1792,1808-1859`）。この helper 自体はログを出しません。

ソースコメントでは `STRATA_GR_DOWN_DIRECT=0` が tiled kernel を選ぶ設定で、3〜6 token の `gr_bench` では direct より13〜19%遅かったと記されています（同 `:596-598`）。これはコードコメントに記録された測定で、文書には測定環境や反復条件が示されていないため、一般的な性能差としては扱えません。`docs/INTEL.md` は `STRATA_GR_DOWN_SLICED=0` で sliced 以前の direct kernel に戻し、さらに `STRATA_GR_DOWN_DIRECT=0` で旧経路に切り替えると記載しています。同資料の別の測定では sliced 化により GR read が6 tokenで108.6→76.5 μs（和は約1e-7差）、135→110 μs（bitwise equal）と報告されていますが、これは sliced 方式との比較であり、本変数単独の効果ではありません（`docs/INTEL.md:476-481`）。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:479-524`: direct down kernel の読み込みと部分和。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:582-599`: sliced/direct の既定値、変換、static cache。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1777-1812`: down projection の優先順位と kernel launch。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1892-1915`: 単一 read から multi read への条件付き routing。
- `docs/INTEL.md:154-164`: SYCL ポートが Strata エンジンの Intel 向け実装であること。
- `docs/INTEL.md:476-481`: sliced/direct/tiled の切替説明と測定記録。
