# `NCCL_ROOT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`NCCL_ROOT` は実行時の Strata プログラムが読む設定ではなく、分散 CUDA runtime を構成する CMake が NCCL のヘッダーとライブラリを探すときの追加ヒントです。`engine/src/tp/CMakeLists.txt` は `STRATA_TP_CUDA` が有効な場合に限り、`ENV NCCL_ROOT` を `find_path` と `find_library` の `HINTS` に渡します。ヘッダー検索では `include`、ライブラリ検索では `lib` と `lib64` を追加で調べます（`engine/src/tp/CMakeLists.txt:31-41`）。

この変数自体は NCCL 機能を有効化しません。Hy4-Flash の構成では `STRATA_HY4_DISTRIBUTED=ON` が分散構成を有効にし、そのブロックが `STRATA_TP_CUDA` を `ON` にして TP サブディレクトリを追加します（`engine/src/hy4flash/run/CMakeLists.txt:56-64`）。

## 値と判定

Strata の CMake に独自の文字列 parse、空白除去、数値変換、値域検査はありません。値は CMake の `ENV` 指定を通じて探索ディレクトリのヒントとして扱われます。`NCCL_ROOT` 配下に `include/nccl.h` と、`lib` または `lib64` 配下に候補名 `nccl`、`nccl.so.2`、`libnccl.so.2` のいずれかが見つかるかを各検索で判定します（`engine/src/tp/CMakeLists.txt:34-38`）。

| 条件 | unset / 空文字 | 探索に使われる例 | 探索に使われない例 |
|---|---|---|---|
| `STRATA_TP_CUDA=ON` で CMake が NCCL を探すとき | `NCCL_ROOT` のヒントなしで、CMake の通常の探索先を使う | `NCCL_ROOT=/opt/nccl` なら `/opt/nccl/include`、`/opt/nccl/lib`、`/opt/nccl/lib64` をヒントにする | パスが存在しない、または必要なファイルが所定のサブディレクトリにない場合、そのヒントからは見つからない |
| `STRATA_TP_CUDA=OFF` | 参照されない | 該当なし | 値にかかわらず、この CMakeLists では NCCL の検索を行わない |

パスの相対・絶対、空白、複数パスの細かな解釈を Strata が独自に定めるコードはありません。検索結果が既に CMake 変数 `STRATA_NCCL_INCLUDE_DIR` または `STRATA_NCCL_LIBRARY` に設定されている場合は `find_path` / `find_library` がそれぞれ探索を省略するため、`NCCL_ROOT` の変更がその結果に反映されないことがあります。両変数は別々に検索・設定されます（`engine/src/tp/CMakeLists.txt:34-41`）。

## 有効になる条件

- `engine/src/tp/CMakeLists.txt` が構成に含まれ、`STRATA_TP_CUDA` が真であること。CMake のこのオプションの初期値は `OFF` です（`engine/src/tp/CMakeLists.txt:31-33`）。
- Hy4-Flash の分散ビルド経路では `STRATA_HY4_DISTRIBUTED=ON` が必要です。この経路は Linux 以外を fatal error にし、CUDA/NCCL TP サブディレクトリを追加します（`engine/src/hy4flash/run/CMakeLists.txt:56-64`）。
- NCCL ヘッダーとライブラリがそれぞれ見つかること。`NCCL_ROOT` が未設定・空・誤ったパスでも通常の探索先などから両方が見つかれば構成は続きます。片方でも見つからない場合は `NCCL headers and library are required; set STRATA_NCCL_INCLUDE_DIR and STRATA_NCCL_LIBRARY` で CMake 構成が失敗します（`engine/src/tp/CMakeLists.txt:34-38`）。
- ヘッダーとライブラリの場所を CMake 変数 `STRATA_NCCL_INCLUDE_DIR`、`STRATA_NCCL_LIBRARY` で個別指定した場合、各検索結果はそれぞれの指定値に従います。エラーメッセージもこの2変数を代替指定先として案内します（`engine/src/tp/CMakeLists.txt:36-41`）。

## 実行時の詳細

読み取りは CMake configure 時の `find_path` / `find_library` によるもので、Strata の実行ファイルは `NCCL_ROOT` を読み直したり、実行中にパスを更新したりしません。両 CMake 検索コマンドは結果を `STRATA_NCCL_INCLUDE_DIR` と `STRATA_NCCL_LIBRARY` のキャッシュ項目に保存します。そのため同じ build directory で再構成すると、キャッシュ済み結果が優先され、環境変数を変えただけでは再探索されない場合があります（`engine/src/tp/CMakeLists.txt:34-35`）。

検索に成功すると `strata_tp_nccl` が作られ、検出したヘッダーの include path とライブラリがリンク対象に渡されます。検索が失敗した場合は上記 fatal error となり、ビルド用 CMake 構成が中断します（`engine/src/tp/CMakeLists.txt:36-43`）。起動済みプロセス、CLI 引数、リクエストごとの処理への直接の作用はありません。

## ログと測定値

Strata 固有の成功ログや警告はこの設定箇所にありません。必要なヘッダーまたはライブラリが見つからない場合、CMake は `engine/src/tp/CMakeLists.txt:37` の fatal error 文言を出して構成を失敗させます。性能測定値は該当しません。

## 根拠

- `engine/src/tp/CMakeLists.txt:31-43` — CUDA/NCCL 構成条件、環境変数ヒント、探索対象、失敗条件、ターゲットへの設定。
- `engine/src/hy4flash/run/CMakeLists.txt:56-64` — Hy4 分散モードから TP CUDA/NCCL サブディレクトリへ進む条件。
- `docs/DGX_SPARK_LINUX.md:150-163` — Hy4 分散構成で使う CUDA、MPI、NCCL 要件と CMake オプション。
