# `STRATA_DENSE_PFGEMM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 エンジンの HIP ビルドで、chunk の dense FP16×FP16 GEMM を Strata の RDNA3 WMMA kernel に渡すかを選びます。有効なら条件を満たす GEMM で `strata_pf_gemm_f16_ld()` を試し、使えない形状・GPUなら既存の hipBLAS GEMM を使います。CUDA ビルドではこの環境変数を読みません。

この機能が含まれる `strata-dsv41` 自体は `STRATA_BUILD_DSV41` が ON のときだけ作られる別 executable で、既定ではビルドされません（`CMakeLists.txt:906-920`）。通常の `strata` の設定ではありません。

## 値と判定

名前を受け取る共通 helper `env_tri()` は、未設定なら `-1`、設定済みなら `atoi()` の結果が 0 か非 0 かを返します。helper はこの環境変数以外にも使われますが、本変数の読み取りは `gemm()` 内の呼び出し 1 か所です。

| `STRATA_DENSE_PFGEMM` | `env_tri()` の結果 | `DS4_DEFAULTS` が 0.2.6 指定でない場合 | `DS4_DEFAULTS` が 0.2.6 指定の場合 |
|---|---:|---|---|
| 未設定 | -1 | 有効 | 無効 |
| 空文字 | 0 | 無効 | 無効 |
| `0`、`00`、`junk` | 0 | 無効 | 無効 |
| atoi が 0 以外を返す文字列（例: `1`, `-1`, `1tail`, `  +2x`） | 1 | 有効 | 有効 |

文字列全体の検証はなく、`atoi()` の数値変換結果だけで判定します。したがって先頭の空白や符号は変換規則に従い、数字以降の文字は無視されます。数値に変換できない先頭部分は 0 扱いです。範囲 clamp はありません。

未設定時の既定は `dense_pfgemm_default()` が決めます。別環境変数 `DS4_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致すると既定 OFF、それ以外は既定 ON です。対象変数を明示設定すると `DS4_DEFAULTS` より優先し、明示値の 0 / 非 0 で OFF / ON を決めます。専用 CLI 引数による上書きは見つかりませんでした。

根拠: `src/dsv41/ds4_model.cu:97-101,3441-3446`; `src/dsv41/ds4_experts_rule.hpp:16-28,228-232`。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で `strata-dsv41` をビルドして実行する必要があります。
- 実際に環境変数を読むのは `STRATA_USE_HIP` のビルド分岐内だけです。CUDA 側は同じ `gemm()` で cuBLAS を使用します（`src/dsv41/ds4_model.cu:3444-3464`）。HIP でも、GPU が gfx11 でなければ WMMA 関数が false を返すため hipBLAS に戻ります。
- `gemm()` の各呼び出しで `rows >= 64`、入力 `x16` が 16 バイト境界に整列していることが、WMMA 関数を呼ぶ条件です。関数側はさらに非 null のポインター、`N >= 512`、`K` が kernel block `pfg::BK` の倍数かつ 32 以上、`beta` が 0 または 1、妥当な leading dimension と上限、gfx11 device を要求します。条件を満たさない場合は hipBLAS に進みます。
- `gemm()` は `layer_chunk()` の chunk 行列積などから呼ばれます。たとえば attention projection、shared expert の dense projection、および Engram projection が呼び出し箇所です（`src/dsv41/ds4_model.cu:8074-8079,8123-8129,8364-8369`）。したがって値が有効でも、短い chunk や小さい出力幅など、形状条件を満たさない積では WMMA は実行されません。

根拠: `CMakeLists.txt:906-920,935-937`; `src/dsv41/ds4_model.cu:3441-3464`; `src/prefill/wmma_gemm.cu:684-711`。

## 実行時の詳細

`gemm()` は `rows <= 0` なら先に戻ります。それ以外の最初の呼び出しで `static const bool pf` が初期化され、`env_tri("STRATA_DENSE_PFGEMM")` の判定結果がプロセス内に cache されます。`DS4_DEFAULTS` も `defaults_026()` 内の static 値として初回に cache されます。その後にプロセス環境が変わっても判定は更新されません。

各積では、まず必要な重み列を `c.w16` に FP16 で再構成します。有効条件が揃うと `strata_pf_gemm_f16_ld()` を呼び、true が返ればその積を完了扱いにして次へ進みます。無効設定、呼び出し条件不足、gfx11 以外、または WMMA 関数が false を返す場合は `cublasGemmEx()` の経路へ進みます。HIP ビルドではこの呼び出しが hipBLAS 側です。

環境変数専用の有効化ログや警告はありません。WMMA を使わず fallback したこと自体もログには出しません。fallback の GEMM が失敗すると `gemm()` は `cublasGemmEx: status <status>` をエラー文字列に設定して false を返し、推論側は `maya-ds4: <error>` を stderr に出して終了コード 1 で終了します（`src/dsv41/ds4_model.cu:3461-3464`; `src/dsv41/ds4_main.cpp:1527-1533`）。

## 根拠

- `src/dsv41/ds4_model.cu:97-101` — 未設定と設定値を `atoi()` で三値化する helper。
- `src/dsv41/ds4_experts_rule.hpp:16-28,228-232` — `DS4_DEFAULTS` の完全一致判定と、この変数の既定値・明示値優先。
- `src/dsv41/ds4_model.cu:3435-3466` — WMMA を試す条件、重み再構成、hipBLAS fallback とその失敗文字列。
- `src/prefill/wmma_gemm.cu:684-711` — GEMM の shape / stride / beta / GPU 判定と kernel launch 結果。
- `CMakeLists.txt:906-920,935-937` — DeepSeek executable の build option と prefill kernel のリンク。
- `docs/DETAILS.md` と他の `docs/` を対象名および `dense_pfgemm` で検索しましたが、この変数の説明や測定条件は見つかりませんでした。したがって速度・品質の数値は記載していません。
