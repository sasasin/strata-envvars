# `STRATA_WMMA_GEMM`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの内部動作は対象外。

## 役割

AMD HIP の prefill dense GEMM で、Strata の RDNA3 / RDNA3.5 WMMA kernel を試す opt-in スイッチです。FP16 の `Gemm::f16()` と BF16 の `Gemm::bf16()` から呼ばれます。kernel が対象 shape や GPU を受け付けない場合は `false` を返し、通常の hipBLASLt / hipBLAS 経路へ進みます。CUDA ビルドではこの判定は `STRATA_USE_HIP` の条件でコンパイルされません。

## 値と判定

両方の GEMM 関数内に別々の `static const bool` があり、それぞれ最初にその関数へ到達した時点で一度だけ環境変数を読みます。その後プロセス内で値を変えても再判定されません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0anything`） |
| それ以外の非空文字列 | 有効（例: `1`, `true`, `false`, `2`） |

文字列全体や数値としての妥当性は検査せず、先頭文字だけを見ます。したがって `false` も有効です。これは「WMMA を常に実行する」という意味ではなく、呼び出し側と kernel の条件を通った場合に WMMA を試す指定です。

根拠: `src/prefill/gemm.cu:630-635,733-740`。同じ判定は `sycl/src/prefill/gemm.dp.cpp:752-757,838-845` にあります。

## 有効になる条件

- HIP ビルドで `STRATA_USE_HIP` が定義され、prefill の BF16 または FP16 dense GEMM 関数が呼ばれる必要があります。CMake は HIP のときにだけ `src/prefill/wmma_gemm.cu` を `strata_prefill` に加えます（`CMakeLists.txt:607-611`）。
- WMMA の実 kernel は、ビルド時の `CMAKE_HIP_ARCHITECTURES` が `gfx11` を含む場合に定義される `STRATA_WMMA_GFX11` の下でコンパイルされます。gfx11 を含まない HIP build では同じ関数名の stub が `false` を返すため、環境変数を有効にしても WMMA は実行されません。
- FP16 は `T >= 16` かつ `beta` が `0.0f` または `1.0f` の場合に kernel を試します。BF16 も同じ条件に加え、`ldx == 0` が必要です。BF16 関数は `ldx <= K` の入力を `0` に正規化するため、通常の連続 stride は対象になりますが、`ldx > K` は WMMA 経路を通りません。
- kernel 側はポインターが非 null、`T`, `N`, `K` が正、`K` が16の倍数、`ldy >= N` を要求します（`ldy <= 0` は GEMM 関数が `N` に直します）。GPU は `gfx1100`, `gfx1101`, `gfx1102`, `gfx1103`, `gfx1150`, `gfx1151` のみです。別の GPU、たとえば gfx1152 や gfx12 では `false` になり、fallback します。
- BF16 にはさらに `STRATA_WMMA_BF16` があります。これは unset なら有効、設定時は空文字または先頭が `0` なら無効、それ以外なら有効です。`STRATA_WMMA_GEMM` と `STRATA_WMMA_BF16` の両方が有効でなければ BF16 WMMA は試されません。FP16 経路にはこの追加条件はありません。
- FP16 関数では先に `STRATA_PF_GEMM` による別の GEMM が shape を処理して成功すると、WMMA 判定に到達しません。

根拠: `src/prefill/gemm.cu:624-638,728-742`; `src/prefill/wmma_gemm.cu:41-56,264-289`; `include/strata/kernels/gfx_arch.hpp:15-25`。

## 実行時の詳細

有効値かつ呼び出し側の条件を満たすと、`strata_wmma_gemm_f16()` または `strata_wmma_gemm_bf16()` が共通 dispatch に入ります。`T >= 32` かつ `N >= 32` では 64×64 の出力タイル kernel、それ以外は 16×16 kernel を起動します。dispatch が `true` を返した場合、GEMM 関数はその場で戻り、通常の後続経路へ進みません。未対応の GPU / shape では `false` となり、BF16 は hipBLASLt が利用可能ならそれを試してから hipBLAS へ、FP16 も hipBLASLt が利用可能ならそれを試してから hipBLAS へ進みます。

この変数自体について専用の起動ログや警告はありません。GPU の対応判定は device ごとに cache されます。WMMA kernel 起動後のエラーは dispatch の戻り値で検査されず、後続の `true` となるため、kernel 実行成否をこの関数の戻り値だけからは確認できません。

WMMA を使わない場合の fallback は GEMM 状態でも異なります。FP16 は `f16_io_` が有効かつ `beta == 0` なら `f16_inplace()` を呼び、それ以外は利用可能な hipBLASLt を試した後に hipBLAS へ進みます。BF16 は `f16_io_` が有効なら weight を scratch に FP16 変換して `f16_inplace()` を実行しますが、この経路で `beta != 0` だと stderr に `prefill gemm: an accumulating BF16 GEMM on the FP16 prompt path` を出して終了します。`f16_io_` が無効なら利用可能な hipBLASLt を試してから hipBLAS へ進みます。

根拠: `src/prefill/wmma_gemm.cu:45-56,264-301`; `src/prefill/gemm.cu:640-660,720-725,746-753`。

## 文書との照合

`docs/DETAILS.md` と `docs/AMD_HIP.md` に、この変数の値の解釈や既定値を説明する記載は見つかりませんでした。`docs/STRIX_HALO.md:18` は prompt GEMM に WMMA kernel があることを概説しますが、この環境変数の設定方法や条件は説明していません。`CMakeLists.txt:704-710` には HIP WMMA dense GEMM parity test の登録がありますが、これはテストコードの存在を示すもので、実運用の性能や正確性の測定結果とは扱いません。この調査では build、GPU 実行、性能測定、テストは行っていません。

## 根拠

- 環境変数の読み取りと GEMM の呼び出し条件: `src/prefill/gemm.cu:624-638,728-742`、SYCL 側の同等箇所 `sycl/src/prefill/gemm.dp.cpp:746-760,833-847`。
- WMMA dispatch の形状条件、タイル選択、GPU ごとの対応判定: `src/prefill/wmma_gemm.cu:41-56,264-301`。
- gfx11 対応名一覧: `include/strata/kernels/gfx_arch.hpp:15-25`。
- HIP ビルドでの実装追加と gfx11 build macro: `CMakeLists.txt:607-611`, `cmake/hip_backend.cmake:94-98`。
- gfx11 build の compile-time gate と非 gfx11 stub: `cmake/hip_backend.cmake:94-99`; `src/prefill/wmma_gemm.cu:31-37,710-736`。
