# `STRATA_WMMA_GEMM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの動作は含めない。

## 役割

AMD HIP ビルドの prefill に使う dense FP16 / BF16 GEMM で、Strata 内蔵 RDNA3 / RDNA3.5 WMMA カーネルを hipBLASLt などの通常経路より先に試す opt-in スイッチです。decode の GEMM 全般を切り替える変数ではありません。未設定時はこの WMMA 経路を選びません。

## 値と判定

値全体の parse や数値変換はせず、環境変数の先頭文字だけを調べます。FP16 と BF16 の関数それぞれで `static const bool` に保存されるため、各関数の初回判定後に環境を変更しても、その関数では再評価されません。

| 設定 | `STRATA_WMMA_GEMM` の判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0anything`） |
| 上記以外 | 有効（例: `1`, `2`, `true`, `false`, ` 0`） |

## 有効になる条件

変数が有効でも、すべての GEMM が WMMA で処理されるわけではありません。

- Strata の AMD HIP ビルドであること。CUDA ビルドには WMMA 実装ファイルは組み込まれず、このスイッチによる経路はありません。
- 実行 GPU の arch 名が `gfx1100`, `gfx1101`, `gfx1102`, `gfx1150`, `gfx1151` のいずれかであること。`gfx1103` や `gfx1152` は含まれず、通常経路に戻ります。実行時の GPU 判定はデバイスごとに cache されます。
- 入力ポインターが null でなく、`T`, `N`, `K` が正で、`K % 16 == 0`、`ldy >= N` であること。
- `T >= 16` で、`beta` が `0.0f` または `1.0f` であること。

BF16 呼び出しでは、さらに `STRATA_WMMA_BF16` が判定されます。これは未設定なら有効、空文字または先頭文字が `0` なら無効、それ以外なら有効です。したがって BF16 WMMA を止めるには `STRATA_WMMA_GEMM` または `STRATA_WMMA_BF16` のいずれかを無効にできます。`STRATA_WMMA_BF16` は FP16 経路には関与しません。

## 実行時の詳細

`Gemm::f16()` は `STRATA_WMMA_GEMM` が有効で上記の `T` / `beta` 条件を満たすと、`strata_wmma_gemm_f16()` を試します。ただし、それより前に `STRATA_PF_GEMM` が先頭文字 `1` で、`T >= STRATA_PF_SWITCH_MIN_T`（未設定時の下限は 0）を満たし、専用 FP16 prefill GEMM がその形状を受け付けた場合は、そちらが先に使われます。専用経路が使われないとき WMMA を試し、WMMA の arch / shape 条件に合わなければ後続の FP16 経路（`f16_io_`、hipBLASLt、または HIP BLAS）へ進みます。

`Gemm::bf16()` も WMMA を hipBLASLt より先に試します。`ldx <= K` のとき Strata は `ldx` を 0 に正規化してから判定し、`ldx > K` の呼び出しでは WMMA を試しません。WMMA が条件を満たさない場合は、後続の FP16 入力用処理または hipBLASLt / HIP BLAS の経路へ進みます。

カーネルは `Y[t,n] = beta * Y[t,n] + Σ W[n,k] * X[t,k]` を計算します。`T` と `N` がともに 32 以上なら 64x64 タイル、それ以外は 16x16 タイルで起動します。WMMA 経路を選択した場合も、コード上この変数に関するログ出力はありません。条件に合わず関数が `false` を返す場合は呼び出し元が次の GEMM 経路へ進みます。

## 根拠

- 環境変数の読み取り、値判定、前後の GEMM 経路: `src/prefill/gemm.cu:571-607,675-700`。HIP 用 SYCL ソースにも同じ判定と分岐があります: `sycl/src/prefill/gemm.dp.cpp:746-782,833-857`。
- HIP ビルドでの WMMA ソース組み込み: `CMakeLists.txt:589-593`。
- GPU arch ごとの実行時判定、ポインター・shape・`K`・`beta` 条件、タイル選択: `src/prefill/wmma_gemm.cu:31-56,264-301`。対象 arch 名: `include/strata/kernels/gfx_arch.hpp:22-26`。
- `STRATA_PF_GEMM` と `STRATA_PF_SWITCH_MIN_T` の先行判定: `src/prefill/gemm.cu:680-687`。
- `docs/DETAILS.md` と `docs/AMD_HIP.md` に、この環境変数固有の説明や性能測定値は見つかりませんでした。
