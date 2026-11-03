# `ONEAPI`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux 向け SYCL エンジンのパッケージを作る `packaging/build_sycl_linux.sh` が、Intel oneAPI のインストール root を指定するために読む build-time 環境変数です。通常の `strata` エンジン実行時の設定ではありません。スクリプトはこの root の `setvars.sh` を読み込み、さらにその下の compiler / MKL ライブラリを package 用に検索します（`packaging/build_sycl_linux.sh:24,33,56-57`）。

## 値と判定

値を boolean や数値として parse せず、パス文字列として使います。

| 入力 | 使用される値 |
| --- | --- |
| 未設定 | `/opt/intel/oneapi` |
| 空文字 | `/opt/intel/oneapi` |
| その他 | 指定された文字列をそのまま oneAPI root として使用 |

`${ONEAPI:-...}` の shell 展開なので、未設定と null（空文字）の両方で既定値になります。空白除去、正規化、存在確認による別パスへの fallback はありません。指定 root の `setvars.sh` を source できない場合は stderr に `build_sycl_linux.sh: <path>/setvars.sh not found or failed` と出して終了コード 2 になります（`packaging/build_sycl_linux.sh:24,33`）。

## 有効になる条件

`packaging/build_sycl_linux.sh` を実行するときだけ参照されます。スクリプトは Linux 向け SYCL package build を行い、`ONEAPI` を runtime engine に渡す処理はありません。`ONEAPI_DEVICE_SELECTOR` は別の環境変数です。SYCL serve wrapper が転送する `ONEAPI_*` も prefix に underscore が続く名前だけで、裸の `ONEAPI` はその対象ではありません（`sycl/serve/strata-sycl.sh:33-42`）。

## 実行時の詳細

スクリプト起動時に `oneapi=${ONEAPI:-/opt/intel/oneapi}` として一度 shell 変数へ取り込みます。そのパスの `setvars.sh` を source し、以後は `compiler/latest/lib` と `mkl/latest/lib` を `collect_libs.py` の検索先に渡します。したがって `ONEAPI` はこの build script 内のパス選択に作用し、生成物の engine 起動時に再評価される設定ではありません（`packaging/build_sycl_linux.sh:24,30-35,56-57`）。

## 根拠

- `packaging/build_sycl_linux.sh:24` は `ONEAPI` を読み、未設定または空文字に `/opt/intel/oneapi` を使います。
- `packaging/build_sycl_linux.sh:33-35` は `setvars.sh` の source 失敗を終了コード 2 とし、source 後に `icpx` が PATH 上にない場合もエラー終了します。
- `packaging/build_sycl_linux.sh:56-57` は同じ root 以下の compiler と MKL の library directory を package collector に渡します。
- `sycl/serve/strata-sycl.sh:33-42` の実行時環境転送は `ONEAPI_*` prefix を対象とし、裸の `ONEAPI` とは別です。
