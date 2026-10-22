# `STRATA_ROOT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 判定

この名前は `000_envvers.md` にありますが、Strata の通常実行コードが読む環境変数ではありません。調査対象の Strata 所有ソースで確認できるのは、SYCL と Metal の CMake build script が同名の CMake 変数を定義し、ソースツリー内のパスを組み立てる用途です。したがって、プロセス実行時の環境変数としての既定値、値の parse、評価時期、実行時効果はありません。

## ビルド時の同名 CMake 変数

SYCL build は `STRATA_ROOT` を `${CMAKE_CURRENT_SOURCE_DIR}/..` として設定します。以降の CMake 設定では、この値を使って Strata のソース・ヘッダー・データへのパスを組み立てます。Metal build では `get_filename_component(... ABSOLUTE)` により、同じく CMake の現在のソースディレクトリの親を絶対パスとして設定し、ggml-common.h や include/source の配置に使います。いずれも `$STRATA_ROOT` のようなプロセス環境変数を参照する処理ではありません。

## 適用範囲

この CMake 変数は SYCL / Metal の configure 時に使われます。設定値は生成される build graph のパスに関係しますが、実行中の `strata` が環境変数 `STRATA_ROOT` を読み取って挙動を変える根拠は見つかりませんでした。

## 根拠

- `sycl/CMakeLists.txt:21-23` — `project()` 後、`set(STRATA_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/..)` で CMake 変数を定義。
- `sycl/CMakeLists.txt:60-62, 437` — CMake 変数をソースファイルのパス指定に利用。
- `metal/CMakeLists.txt:29-35, 90-94` — CMake の `get_filename_component` / `set` で変数を作り、ヘッダーやソースのパスに利用。
- ソース全体の `STRATA_ROOT` 参照を確認したところ、実行時環境読み取り API での参照はありません。`bench/results/` 以下には測定手順やスクリプトがこの名前をシェル変数・Python 環境変数として使う例がありますが、調査手順で除外される測定記録・benchmark 結果の範囲であり、通常の Strata 実行時挙動の根拠にはしていません。
