# `STRATA_WMMA_GEMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

HIP ビルドの prefill FP16/BF16 GEMM で、Strata の WMMA GEMM 実装を試す opt-in スイッチ。通常は hipBLASLt など後続の GEMM 経路へ進み、この変数が有効かつ shape などの条件を満たして WMMA 関数が成功を返す場合に限り、その呼び出しを使って早期 return する。CLI 引数や設定ファイルによる同等の上書きはこのコードにはない。CUDA ビルドでは読み取りコードが `STRATA_USE_HIP` の条件内にないため、この変数は Strata の制御に使われない。HIP ビルドでは CMake が `gemm.cu` を `strata_prefill` に含め、追加で `wmma_gemm.cu` を加える（`engine/cmake/strata_gpu_engine.cmake:482-486`）。

対象は prefill の dense GEMM 呼び出しであり、変数の有効化だけで全 GEMM が WMMA になるわけではない。実際にどの GEMM 呼び出しがあるかは `engine/src/prefill/prefill.cpp:3995-3997` などを参照。

## 値と判定

HIP ビルドで BF16 経路と FP16 経路がそれぞれ `Gemm::bf16` / `Gemm::f16` 内で読み取る。C の文字列の先頭文字だけを調べ、数値変換、文字列全体の比較、空白除去、大文字小文字変換はしない（`engine/src/prefill/gemm.cu:1159-1165,1307-1315`）。

| 条件（build / 呼び出し） | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP、FP16 `Gemm::f16` | 無効 | 空でない値で先頭が `0` 以外（例: `1`, `true`, `false`, ` 0`, `-1`） | 空文字、または先頭が `0`（例: `0`, `00`, `0anything`） |
| HIP、BF16 `Gemm::bf16` | 無効 | FP16 と同じ | FP16 と同じ |
| CUDA / 通常の SYCL | 読み取りなし | 該当なし | 該当なし |

したがって `true` や `false` はどちらも有効、先頭に空白を置いた ` 0` も有効になる。一方 `0anything` は無効。未設定と空文字は無効である。数値としての妥当性は検査されない。ソース中の `engine/sycl/src/prefill/gemm.dp.cpp:851-860,952-962` にも同じ読み取り式があるが、どちらも `#ifdef STRATA_USE_HIP` 内である。SYCL は独立 backend として CUDA/HIP を同時に構成しないため（`engine/CMakeLists.txt:23-32`）、通常の SYCL ビルドではこの箇所は有効にならない。候補名は `engine/src/core/arch_defaults_test.cpp:115-117` のテスト用除外リスト、`terminal/data/settings-register.json:52589-52602` の自動生成設定台帳、`engine/cmake/strata_gpu_engine.cmake:675-680` のコメントとテスト登録にも現れるが、これらは実行時の追加読み取りではない。

## 有効になる条件

- `STRATA_USE_HIP` を定義した HIP build で `Gemm::f16` または `Gemm::bf16` に到達する必要がある。通常の CUDA build では当該読み取りブロックがコンパイルされない（`engine/src/prefill/gemm.cu:1159,1307`; HIP 定義は `engine/cmake/hip_backend.cmake:105-118`）。
- `Gemm::f16`: `T >= 16` かつ `beta` が `0.0f` または `1.0f` であることが呼び出し側の条件。加えて `strata_wmma_gemm_f16` が `true` を返す必要がある（`engine/src/prefill/gemm.cu:1313-1315`）。
- `Gemm::bf16`: 追加の `STRATA_WMMA_BF16` 判定が有効で、`ldx` が `0`、`T >= 16`、`beta` が `0.0f` または `1.0f` であり、`strata_wmma_gemm_bf16` が `true` を返す必要がある。`ldx <= K` は先に `0` に正規化される（同 `:1157-1166`）。`STRATA_WMMA_BF16` は未設定なら有効、空文字または先頭 `0` なら無効、それ以外の先頭文字なら有効という別の判定であり、こちらも関数内 `static` として BF16 経路でキャッシュされる（同 `:1162-1165`）。
- GFX11 の WMMA dispatch では `K > 0`、`K % 16 == 0`、`ldy >= N` も必要で、実行中デバイスの gfx11 WMMA 対応判定を通らなければ `false` を返す。デバイス判定結果は device ごとにキャッシュされる（`engine/src/prefill/wmma_gemm.cu:44-59,276-301`）。ビルド時には gfx11 向け HIP arch の場合に `STRATA_WMMA_GFX11` を定義し、WMMA intrinsics を含む実装を有効にする（`engine/cmake/hip_backend.cmake:114-118`; `engine/src/prefill/wmma_gemm.cu:34-40`）。
- `Gemm::f16` は `STRATA_PF_GEMM` の経路を先に試し、それが処理した場合は WMMA GEMM の呼び出しへ進まない。`STRATA_PF_GEMM` が設定されているだけで必ず優先されるのではなく、その閾値と `strata_pf_gemm_f16` の戻り値も条件になる（`engine/src/prefill/gemm.cu:1310-1315`）。
- GFX11 以外では Strata の wrapper が、HIP compile 時かつ `STRATA_HIP_GFX906` でない場合に `hip_unsloth_wmma_gemm_f16/bf16` へ処理を委譲する。wrapper が `false` を返す場合は呼び出し元の後続 GEMM 経路へ進む。ここではその helper 内部の挙動を Strata の WMMA 実装として説明しない（`engine/src/prefill/wmma_gemm.cu:304-323`）。

## 実行時の詳細

`Gemm::bf16` と `Gemm::f16` は別々の関数内 `static const bool` として値を初期化する。各経路で最初に `T <= 0` または `N <= 0` ではない呼び出しに到達した時点で一度だけ環境を読み、その関数の以後の呼び出しではキャッシュ値を使う。したがって、その経路の初回読み取り後にプロセス環境を変えても反映されない。BF16 と FP16 の初回読み取り時点は独立している（`engine/src/prefill/gemm.cu:1154-1165,1303-1315`）。

GFX11 WMMA dispatch は shape / device 条件を満たすと、`T >= 32 && N >= 32` では 64×64 タイル、それ以外では 16×16 タイルの kernel を launch し、`true` を返す。呼び出し側は `true` の場合に通常の後続 GEMM 経路を省略する。条件を満たさず `false` なら BF16 は後続の hipBLASLt などへ、FP16 は `f16_io_` 経路（条件付き）、hipBLASLt などへ進む（`engine/src/prefill/wmma_gemm.cu:276-301`; `engine/src/prefill/gemm.cu:1164-1189,1312-1327`）。

## ログと測定値

この変数の値、有効化、WMMA 経路の選択、GFX11 shape gate の失敗について、上記の実装箇所には専用ログや警告、環境変数に起因する終了処理がない。GFX11 dispatch は kernel launch 後に `true` を返すが、その箇所で launch status を検査していない（`engine/src/prefill/wmma_gemm.cu:290-301`）。通常経路へ戻った後に呼ばれる BLAS 側のエラー処理は、WMMA 変数専用の観測手段ではない。`docs/DETAILS.md` にこの変数名の記述は見つからず、性能値は記載しない。

## 根拠

- `engine/src/prefill/gemm.cu:1154-1168,1303-1317` — HIP 限定の環境読み取り、値判定、BF16 / FP16 の分岐と優先順。
- `engine/src/prefill/wmma_gemm.cu:34-59,276-323` — build macro、GFX11 device cache、dispatch gate、kernel launch、他 arch の helper への委譲。
- `engine/cmake/hip_backend.cmake:105-118`; `engine/cmake/strata_gpu_engine.cmake:482-486` — HIP compile definition と WMMA source の組み込み。
- `engine/sycl/src/prefill/gemm.dp.cpp:851-860,952-962`; `engine/CMakeLists.txt:23-32` — 同名参照の macro guard と SYCL の独立 backend 条件。
