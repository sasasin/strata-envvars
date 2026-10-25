# `STRATA_SYCL_VERSION`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 判定

この名前は `000_envvers.md` に候補として載っていますが、調査対象のソースでは環境変数として読み取られていません。したがって、利用者がプロセス環境に `STRATA_SYCL_VERSION` を設定しても、それを読む Strata の実装箇所は確認できませんでした。

## 実際の用途

`sycl/CMakeLists.txt` で SYCL サブプロジェクトの版数を決める CMake 変数です。トップレベル `CMakeLists.txt` から `project(strata VERSION ...)` の行を読み、その版数を `STRATA_SYCL_VERSION` に設定します。該当行が見つからない場合は `0.1.40.2` を設定し、その値を `project(strata_sycl VERSION ...)` に渡します。現 HEAD のトップレベル版数は `0.1.47` です。

これは CMake の設定・構成時に評価されるビルド用の値であり、生成された Strata 実行ファイルが起動時に読む設定ではありません。値の上書き方法や受理範囲について、Strata が環境変数として検査するコードはありません。

## 根拠

- `sycl/CMakeLists.txt:13-21` — トップレベルの `CMakeLists.txt` を検索し、見つかったプロジェクト版数または固定 fallback を CMake 変数 `STRATA_SYCL_VERSION` に設定して SYCL サブプロジェクトに渡す。
- `CMakeLists.txt:10-14` — トップレベルの Strata 版数は `0.1.47`。SYCL ビルドは別サブプロジェクトとして構成される。
- `rg -n --hidden --glob '!.git/**' 'STRATA_SYCL_VERSION'` による HEAD 全体の検索では、本番ソースの出現は上記 CMake 設定箇所のみ。もう一つの出現 `tools/test_setup_sycl.py:130-131` はテストが一時 CMakeLists を作る文字列であり、環境変数の実装ではない。
