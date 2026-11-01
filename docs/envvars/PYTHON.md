# `PYTHON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更は表示されていません。

## 役割

`PYTHON` は Strata の推論エンジンや通常の CLI / サーバー実行時の設定ではありません。Strata 同梱のシェル形式のビルド、パッケージ作成、補助スクリプトが Python 実行ファイルを選ぶために読みます。確認できた読み取り箇所は `packaging/build_cuda_linux.sh`、`packaging/build_sycl_linux.sh`、`packaging/build_cuda_linux_aarch64.sh`、`spark/build_engine.sh`、`docker/publish.sh`、`sycl/tools/get-cuda-headers.sh` です。

## 値と判定

各箇所はシェルの `${PYTHON:-python3}` を使います。変数が未設定または空文字なら `python3`、空でない場合はその文字列を Python コマンドとして選びます。バージョン番号や実行可能性の検査、文字列の正規化はありません。

| 状態 | 選ばれる値 |
|---|---|
| 未設定 | `python3` |
| 空文字 | `python3` |
| 空でない値 | 指定した文字列 |

選んだコマンドは CUDA / SYCL の Linux エンジン作成時に `collect_libs.py`、`package_engine.py`、`binary_deps.py` 等を実行するために使われます。DGX Spark 用の `spark/build_engine.sh` では、llama.cpp がない場合の `setup.get_llama_cpp()` の呼び出しにも使います。`docker/publish.sh` は `fetch-engines.py` の実行に使い、`sycl/tools/get-cuda-headers.sh` は pip で CUDA ヘッダー wheel を取得し、そのアーカイブを展開する Python 処理にも使います。

## 有効になる条件

この変数が作用するのは上記スクリプトを実行したときだけです。各スクリプトの対象は Linux CUDA / SYCL のビルド、DGX Spark の arm64 ビルド、Docker イメージ公開補助、SYCLomatic 用ヘッダー取得です。特に Spark ビルドスクリプトは Linux arm64 以外では終了コード 2 で終了します（`spark/build_engine.sh:27-30`, `packaging/build_cuda_linux_aarch64.sh:21-24`）。エンジンの実行時や通常の CLI / サーバーモードから `PYTHON` を読む実装は確認できません。

既定値はコマンドライン引数や別環境変数との優先順位で決まるものではなく、これらのシェルスクリプト内のフォールバックです。たとえば DGX Spark の手順は仮想環境の Python を `PYTHON` に明示して `spark/build_engine.sh` を呼ぶ例を示しています（`docs/DGX_SPARK_LINUX.md:54-60`）。

## 実行時の詳細

シェルスクリプト開始時に選択結果を `py` または `PY` に代入し、スクリプト内の Python 子プロセス起動に繰り返し使います。`packaging/build_cuda_linux.sh`、`packaging/build_sycl_linux.sh`、`packaging/build_cuda_linux_aarch64.sh`、`spark/build_engine.sh` は引用符付きで `"$py"` を実行するため、指定値全体が単一の実行ファイル名として扱われます。`docker/publish.sh` と `sycl/tools/get-cuda-headers.sh` は `$PY` / `$py` を引用せず展開するため、シェルの単語分割とパス名展開が適用されます（`docker/publish.sh:55,70`, `sycl/tools/get-cuda-headers.sh:5-10`）。したがって空白を含む値は前者では一つのコマンド名、後者では複数語に分かれ得ます。

スクリプトは選択したコマンドを実行できない場合や Python 補助処理が失敗した場合、`set -e` / `set -euo pipefail` により後続処理へ進まず終了します。`PYTHON` 専用の警告、エラーメッセージ、終了コード変換はありません。読み取りは各シェルプロセス内で変数を代入した時点で行われ、その後の外部変更を再読込する処理はありません。arm64 パッケージスクリプトは `spark/build_engine.sh` を別シェルとして起動し、元の環境を引き継ぐため、子スクリプトも同じ `PYTHON` を選びます（`packaging/build_cuda_linux_aarch64.sh:18,32`, `spark/build_engine.sh:23`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:517`。
- CUDA x86_64 パッケージ作成時の読み取りと Python 補助コマンド: `packaging/build_cuda_linux.sh:14-25,58-66`。
- SYCL パッケージ作成時の読み取りと Python 補助コマンド: `packaging/build_sycl_linux.sh:17-28,54-72`。
- arm64 CUDA パッケージ作成時の読み取り、Spark 子スクリプト起動、パッケージ補助コマンド: `packaging/build_cuda_linux_aarch64.sh:16-32,37-51`。
- Spark ビルド時の読み取り、llama.cpp セットアップ呼び出し、ライブラリ収集: `spark/build_engine.sh:16-25,44-47,89-94`。
- Docker 公開補助での読み取りと取得スクリプトの起動: `docker/publish.sh:27-28,53-55,66-71`。
- CUDA ヘッダー取得補助での読み取りと pip / 展開処理: `sycl/tools/get-cuda-headers.sh:1-10`。
- Spark 手順での仮想環境 Python の指定例: `docs/DGX_SPARK_LINUX.md:54-60`。

候補名の全体検索では、`packaging/lock_wheels.py` の `PYTHON = "3.12"` は wheel ターゲット用のコード定数であり環境読み取りではありません。`apps/host/server/index.mjs` などの `PYTHON` はコード上の変数名で、該当経路は `PYTHON` 環境変数を読むものではありません。候補一覧の `PYTHON` は上記シェルスクリプトで環境から実際に読まれているため、環境変数候補としての食い違いではありません。
