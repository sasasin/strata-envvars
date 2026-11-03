# `DF2B_ND`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DF2B (DFlash2) ベンチマークが head / top-k / selector で処理する draft row 数を指定します。Strata の通常の推論・サーバー経路で読む箇所は見つからず、確認できた読み取りは SYCL の `dflash2_bench` と Metal の `df2_bench` に限られます。SYCL のベンチマークは乱数データで DFlash2 の kernel checks と round timing を行うツールで、実モデルの推論設定ではありません（`sycl/src/kernels/dflash2_bench.cpp:1-9,437-438`）。

## 値と判定

| 実装 | 未設定 | 空文字 | 設定値の変換 |
|---|---:|---:|---|
| SYCL `dflash2_bench` の bench 経路 | 7 | 7 | `atoi`。数値全体の検証・範囲制限なし |
| Metal `df2_bench` の `build_head()` | 7 | 0 | `atoi`。数値全体の検証・範囲制限なし |

SYCL は `envi()` helper が値のポインタと先頭文字の両方を確認し、未設定または空文字なら既定値を返します。Metal はポインタの有無だけで分岐するため、空文字は `atoi("")` により 0 になります。どちらも `atoi` のため、先頭の空白や符号の後にある数値部分を変換し、数値で始まらない文字列は 0 になります。末尾の非数値部分は変換結果の検証に使われません。コードに clamp や無効値時の fallback はありません。

SYCL ソース先頭の説明は `1..7` を想定値として示しますが、実装にその範囲を検査する処理はありません（`sycl/src/kernels/dflash2_bench.cpp:3,56`）。0、負数、7 より大きい値を指定した場合の kernel 内部の結果やエラーは、この調査では実行していないため断定しません。

## 有効になる条件

- SYCL では `dflash2_bench` の既定モード（`bench`）または明示的な `bench` 以外の、`run_bench()` に落ちるモードで使われます。`test`, `gemm`, `attn`, `dp4a`, `bubble`, `small`, `poison`, `poison2`, `ctx` は別関数へ分岐します（`sycl/src/kernels/dflash2_bench.cpp:894-901`）。
- Metal では `df2_bench` の head dispatch 構築時に使われます（`metal/tests/df2_bench.cpp:391-415,452-464`）。
- OS/backend 条件は各ベンチマークのビルド対象に限られます。SYCL 実行ファイルは `dflash2_bench` として定義されています（`sycl/CMakeLists.txt:437-438`）。
- どちらも通常の Strata CLI、サーバー、モデル読込経路が参照する変数ではありません。索引に掲載されていても通常利用者向けの推論環境変数ではありません。

## 実行時の詳細

SYCL の bench 経路では `run_bench()` の開始時に一度値を読み、`D.nd` に保存してから round を構築します。値は `quantize`, `head`, `top-k`, selector の各処理へ渡され、起動時の `config:` ログにも `drafts` として出ます。head の logits 診断表示も `D.nd` を使います（`sycl/src/kernels/dflash2_bench.cpp:486-495,508,250-255,520`）。読み取り後の環境変更を再評価するコードはありません。

SYCL 側の関連バッファは 7 row 分で確保されますが、`D.nd` の範囲検査は見当たりません（`sycl/src/kernels/dflash2_bench.cpp:168-169,494`）。指定値がその容量を外れる場合の結果は、実行せず、また downstream kernel の挙動を Strata の保証として扱わないため記述しません。

Metal は `build_head()` の呼び出しごとに値を読み、head GEMV、top-k、selector の row 数および dispatch grid に使います（`metal/tests/df2_bench.cpp:391-412`）。benchmark の起動時に生成される `config:` 行は `DF2B_ND` を含まないため、SYCL と異なりこの値を表示するログは確認できません（同ファイル `:441-464`）。無効値専用の警告、終了処理、fallback は見つかりませんでした。

## 根拠

- 全ソース参照の検索では、変数名を含むコメントを除く直接読み取りは `sycl/src/kernels/dflash2_bench.cpp:494` と `metal/tests/df2_bench.cpp:393` の 2 箇所です。SYCL の動的な名前 helper は同ファイル `:56` にあり、`DF2B_ND` の呼び出し元 `:494` を確認しました。
- SYCL bench 実行と値の利用: `sycl/src/kernels/dflash2_bench.cpp:486-495,508,520,250-255`。
- Metal head dispatch と呼び出し経路: `metal/tests/df2_bench.cpp:391-415,452-464`。
- SYCL standalone benchmark target: `sycl/CMakeLists.txt:437-438`。
