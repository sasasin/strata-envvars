# `JOBS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`JOBS` は Strata の実行時エンジンではなく、Strata リポジトリに同梱されたビルド用シェルスクリプトが `cmake --build` または `ninja` に渡す並列ビルド数として読む。通常のビルド対象は SYCL 開発ビルド、Linux SYCL/HIP のパッケージビルド、CUDA/HIP split engine、DGX Spark 向け CUDA ビルドである。テスト専用の量子化 oracle ビルドスクリプトも同名を読むが、調査手順の対象範囲から除外する。どの読み取り箇所も、モデル実行・サーバー・CLI の動作を設定しない（`engine/sycl/tools/build.sh:44`、`tools/packaging/build_sycl_linux.sh:29,51`、`tools/packaging/build_hip_linux.sh:32,67-82`、`tools/packaging/build_split_cuda.sh:20,29`、`tools/packaging/build_split_hip.sh:25,38`、`engine/spark/build_engine.sh:23,65,72`、除外対象: `engine/tests/quant/run_oracle.sh:15,35`）。

## 値と判定

各スクリプトはシェルの `${JOBS:-既定値}` 展開を使う。`JOBS` が未設定または空文字なら既定値を使い、それ以外は文字列を数値変換・範囲検査せずビルドコマンドへ渡す。したがって `0`、負数、`abc` なども Strata のスクリプトでは拒否・補正されず、最終的な解釈やエラーは呼び出された CMake/Ninja 側に委ねられる。先頭文字だけの判定や真偽値判定はない。

| 読み取り箇所 | unset / 空文字 | 非空値の渡し方 |
|---|---|---|
| `engine/sycl/tools/build.sh:44` | `12` | `-j` の後へ未引用展開。空白による分割や glob 展開が起こり得る。 |
| `tools/packaging/build_sycl_linux.sh:29,51` | `$(nproc)` の出力 | `jobs` に保存し、`-j "$jobs"` で1引数として渡す。 |
| `tools/packaging/build_hip_linux.sh:32,67,75,82` | `16` | `JOBS` を `-j "$JOBS"` で3つのビルドへ渡す。 |
| `tools/packaging/build_split_cuda.sh:20,29` | `8` | `ninja -j "$JOBS"` へ渡す。 |
| `tools/packaging/build_split_hip.sh:25,38` | `12` | `ninja -j "$JOBS"` へ渡す。 |
| `engine/spark/build_engine.sh:23,65,72` | `$(nproc)` の出力 | `jobs` に保存し、エンジンと（有効なら）vision ビルドへ `-j "$jobs"` で渡す。 |
| `engine/tests/quant/run_oracle.sh:15,35`（テスト専用・対象外） | `$(nproc)` の出力 | 量子化テストの build に `-j "$JOBS"` で渡す。 |

空文字は全箇所で unset と同じく既定値になります。値の検証はなく、`0`、`1`、`16` はいずれもそのまま渡されます。`true`、`false`、空白を含む文字列も Strata は特別扱いしません。SYCL 開発ビルドだけは値を引用せず展開するため、空白や glob 文字がある場合にシェルによる引数分割・展開が加わります（`engine/sycl/tools/build.sh:44`）。`tools/packaging/mac/build_engine.sh` の `JOBS` は `--jobs` CLI 引数で設定するスクリプト内変数（既定 `2`）で、呼び出し元環境から `JOBS` を読んでいない（同ファイル `:28,35`）。その他に見つかった参照はコメント・文書または `HIST_JOBS` 等の別名です。

## 有効になる条件

- `JOBS` を読むのは上記のビルドスクリプトを実行したときだけである。各スクリプトの OS、backend、ビルド対象などの前提は個別に適用される。たとえば Spark 用は Linux arm64 以外で終了し、split 用スクリプトはそれぞれ CUDA/HIP の開発環境を要求する（`engine/spark/build_engine.sh:29-32`、`tools/packaging/build_split_cuda.sh:13-15`、`tools/packaging/build_split_hip.sh:18-20`）。
- `tools/packaging/build_hip_linux.sh` は `VISION_ONLY` が空でない場合、エンジン本体のビルドを飛ばすが、CPU/HIP vision ビルドには同じ `JOBS` を使う（`tools/packaging/build_hip_linux.sh:60-82`）。
- `engine/spark/build_engine.sh` は `BUILD_VISION=1`（既定）ならエンジンと vision の両方に適用する。`BUILD_VISION` が `1` 以外ならエンジンのビルドだけに使う（`engine/spark/build_engine.sh:65-72`）。
- `JOBS` を読む通常の Strata 実行経路、サーバーモード、モデル状態による条件分岐は見つからない。CLI 引数や他の環境変数による `JOBS` の上書きもない。

## 実行時の詳細

読み取りはスクリプト内で `jobs` / `JOBS` に代入するとき、または `-j` 引数を組み立てるときに行い、その値（または既定値）をビルドコマンドへ渡す。実行中の親プロセス環境の変更は子のシェルへ反映されないため、すでに起動したスクリプトの値は変わらない。リクエスト単位の読み取りや Strata エンジン内の cache はない。

テスト専用 `engine/tests/quant/run_oracle.sh` も同じ unset/空文字時の `nproc` fallback を使い、量子化テスト用ターゲットの build にだけ渡す（同ファイル `:12-16,31-35`）。これは環境変数の実装根拠に含めず、実行時機能の説明対象にも含めない。

この値が指定するのはビルドツールへの並列数引数であり、ソース中に `JOBS` を使って生成物の内容や Strata の推論結果を分岐する処理はない。CMake/Ninja が引数をどう解釈するか、その結果として何個の処理を実際に並行させるかは Strata の読み取り処理の範囲外である。

## ログと測定値

`engine/sycl/tools/build.sh` はビルド出力を `build.log` に保存し、最後に `BUILD EXIT <終了コード>`、`errors: <件数>` と失敗ターゲットを出力して、CMake の終了コードを返す（`engine/sycl/tools/build.sh:44-52`）。HIP パッケージビルドは各 build の出力を `$OUT/build*.log` に保存し、失敗時は `$OUT/build.status` に `ABORT ... failed (rc=...)` を記録して終了する（`tools/packaging/build_hip_linux.sh:45-47,67-84`）。他の対象スクリプトは失敗した build コマンドの非ゼロ終了で停止する構造で、`JOBS` 固有の理由ログはない（`tools/packaging/build_sycl_linux.sh:51`、`tools/packaging/build_split_cuda.sh:28-30`、`tools/packaging/build_split_hip.sh:37-40`、`engine/spark/build_engine.sh:65-72`）。並列数に関する測定値は該当資料にない。

## 根拠

- `engine/sycl/tools/build.sh:38-52` — 開発用 SYCL ビルドの既定値、渡し方、終了コードと出力。
- `tools/packaging/build_sycl_linux.sh:25-29,40-52` — Linux SYCL package build の既定値と `strata` ビルド。
- `tools/packaging/build_hip_linux.sh:21-32,45-47,60-84` — HIP パッケージビルドの既定値、vision-only 分岐、各 build と失敗記録。
- `tools/packaging/build_split_cuda.sh:12-29`、`tools/packaging/build_split_hip.sh:17-38` — CUDA/HIP split engine の既定値とターゲットごとの Ninja 呼び出し。
- `engine/spark/build_engine.sh:17-25,29-32,48-73` — Spark 用の既定値、platform 条件、エンジンと vision のビルド。
- `docs/DGX_SPARK_LINUX.md:59` — Spark 向けビルド例で `JOBS=16` を指定。
