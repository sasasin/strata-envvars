# `STRATA_PREFILL_DENSE_I8_TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

CUDA dense INT8 Tensor Core のプロンプト prefill 判定関数 `strata::kernels::dense_i8_tc_prefill_enabled()` が、この変数を見て機能の許可・禁止を決める。値が `0` と判定されると `false`、それ以外（未設定・空文字を含む）では現在の GPU compute capability が 75 以上の場合に `true` を返す（`engine/src/kernels/cuda/dense_i8_tc.cu:1701-1703,1722-1729`）。

ただし、調査対象の Strata ソースではこの判定関数を呼ぶ製品コードの箇所がなく、宣言と定義だけが見つかった。したがって、この変数が通常の Strata の prefill 計算を切り替える経路は確認できない。実装された prefill kernel と入口関数は存在するが、変数による gate を呼び出す Strata 内部経路はない（`engine/include/strata/kernels/dense_i8_tc.hpp:28-29,43-45`、`engine/src/kernels/cuda/dense_i8_tc.cu:1722-1729,1774-1811`）。

## 値と判定

判定関数内の関数ローカル `static` 初期化子が、初回呼び出し時に `std::getenv` で値を取得し、未設定または空文字なら `-1`、それ以外は `std::atoi(value) != 0` の結果を `1` / `0` として保存する。保存値が `0` のときだけ無効。それ以外は GPU capability 判定へ進む（`engine/src/kernels/cuda/dense_i8_tc.cu:1722-1729`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `dense_i8_tc_prefill_enabled()` が呼ばれた場合 | `-1` として扱い、GPU 判定へ進む | `atoi` が 0 以外を返す値。例: `1`, `-1`, `1suffix` | `atoi` が 0 を返す値。例: `0`, `0suffix`, `true`, `false`, 空白だけ |

`atoi` は文字列全体の妥当性を検査しないため、数値として読める先頭部分の後ろは無視される。先頭の空白や符号も C の `atoi` の変換規則に従い、大文字小文字の比較はしない。文字列が数値で始まらない場合は `0` となり無効扱い。未設定と空文字は明示的な `0` とは異なり、無効化せず GPU 判定へ進む。CLI 引数や別の環境変数による上書き・優先順位は、この関数にはない（同 `1722-1729`）。

## 有効になる条件

- この関数の戻り値が `true` になるには、`atoi` 判定が 0 でないか、変数が未設定または空文字であり、かつ `dense_i8_tc_supported()` が true である必要がある。同関数は現在の device の capability を取得し `major * 10 + minor >= 75` を返す。デバイス取得または属性取得に失敗した場合は capability 0 を返す（`engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`）。
- HIP コンパイル時は `current_cc()` が 0 を返すため、この gate は有効にならない。また、このファイルの prefill kernel 本体は `!__HIPCC__` かつ `__CUDA_ARCH__ >= 750` のときだけコンパイルされる（`engine/src/kernels/cuda/dense_i8_tc.cu:49-53,1552-1557,1678-1680,1683-1686`）。CMake ではこの CUDA ソースが CUDA/HIP 共用の `strata_kernels` ソース一覧に含まれる（`engine/cmake/strata_gpu_engine.cmake:6-8,52-53,97-104`）。
- 対応する量子化型、次元、scratch などは `dense_i8_tc_prefill()` 自身が検査するが、その入口をこの環境変数の判定関数へ接続する Strata 内部呼び出し箇所は見つからなかった。したがって、これらの条件を満たしても通常のアプリケーションでこの変数が kernel の選択や fallback を起こすとは確認できない（`engine/src/kernels/cuda/dense_i8_tc.cu:1774-1785`、同関数の呼び出し箇所はなし）。

## 実行時の詳細

環境変数は判定関数が最初に呼ばれた時点で一度だけ取得され、関数ローカル `static` にキャッシュされる。その後のプロセス内環境変更は再評価されない（`engine/src/kernels/cuda/dense_i8_tc.cu:1722-1729`）。調査対象の Strata 内部には同関数の呼び出し箇所がないため、通常の実行で読み取りが起こる時期や、子プロセスへの引き継ぎは確認できない。

別の `dense_i8_tc_prefill()` 入口は、GPU capability と型を確認し、ポインタ・サイズ・alignment・scratch の条件を満たさなければ `false` を返す。条件を満たす場合は FP16 activation を scratch 上の Q8_1 に量子化して kernel を起動し、最後に `cudaGetLastError() == cudaSuccess` を返す（`engine/src/kernels/cuda/dense_i8_tc.cu:1774-1811`）。この入口は環境変数を読まず、Strata 内部からの呼び出しも見つからなかった。

## ログと測定値

判定関数および prefill 入口に、この環境変数に関するログ出力はない。判定関数は bool を返し、prefill 入口も条件不成立または CUDA launch error 時に `false` を返すだけで、同入口から明示的な警告・エラー文言を出さない（`engine/src/kernels/cuda/dense_i8_tc.cu:1722-1729,1774-1811`）。この変数による実アプリケーション上の選択や測定値は、内部の gate 呼び出しがないため確認できない。

## 根拠

- 変数の読み取りとキャッシュ、値判定: `engine/src/kernels/cuda/dense_i8_tc.cu:1722-1729`
- GPU 対応判定: `engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`
- compile-time guard と prefill kernel: `engine/src/kernels/cuda/dense_i8_tc.cu:49-53,1552-1557,1678-1686`
- 宣言と prefill 入口 API: `engine/include/strata/kernels/dense_i8_tc.hpp:28-29,43-45`
- prefill 入口での条件判定と戻り値: `engine/src/kernels/cuda/dense_i8_tc.cu:1774-1811`
- CUDA/HIP 共用 target とソース登録: `engine/cmake/strata_gpu_engine.cmake:6-8,52-53,97-104`
