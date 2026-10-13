# `STRATA_GR_DOWN_SLICED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 fused GR read の down projection に、列方向に分割した sliced kernel を使うかを選びます。これは top-level CUDA build の `src/kernels/cuda/fused_gr.cu` ではなく、Intel GPU 向けの別 SYCL build が使う `sycl/src/kernels/cuda/fused_gr.dp.cpp` にある設定です。SYCL build は CUDA ソースに対応する移植済み `.dp.cpp` を優先してコンパイルします（`sycl/CMakeLists.txt:1-7,87-104,205-214`）。

## 値と判定

`gr_down_sliced()` が初回に `getenv()` と `std::atoi()` で判定し、結果を関数内 `static const bool` に保存します。未設定なら有効、設定されている場合は `atoi` の結果が 0 以外なら有効です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:582-585`）。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字、`0`、`false`、数字で始まらない文字列 | 無効（`atoi` が 0） |
| `1`、`-1`、`2tail`、空白の後の非ゼロ整数 | 有効（整数変換結果が 0 以外） |
| `0tail`、`00`、`+0` | 無効 |

文字列全体の検証はなく、大文字小文字を比較する処理もありません。符号と先頭空白は `atoi` の規則に従い、数値の後ろの文字列は判定されません。整数変換で 0 になる値は無効です。最初の判定後はプロセス中に環境変数を変えても再評価されません。

## 有効になる条件

- この変数を読むのは SYCL fused GR 実装です。CUDA/HIP の同名相当経路にこの変数の読み取りはありません。
- 実際の層処理で fused GR が選ばれるには、`gr_native_mmvf` が有効で、`--no-fused-gr` がなく、GPU stages、layer dump、half dump、stage timing が使われていないことが必要です（`sycl/src/program/generate.cpp:2844-2853`）。native モデル経路は `gr_native_mmvf` を有効にします（同 `:2298-2306`）。
- さらに層の形状が `n_embd=2560, hc=4, hc_lr=320` のときだけ fused GR が対応します（`sycl/src/core/layer.cpp:1560-1562`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:1888-1890`）。この条件に合わない経路では、この変数は down projection を切り替えません。

## 実行時の詳細

有効時は `fused_gr_read_multi()` が列幅 128、80 slice の down kernel と reduce kernel を起動します。各 work-group が入力 activation の列 slice を共有メモリへ読み、down/inject 行の部分和を出し、reduce kernel が slice 順に加算して後段用の出力を作ります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:526-580,1793-1807`）。単一 token の `fused_gr_read()` も、sliced、norm split、direct のいずれかが有効なら multi-token 実装を呼ぶため、この設定は single-token read にも関係します（同 `:1900-1915`）。

無効時の次の分岐は `STRATA_GR_DOWN_DIRECT` です。同変数も未設定なら既定で有効な direct kernel を使います。`STRATA_GR_DOWN_DIRECT=0` も指定した場合は tiled kernel に進み、device local memory から一度に処理できる token 数を決め、必要なら複数 launch に分けます（同 `:596-599,1777-1793,1808-1860`）。したがって `STRATA_GR_DOWN_SLICED=0` 単独では tiled kernel ではなく direct kernel になります。

`docs/INTEL.md` は、sliced kernel による GR read の時間を 6 token で 108.6 µs から 76.5 µs と記し、和の差は約 `1e-7`、同変数を `0` にすると direct kernel に戻ると説明しています。これは同資料に記載された測定値で、他の機器・条件での性能を保証しません（`docs/INTEL.md:472-477`）。

## 根拠

- SYCL build が `.dp.cpp` の移植済み実装を選ぶ: `sycl/CMakeLists.txt:1-7,87-104,205-214`
- 値の取得と既定値: `sycl/src/kernels/cuda/fused_gr.dp.cpp:582-585`
- sliced kernel と slice reduce の実装・選択: 同 `:526-580,1793-1807`
- direct/tiled fallback: 同 `:596-599,1777-1793,1808-1860`
- fused GR の層側条件と対応 shape: `sycl/src/program/generate.cpp:2844-2853`, `sycl/src/core/layer.cpp:1560-1562`, `sycl/src/kernels/cuda/fused_gr.dp.cpp:1888-1890,1900-1915`
- 記載された測定と `=0` の説明: `docs/INTEL.md:472-477`
