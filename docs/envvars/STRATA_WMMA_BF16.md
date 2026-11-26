# `STRATA_WMMA_BF16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP ビルドの prefill BF16 GEMM で、専用 WMMA GEMM を試すかどうかを制御します。この変数単独では WMMA を有効にしません。別の `STRATA_WMMA_GEMM` が有効で、形状などの条件を満たした場合に限り、値が無効でないと専用 BF16 WMMA 関数を呼びます。関数が処理しない場合は通常の BF16 GEMM 経路へ進みます（`engine/src/prefill/gemm.cu:1154-1168,1183-1193,1295-1300`）。

読み取りは `Gemm::bf16` にあり、HIP 用の `strata_prefill` に WMMA 実装を加える構成です（`engine/cmake/strata_gpu_engine.cmake:482-488`）。同じ HIP 条件付きの分岐は SYCL 側の BF16 GEMM 実装にもあります（`engine/sycl/src/prefill/gemm.dp.cpp:845-860`）。CUDA-only ビルドではこのゲートはコンパイルされません。

## 値と判定

`std::getenv` の結果を関数ローカル `static const bool` に保存し、文字列全体の parse ではなく、未設定かどうかと先頭 byte だけを判定します（`engine/src/prefill/gemm.cu:1162-1164`; `engine/sycl/src/prefill/gemm.dp.cpp:854-857`）。

| 条件 | unset | WMMA BF16 を許可する値の例 | WMMA BF16 を許可しない値の例 |
|---|---|---|---|
| `STRATA_USE_HIP` が定義されたビルド | 許可（`getenv` が null なら true） | `1`, `true`, `false`, `no`, ` 0` | 空文字、`0`, `00`, `0anything` |
| `STRATA_USE_HIP` が未定義 | この変数の判定コードなし | 該当なし | 該当なし |

空文字は設定済みですが、先頭 byte が NUL なので false です。非空値は先頭が文字 `0` のときだけ false で、残りの文字、数値としての妥当性、空白、大文字小文字は検査しません。したがって `false` や `no` は先頭が `f` / `n` のため true、` 0` は先頭が空白のため true です。境界値・無効文字列のエラーや fallback はなく、単純にこの真偽値として扱われます。

## 有効になる条件

- ビルドで `STRATA_USE_HIP` が定義されていること。HIP backend 以外ではこの変数を読む分岐がありません（`engine/src/prefill/gemm.cu:1159-1168`; `engine/sycl/src/prefill/gemm.dp.cpp:851-860`）。
- 別の `STRATA_WMMA_GEMM` が同じ `Gemm::bf16` 実装で true と判定されること。これは未設定または空文字、先頭が `0` の値では false で、それ以外の非空値で true です（`engine/src/prefill/gemm.cu:1162-1164`）。
- GEMM 呼び出しが初期の `T <= 0 || N <= 0` で return せず、正規化後の `ldx` が 0、`T >= 16`、`beta` が `0.0f` または `1.0f` であること（`engine/src/prefill/gemm.cu:1154-1165`）。`ldx <= K` は事前に 0 に正規化されます（同:1157-1158）。
- `strata_wmma_gemm_bf16` が入力・寸法・デバイスなどの内部条件を受理すること。gfx11 のディスパッチは有効なポインター、正の寸法、`K % 16 == 0`、許容 beta、`ldy >= N` を要求します（`engine/src/prefill/wmma_gemm.cu:277-301`）。HIPCC で gfx11 以外の場合は別実装 `hip_unsloth_wmma_gemm_bf16` に渡されます（同:315-324）。いずれかが false を返すと呼び出し側は後続経路へ進みます。

## 実行時の詳細

対象は BF16 の prefill GEMM だけです。ゲートを通り専用関数が true を返した場合に限り、その GEMM は早期 return します。`engine/src/prefill/gemm.cu` ではそうでない場合、HIPBLASLt が利用可能ならその経路を試し、続いて条件に合えば RDNA2 用の SGEMM 変換経路を試し、最後はネイティブ BF16 `cublasGemmEx` 呼び出しへ進みます（同:1164-1168,1183-1193,1295-1300）。SYCL ソースでは決定的 BF16 経路、HIPBLASLt（HIPCC かつ利用可能な場合）、staging 経路を順に試し、最後は `dpct::blas::gemm` へ進みます（`engine/sycl/src/prefill/gemm.dp.cpp:875-945`）。この変数が false でも BF16 GEMM 自体を停止しません。

値は `Gemm::bf16` が初期寸法チェックを通過して HIP 用ゲートに到達した際に初めて読み取られ、関数ローカル `static` に一度だけ保存されます。以降の同じプロセス内の呼び出しでは環境を読み直さないため、その後の環境変更は反映されません。寸法チェックで先に return した呼び出しではまだ初期化されません（`engine/src/prefill/gemm.cu:1154-1164`; `engine/sycl/src/prefill/gemm.dp.cpp:845-857`）。

## ログと測定値

このスイッチの読み取り、有効化、無効化、または WMMA 関数の false 戻りを知らせるログはありません。ゲートが通らない場合は上記の通常経路へ進みます。そこで別の条件によるエラーが発生し得ますが、この変数に固有の失敗として扱うコードはありません（`engine/src/prefill/gemm.cu:1164-1168,1183-1193,1295-1300`）。`docs/DETAILS.md` にこの変数固有の測定値は見当たりません。

## 根拠

- `engine/src/prefill/gemm.cu:1154-1168,1183-1193,1295-1300` — HIP 用ゲート、値の読み取り、失敗時の後続処理。
- `engine/sycl/src/prefill/gemm.dp.cpp:845-860` — SYCL 側ソースにある同じ HIP 条件付き読み取り。
- `engine/src/prefill/wmma_gemm.cu:277-324` — gfx11 ディスパッチ条件と gfx11 以外の委譲。
- `engine/cmake/strata_gpu_engine.cmake:482-488` — `strata_prefill` と HIP 時の WMMA 実装の組み込み。
