# `STRATA_DF2_GEMM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 drafter の Q8_0 GEMM が使う CUDA/HIP カーネル variant の選択を切り替えます。既定値は行列の出力行数に応じた variant 選択で、値 `0` は従来の 8 rows-a-warp 系 variant を選びます。Q4_0 重みの GEMM は別分岐なので、この変数の影響を受けません。

この環境変数を読む実装は `src/kernels/cuda/dflash2.cu` の `df2_gemm()` に 1 か所あります。DFlash2 自体は CUDA と HIP のビルドに含まれ、Metal と SYCL のビルドには含まれません（`CMakeLists.txt:431-436,520`）。通常の実行では `Dflash2Drafter::gemm()` から同カーネルを呼び、DFlash2 の context 記録と drafter block の複数の射影 GEMM に使います（`src/core/dflash2.cpp:404-415,438-450,463-505`）。

## 値と判定

値は `std::atoi()` で 10 進整数に変換され、`df2_gemm()` が最初に Q8 GEMM 分岐へ入ったときに `static const int` として一度だけ読み取られます（`src/kernels/cuda/dflash2.cu:1080-1086`）。

| 環境値 | `atoi` の結果と選択 |
|---|---|
| 未設定 | `1`。行数に応じた既定の variant 選択 |
| 空文字 | `0`。従来 variant 選択 |
| `0`、または先頭から整数として `0` に変換される値 | `0`。従来 variant 選択 |
| 整数として非ゼロに変換される値 | 行数に応じた既定の variant 選択。`1` 以外の値を variant 番号としては使わない |
| 数字で始まらない文字列 | `0`。従来 variant 選択 |

`atoi` は整数部分の後ろを検査しません。したがって `2tail` は `2`、`  +1tail` は `1`、`-1` は `-1` として扱われます。先頭の空白と符号は変換規則に従い、大文字小文字の比較はありません。範囲外整数の `atoi` 結果は C/C++ の仕様上保証できないため、文書化された有効値として扱いません。コードに clamp や無効文字列用の fallback はなく、変換結果がゼロかどうかだけで分岐します（同 `:1080-1086`）。

従来 variant は、合計出力行数 `rows` が 32 の倍数なら variant 1、そうでなければ variant 2 です。既定 variant は `rows <= 1024` なら 20、`rows <= 3072` なら 13、`rows >= 15000` なら 10、それ以外は同じく 32 の倍数判定で 1 または 2 を選びます（同 `:1081-1086`）。

## 有効になる条件

- 実行物が DFlash2 カーネルを含む CUDA または HIP build である必要があります。CMake は `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` のとき DFlash2 を含め、Metal / SYCL は対象外としています（`CMakeLists.txt:431-436,520`）。
- GEMM が Q8_0 重みの分岐に入った場合に限り有効です。`mats[0].q4` が真なら `STRATA_DF2_GEMM4` を使う別分岐から return し、この変数は読まれません（`src/kernels/cuda/dflash2.cu:1031-1033,1077-1080`）。DFlash2 GEMM 呼び出し側は重み tensor の `q4_0` dtype から `q4` を設定します（`src/core/dflash2.cpp:404-414`）。
- 通常の CLI では DFlash2 を使う実行経路が必要です。`--draft dflash2` の開始条件には draft pack、native pack、draft vocabulary / MTP 条件などがあり、条件を満たさない場合は MTP へ fallback するか、`--draft-fallback none` なら開始エラーになります（`src/program/generate.cpp:5330-5334,6765-6818`）。変数自体は CLI 引数を上書きせず、DFlash2 の Q8 GEMM カーネル選択だけに作用します。
- 起動後に環境値を変更しても反映されません。static 初期化後は同じプロセス内の以後の Q8 GEMM 呼び出しでキャッシュ値が使われます（`src/kernels/cuda/dflash2.cu:1080`）。

## 実行時の詳細

通常値（未設定または `atoi` 結果が非ゼロ）では GEMM の合計出力行数に基づいて variant を選びます。`STRATA_DF2_GEMM=0` は、32 の倍数なら variant 1、そうでなければ variant 2 を使います。switch は variant 1 を含む標準経路と 2 から 23 の専用カーネルを起動し、該当 case 以外は既定の GEMM カーネルに進みます（`src/kernels/cuda/dflash2.cu:1081-1113`）。この環境変数の分岐は GEMM カーネルの形状選択であり、DFlash2 の drafter 選択、speculative window 幅、別環境変数の優先順位を変更する処理はありません。

ベンチマーク用 API `df2_gemm_variant()` が非ゼロ値を設定した場合は、その値が環境変数による選択より優先されます。実装コメントと API 宣言はこの setter を bench only とし、通常の DFlash2 呼び出し側からの設定は確認できません（`src/kernels/cuda/dflash2.cu:21,995`; `include/strata/kernels/dflash2.hpp:53-60`; 呼び出しは `src/core/dflash2_gemm_bench.cpp:54`）。

この変数を理由とするログや警告はありません。GEMM 入力形状が不正なら `df2_gemm: unsupported shape` または `df2_gemm: n_out must be a multiple of 16` 等の例外になり、CUDA kernel launch error は `dflash2 kernel gemm8: <CUDA error>` を stderr に出して例外を投げます。これらは環境値の検証ではなく GEMM の形状・起動結果に対する処理です（`src/kernels/cuda/dflash2.cu:24-29,1017-1023,1113`）。

## 根拠

- `src/kernels/cuda/dflash2.cu:1017-1029` — GEMM の形状制約、重み形式の判定と合計出力行数。
- `src/kernels/cuda/dflash2.cu:1031-1078` — Q4_0 分岐が別環境変数を使い、Q8 分岐へ戻らないこと。
- `src/kernels/cuda/dflash2.cu:1080-1113` — 対象変数の読み取り、既定値、variant 判定、カーネル起動。
- `src/core/dflash2.cpp:404-415,438-450,463-505` — DFlash2 の実処理から GEMM への呼び出し。
- `CMakeLists.txt:431-436,520` — DFlash2 の build backend 範囲。
- `src/program/generate.cpp:5330-5334,6765-6818` — CLI 上の DFlash2 条件と起動失敗 / fallback。
